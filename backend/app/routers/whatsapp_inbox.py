"""
API autenticada del inbox multiagente de WhatsApp (Etapa 1G).

Router SEPARADO del webhook (`routers/whatsapp.py`, público): acá todo exige JWT y
autorización estricta por usuario y por línea. El router es delgado: delega acceso y
consultas en `services/whatsapp/inbox.py` y construye schemas Pydantic explícitos
(`schemas_whatsapp_inbox`) — nunca retorna modelos SQLAlchemy crudos.

Rutas (arquitectura §6, contrato 1G):
    GET   /whatsapp/lines
    GET   /whatsapp/conversations
    GET   /whatsapp/conversations/{id}
    GET   /whatsapp/conversations/{id}/messages
    GET   /whatsapp/unread-counts
    POST  /whatsapp/conversations/{id}/read
    PATCH /whatsapp/conversations/{id}/assignment
    GET   /whatsapp/conversations/{id}/assignments

Autorización: admin ve/asigna todo; vendedor accede a una conversación si está asignada
a él/ella o si tiene acceso a la línea (`whatsapp_line_user_access.can_view`). El acceso
denegado a una conversación responde 404 (no se filtra existencia — IDOR-safe, §9). La
asignación es exclusiva de admin (403 para el resto).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import crud, models
from .. import schemas_whatsapp_inbox as sch
from ..database import get_db
from ..dependencies.permissions import VALID_ROLES, require_roles
from ..services.whatsapp import inbox as svc
from ..services.whatsapp.redaction import safe_error

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp-inbox"])

# Dependencias de rol reutilizables.
_staff = require_roles("admin", "vendedor")
_admin_only = require_roles("admin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Constructores de schema (sin exponer campos sensibles)
# --------------------------------------------------------------------------- #
def _line_ref(line: Optional[models.WhatsAppLine], line_id: int) -> sch.LineRef:
    if line is None:
        return sch.LineRef(id=line_id, label="", display_number="")
    return sch.LineRef(id=line.id, label=line.label, display_number=line.display_number)


def _contact_out(contact: Optional[models.WhatsAppContact], contact_id: int,
                 masked_phone: Optional[str]) -> sch.ContactOut:
    display = contact.display_name if contact is not None else None
    return sch.ContactOut(id=contact_id, display_name=display, phone_masked=masked_phone)


def _assigned_user_out(user: Optional[models.User]) -> Optional[sch.AssignedUserOut]:
    if user is None:
        return None
    return sch.AssignedUserOut(id=user.id, full_name=user.full_name, role=user.role)


def _preview(text_body: Optional[str]) -> Optional[str]:
    if not text_body:
        return None
    text = text_body.strip()
    if len(text) > sch.PREVIEW_MAX_LENGTH:
        return text[: sch.PREVIEW_MAX_LENGTH] + "…"
    return text


def _assignment_out(row: models.WhatsAppConversationAssignment) -> sch.AssignmentHistoryOut:
    return sch.AssignmentHistoryOut(
        id=row.id,
        from_user_id=row.from_user_id,
        to_user_id=row.to_user_id,
        assigned_by_user_id=row.assigned_by_user_id,
        assignment_source=row.assignment_source,
        reason=row.reason,
        created_at=row.created_at,
    )


# --------------------------------------------------------------------------- #
# GET /whatsapp/lines
# --------------------------------------------------------------------------- #
@router.get("/lines", response_model=List[sch.LineOut])
def list_lines(db: Session = Depends(get_db), current_user: models.User = Depends(_staff)):
    """
    Líneas del alcance EFECTIVO del usuario (admin: todas; vendedor: can_view UNION
    líneas de conversaciones asignadas). Una línea incluida solo por asignación aparece
    con can_view=true y can_send=false (salvo can_send explícito).
    """
    return [
        sch.LineOut(
            id=line.id, label=line.label, display_number=line.display_number,
            provider=line.provider, is_active=line.is_active,
            can_view=can_view, can_send=can_send,
        )
        for (line, can_view, can_send) in svc.effective_lines(db, current_user)
    ]


# --------------------------------------------------------------------------- #
# GET /whatsapp/conversations
# --------------------------------------------------------------------------- #
@router.get("/conversations", response_model=sch.ConversationListResponse)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_staff),
    line_id: Optional[int] = Query(None),
    assigned_user_id: Optional[int] = Query(None),
    assigned_to_me: bool = Query(False),
    unassigned: bool = Query(False),
    unread_only: bool = Query(False),
    status_filter: Optional[str] = Query(None, alias="status", max_length=32),
    search: Optional[str] = Query(None, max_length=sch.SEARCH_MAX_LENGTH),
    limit: int = Query(sch.CONVERSATIONS_DEFAULT_LIMIT, ge=1, le=sch.CONVERSATIONS_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    C = models.WhatsAppConversation
    q = db.query(C)

    # --- autorización: admin ve todo; vendedor solo asignadas o líneas accesibles ---
    if not svc.is_admin(current_user):
        viewable = svc.viewable_line_ids(db, current_user) or set()
        conds = [C.assigned_user_id == current_user.id]
        if viewable:
            conds.append(C.line_id.in_(viewable))
        q = q.filter(or_(*conds))

    # --- filtros ---
    if line_id is not None:
        q = q.filter(C.line_id == line_id)
    if assigned_user_id is not None:
        q = q.filter(C.assigned_user_id == assigned_user_id)
    if assigned_to_me:
        q = q.filter(C.assigned_user_id == current_user.id)
    if unassigned:
        q = q.filter(C.assigned_user_id.is_(None))
    if status_filter:
        q = q.filter(C.status == status_filter)
    if unread_only:
        M = models.WhatsAppMessage
        R = models.WhatsAppConversationRead
        join_cond, where = svc.unread_conditions(current_user.id)
        sub = (
            db.query(M.id)
            .outerjoin(R, join_cond)
            .filter(M.conversation_id == C.id, where)
        )
        q = q.filter(sub.exists())
    if search:
        term = search.strip()
        if term:
            like = f"%{svc.escape_like(term)}%"
            Ct = models.WhatsAppContact
            Idf = models.WhatsAppContactIdentifier
            name_ids = db.query(Ct.id).filter(Ct.display_name.ilike(like, escape="\\"))
            id_ids = db.query(Idf.contact_id).filter(
                Idf.identifier_value.ilike(like, escape="\\"))
            q = q.filter(or_(C.contact_id.in_(name_ids), C.contact_id.in_(id_ids)))
            # No se registra el término (puede contener un teléfono): solo su longitud.
            logger.info("[whatsapp-inbox] búsqueda de conversaciones len=%d", len(term))

    # --- orden estable + paginación (limit+1 para has_more) ---
    q = q.order_by(func.coalesce(C.last_message_at, C.created_at).desc(), C.id.desc())
    rows = q.limit(limit + 1).offset(offset).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    # --- cargas por lote (sin N+1) ---
    conv_ids = [c.id for c in rows]
    line_ids = [c.line_id for c in rows]
    contact_ids = [c.contact_id for c in rows]
    assigned_ids = [c.assigned_user_id for c in rows if c.assigned_user_id is not None]

    lines = svc.lines_by_ids(db, line_ids)
    contacts = svc.contacts_by_ids(db, contact_ids)
    masked = svc.masked_phones_for(db, contact_ids)
    unread = svc.unread_counts_for(db, current_user.id, conv_ids)
    last_msgs = svc.last_messages_for(db, conv_ids)
    users = svc.users_by_ids(db, assigned_ids)

    items: List[sch.ConversationListItem] = []
    for c in rows:
        last = last_msgs.get(c.id)
        items.append(sch.ConversationListItem(
            conversation_id=c.id,
            line=_line_ref(lines.get(c.line_id), c.line_id),
            status=c.status,
            contact=_contact_out(contacts.get(c.contact_id), c.contact_id,
                                 masked.get(c.contact_id)),
            assigned_user=_assigned_user_out(users.get(c.assigned_user_id)),
            # Coherencia: los campos del "último mensaje" (incluido last_message_at)
            # derivan del MISMO mensaje elegido por last_messages_for, no de
            # conversation.last_message_at (que podría contradecirlo).
            last_message_at=(last.created_at if last else c.last_message_at),
            last_message_direction=last.direction if last else None,
            last_message_type=last.message_type if last else None,
            last_message_preview=_preview(last.text_body) if last else None,
            unread_count=unread.get(c.id, 0),
        ))

    return sch.ConversationListResponse(
        items=items, limit=limit, offset=offset, count=len(items), has_more=has_more,
    )


# --------------------------------------------------------------------------- #
# GET /whatsapp/conversations/{id}
# --------------------------------------------------------------------------- #
@router.get("/conversations/{conversation_id}", response_model=sch.ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_staff),
):
    conv = svc.get_authorized_conversation(db, current_user, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    line = db.query(models.WhatsAppLine).filter(
        models.WhatsAppLine.id == conv.line_id).first()
    contact = db.query(models.WhatsAppContact).filter(
        models.WhatsAppContact.id == conv.contact_id).first()
    masked = svc.masked_phones_for(db, [conv.contact_id]).get(conv.contact_id)
    assigned = svc.users_by_ids(db, [conv.assigned_user_id]).get(conv.assigned_user_id)
    unread = svc.unread_count_single(db, current_user.id, conv.id)

    # `lead_id` solo si el usuario está autorizado a LEER ese lead (política de leads).
    # Si no, se devuelve null sin 403 ni revelar por otra vía que el lead existe.
    lead_id_out = None
    if conv.lead_id is not None:
        lead = db.query(models.Lead).filter(models.Lead.id == conv.lead_id).first()
        if lead is not None and crud.can_read_lead(current_user, lead):
            lead_id_out = conv.lead_id

    return sch.ConversationDetail(
        conversation_id=conv.id,
        line=_line_ref(line, conv.line_id),
        contact=_contact_out(contact, conv.contact_id, masked),
        lead_id=lead_id_out,
        assigned_user=_assigned_user_out(assigned),
        status=conv.status,
        unread_count=unread,
        last_message_at=conv.last_message_at,
        last_inbound_at=conv.last_inbound_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


# --------------------------------------------------------------------------- #
# GET /whatsapp/conversations/{id}/messages
# --------------------------------------------------------------------------- #
@router.get("/conversations/{conversation_id}/messages",
            response_model=sch.MessagesResponse)
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_staff),
    limit: int = Query(sch.MESSAGES_DEFAULT_LIMIT, ge=1, le=sch.MESSAGES_MAX_LIMIT),
    cursor: Optional[str] = Query(None),
    offset: Optional[int] = Query(None, ge=0, deprecated=True),
):
    """
    Historial paginado por **keyset/cursor** (mecanismo documentado). Orden canónico
    `created_at ASC, id ASC`. `cursor` codifica (last_created_at, last_id); la página
    siguiente trae `created_at > c` OR (`created_at = c` AND `id > c_id`). `offset` se
    mantiene solo como compatibilidad deprecada y se ignora si viene `cursor`.
    """
    conv = svc.get_authorized_conversation(db, current_user, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    M = models.WhatsAppMessage
    q = db.query(M).filter(M.conversation_id == conv.id)

    use_offset = None
    if cursor is not None:
        try:
            c_created, c_id = svc.decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=422, detail="Cursor inválido")
        # El cursor es solo una posición; la consulta sigue acotada a esta conversación,
        # así que un cursor de otra conversación no otorga acceso ni amplía el scope.
        q = q.filter(or_(M.created_at > c_created,
                         and_(M.created_at == c_created, M.id > c_id)))

    # order_by SIEMPRE antes de offset/limit.
    q = q.order_by(M.created_at.asc(), M.id.asc())
    if cursor is None:
        use_offset = offset or 0
        if use_offset:
            q = q.offset(use_offset)

    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        sch.MessageOut(
            id=m.id, conversation_id=m.conversation_id, direction=m.direction,
            message_type=m.message_type, text_body=m.text_body,
            current_status=m.current_status, provider_timestamp=m.provider_timestamp,
            sender_user_id=m.sender_user_id, created_at=m.created_at,
        )
        for m in rows
    ]
    next_cursor = (
        svc.encode_cursor(rows[-1].created_at, rows[-1].id) if rows and has_more else None
    )
    return sch.MessagesResponse(
        items=items, limit=limit, count=len(items), has_more=has_more,
        next_cursor=next_cursor, offset=use_offset,
    )


# --------------------------------------------------------------------------- #
# GET /whatsapp/unread-counts
# --------------------------------------------------------------------------- #
@router.get("/unread-counts", response_model=sch.UnreadCountsResponse)
def unread_counts(db: Session = Depends(get_db),
                  current_user: models.User = Depends(_staff)):
    """Totales de no leídos del usuario, por línea accesible."""
    C = models.WhatsAppConversation
    q = db.query(C.id, C.line_id)
    if not svc.is_admin(current_user):
        viewable = svc.viewable_line_ids(db, current_user) or set()
        conds = [C.assigned_user_id == current_user.id]
        if viewable:
            conds.append(C.line_id.in_(viewable))
        q = q.filter(or_(*conds))
    convs = q.all()
    conv_ids = [cid for (cid, _lid) in convs]
    line_of = {cid: lid for (cid, lid) in convs}
    counts = svc.unread_counts_for(db, current_user.id, conv_ids)

    per_line = {}
    total = 0
    for cid, n in counts.items():
        total += n
        lid = line_of.get(cid)
        if lid is not None:
            per_line[lid] = per_line.get(lid, 0) + n

    items = [
        sch.LineUnread(line_id=line.id, label=line.label,
                       unread_count=per_line.get(line.id, 0))
        for (line, _cv, _cs) in svc.effective_lines(db, current_user)
    ]
    return sch.UnreadCountsResponse(total_unread=total, lines=items)


# --------------------------------------------------------------------------- #
# POST /whatsapp/conversations/{id}/read
# --------------------------------------------------------------------------- #
def _advance_read(read, target_id):
    """Avanza el puntero de lectura solo hacia adelante. Devuelve True si cambió."""
    if target_id is not None and (
        read.last_read_message_id is None or target_id > read.last_read_message_id
    ):
        read.last_read_message_id = target_id
        read.last_read_at = _utcnow()
        return True
    return False


@router.post("/conversations/{conversation_id}/read", response_model=sch.ReadResponse)
def mark_read(
    conversation_id: int,
    body: Optional[sch.ReadRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_staff),
):
    """
    Marca leído de forma ATÓMICA y MONOTÓNICA. La conversación se bloquea con
    `FOR UPDATE` como mutex por conversation_id: serializa marcados concurrentes y cubre
    la creación inicial de la fila de lectura, de modo que `last_read_message_id` solo
    avanza, hay a lo sumo una fila por (conversation_id, user_id) y una carrera de
    creación nunca produce 500. Rollback completo ante cualquier error.
    """
    C = models.WhatsAppConversation
    M = models.WhatsAppMessage
    R = models.WhatsAppConversationRead

    conv = db.query(C).filter(C.id == conversation_id).with_for_update().first()
    if conv is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    # Revalidar autorización BAJO el lock.
    if not svc.can_access_conversation(db, current_user, conv):
        db.rollback()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    payload = body or sch.ReadRequest()
    if payload.last_read_message_id is not None:
        belongs = (
            db.query(M.id)
            .filter(M.id == payload.last_read_message_id, M.conversation_id == conv.id)
            .first()
        )
        if belongs is None:
            db.rollback()
            raise HTTPException(status_code=404,
                                detail="Mensaje no encontrado en la conversación")
        target_id = payload.last_read_message_id
    else:
        target_id = db.query(func.max(M.id)).filter(M.conversation_id == conv.id).scalar()

    try:
        read = (
            db.query(R)
            .filter(R.conversation_id == conv.id, R.user_id == current_user.id)
            .first()
        )
        if read is None:
            read = R(conversation_id=conv.id, user_id=current_user.id,
                     last_read_message_id=target_id, last_read_at=_utcnow())
            db.add(read)
        else:
            _advance_read(read, target_id)
        db.commit()
    except IntegrityError:
        # Defensa extra al mutex: si otra transacción creó la fila, se avanza sobre ella.
        db.rollback()
        read = (
            db.query(R)
            .filter(R.conversation_id == conv.id, R.user_id == current_user.id)
            .first()
        )
        if read is None:
            raise
        _advance_read(read, target_id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("[whatsapp-inbox] fallo marcando leído conversation_id=%s: %s",
                     conversation_id, safe_error(exc))
        raise HTTPException(status_code=500, detail="No se pudo marcar como leído")

    unread = svc.unread_count_single(db, current_user.id, conv.id)
    return sch.ReadResponse(
        conversation_id=conv.id,
        last_read_message_id=read.last_read_message_id,
        unread_count=unread,
    )


# --------------------------------------------------------------------------- #
# PATCH /whatsapp/conversations/{id}/assignment
# --------------------------------------------------------------------------- #
@router.patch("/conversations/{conversation_id}/assignment",
              response_model=sch.AssignmentResponse)
def assign_conversation(
    conversation_id: int,
    body: sch.AssignmentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin_only),
):
    """
    Asigna/reasigna una conversación. Solo admin. ATÓMICO bajo `FOR UPDATE`: se bloquea
    la conversación antes de leer `old_user_id`, se evalúa "mismo usuario" y se revalida
    el acceso del destino a la línea DENTRO de la transacción, y la actualización más el
    historial se confirman juntos. Concurrentes se serializan → el historial forma una
    cadena lineal (cada `from_user_id` = el estado confirmado inmediatamente anterior).
    Rollback completo ante cualquier error.
    """
    C = models.WhatsAppConversation
    conv = db.query(C).filter(C.id == conversation_id).with_for_update().first()
    if conv is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    line_id = conv.line_id

    target = db.query(models.User).filter(
        models.User.id == body.assigned_user_id).first()
    if target is None or target.role not in VALID_ROLES:
        db.rollback()
        raise HTTPException(status_code=400, detail="Usuario destino inválido")

    # El usuario destino debe tener acceso a la línea (admin lo tiene siempre); se
    # revalida BAJO el lock.
    if target.role != svc.ROLE_ADMIN:
        has_access = (
            db.query(models.WhatsAppLineUserAccess.id)
            .filter(
                models.WhatsAppLineUserAccess.user_id == target.id,
                models.WhatsAppLineUserAccess.line_id == line_id,
                models.WhatsAppLineUserAccess.can_view.is_(True),
            )
            .first()
        )
        if has_access is None:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="El usuario destino no tiene acceso a la línea",
            )

    old_user_id = conv.assigned_user_id  # leído BAJO el lock
    if old_user_id == target.id:
        # Sin cambio: se libera el lock y NO se agrega historial (idempotente).
        db.rollback()
        return sch.AssignmentResponse(
            conversation_id=conversation_id, assigned_user_id=old_user_id,
            changed=False, assignment=None,
        )

    try:
        conv.assigned_user_id = target.id
        conv.assignment_source = svc.ASSIGNMENT_SOURCE_MANUAL
        history = models.WhatsAppConversationAssignment(
            conversation_id=conversation_id,
            from_user_id=old_user_id,
            to_user_id=target.id,
            assigned_by_user_id=current_user.id,
            assignment_source=svc.ASSIGNMENT_SOURCE_MANUAL,
            reason=body.reason,
        )
        db.add(conv)
        db.add(history)
        db.commit()
        db.refresh(history)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        # safe_error: sin SQL, sin parámetros (reason/email/teléfono), sin traceback.
        logger.error("[whatsapp-inbox] fallo asignando conversation_id=%s: %s",
                     conversation_id, safe_error(exc))
        raise HTTPException(status_code=500, detail="No se pudo asignar la conversación")

    logger.info("[whatsapp-inbox] conversación asignada conversation_id=%s to_user_id=%s",
                conversation_id, target.id)
    return sch.AssignmentResponse(
        conversation_id=conversation_id, assigned_user_id=target.id,
        changed=True, assignment=_assignment_out(history),
    )


# --------------------------------------------------------------------------- #
# GET /whatsapp/conversations/{id}/assignments
# --------------------------------------------------------------------------- #
@router.get("/conversations/{conversation_id}/assignments",
            response_model=sch.AssignmentHistoryResponse)
def assignment_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_staff),
):
    conv = svc.get_authorized_conversation(db, current_user, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    A = models.WhatsAppConversationAssignment
    rows = (
        db.query(A)
        .filter(A.conversation_id == conv.id)
        .order_by(A.created_at.asc(), A.id.asc())
        .all()
    )
    return sch.AssignmentHistoryResponse(items=[_assignment_out(r) for r in rows])
