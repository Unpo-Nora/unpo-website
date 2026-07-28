"""
Lógica del inbox multiagente de WhatsApp (Etapa 1G): autorización y consultas.

El router (`routers/whatsapp_inbox.py`) queda delgado y delega acá toda la resolución de
acceso y las consultas por lotes. Objetivos:

  - Autorización estricta por usuario y por línea (arquitectura §9, protección IDOR).
  - `unread_count` POR usuario derivado de `whatsapp_conversation_reads`.
  - Cero N+1 en el listado del inbox: los datos derivados (última línea, contacto,
    no leídos, último mensaje, agente asignado) se cargan en lotes por página.
  - Compatibilidad cross-dialect: PostgreSQL (prod/harness) y SQLite (tests). Se evita
    `DISTINCT ON`; el "último mensaje" se resuelve por `max(id)`.

Reglas de autorización
----------------------
  admin      -> ve todo.
  vendedor   -> ve una conversación si está asignada a él/ella O si tiene acceso a la
                línea vía `whatsapp_line_user_access.can_view`. El acceso denegado a una
                conversación se traduce como 404 en el router (no se filtra existencia).
"""

import base64
from datetime import datetime
from typing import Dict, List, Optional, Set

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ... import models
from .redaction import mask_identifier

ROLE_ADMIN = "admin"
DIRECTION_INBOUND = "inbound"
ASSIGNMENT_SOURCE_MANUAL = "manual"

# Tipos de identificador que sirven para enmascarar un teléfono (preferencia: E.164).
_PHONE_TYPE = "phone_e164"
_WA_ID_TYPE = "wa_id"


def is_admin(user: models.User) -> bool:
    return user.role == ROLE_ADMIN


# --------------------------------------------------------------------------- #
# Acceso por línea
# --------------------------------------------------------------------------- #
def viewable_line_ids(db: Session, user: models.User) -> Optional[Set[int]]:
    """
    Conjunto de line_id que el usuario puede VER, o None si puede ver todas (admin).
    """
    if is_admin(user):
        return None
    rows = (
        db.query(models.WhatsAppLineUserAccess.line_id)
        .filter(
            models.WhatsAppLineUserAccess.user_id == user.id,
            models.WhatsAppLineUserAccess.can_view.is_(True),
        )
        .all()
    )
    return {lid for (lid,) in rows}


def assigned_line_ids(db: Session, user: models.User) -> Set[int]:
    """Líneas donde el usuario tiene al menos una conversación asignada."""
    rows = (
        db.query(models.WhatsAppConversation.line_id)
        .filter(models.WhatsAppConversation.assigned_user_id == user.id)
        .distinct()
        .all()
    )
    return {lid for (lid,) in rows}


def effective_lines(db: Session, user: models.User) -> List[tuple]:
    """
    Alcance EFECTIVO de líneas: devuelve [(line, can_view, can_send)] ordenado por id.

    effective_line_ids = líneas con can_view=true  UNION  líneas de conversaciones
    asignadas al usuario. Una línea incluida SOLO por asignación se reporta con
    can_view=true y can_send=false (salvo que exista un can_send=true explícito). El
    acceso por asignación NO se convierte en acceso global a la línea: la VISIBILIDAD de
    conversaciones se gobierna por `viewable_line_ids` (can_view) + asignación directa,
    no por este conjunto efectivo.
    """
    if is_admin(user):
        lines = db.query(models.WhatsAppLine).order_by(models.WhatsAppLine.id).all()
        return [(line, True, True) for line in lines]

    access: Dict[int, tuple] = {}
    for lid, cv, cs in (
        db.query(
            models.WhatsAppLineUserAccess.line_id,
            models.WhatsAppLineUserAccess.can_view,
            models.WhatsAppLineUserAccess.can_send,
        )
        .filter(models.WhatsAppLineUserAccess.user_id == user.id)
        .all()
    ):
        access[lid] = (bool(cv), bool(cs))

    effective_ids = {lid for lid, (cv, _cs) in access.items() if cv}
    effective_ids |= assigned_line_ids(db, user)
    if not effective_ids:
        return []

    lines = (
        db.query(models.WhatsAppLine)
        .filter(models.WhatsAppLine.id.in_(effective_ids))
        .order_by(models.WhatsAppLine.id)
        .all()
    )
    out = []
    for line in lines:
        _cv, cs = access.get(line.id, (False, False))
        # Incluida -> viewable; can_send solo si hay permiso explícito.
        out.append((line, True, bool(cs)))
    return out


# --------------------------------------------------------------------------- #
# Acceso por conversación (IDOR-safe)
# --------------------------------------------------------------------------- #
def can_access_conversation(
    db: Session, user: models.User, conv: models.WhatsAppConversation
) -> bool:
    """
    ¿El usuario puede acceder a esta conversación (ya cargada)?

    admin -> siempre; asignada a él/ella -> sí; acceso a la línea (can_view) -> sí.
    Se usa también para REVALIDAR bajo lock (mark_read/assignment) sin re-fetch.
    """
    if is_admin(user):
        return True
    if conv.assigned_user_id == user.id:
        return True
    has_line = (
        db.query(models.WhatsAppLineUserAccess.id)
        .filter(
            models.WhatsAppLineUserAccess.user_id == user.id,
            models.WhatsAppLineUserAccess.line_id == conv.line_id,
            models.WhatsAppLineUserAccess.can_view.is_(True),
        )
        .first()
    )
    return has_line is not None


def get_authorized_conversation(
    db: Session, user: models.User, conversation_id: int
) -> Optional[models.WhatsAppConversation]:
    """
    Devuelve la conversación si el usuario puede accederla, o None si no existe o no
    está autorizado (el router traduce None -> 404 para no filtrar existencia).
    """
    conv = (
        db.query(models.WhatsAppConversation)
        .filter(models.WhatsAppConversation.id == conversation_id)
        .first()
    )
    if conv is None:
        return None
    return conv if can_access_conversation(db, user, conv) else None


def user_can_send_on_line(db: Session, user: models.User, line_id: int) -> bool:
    """¿El usuario puede ENVIAR en la línea? (admin siempre; vendedor por can_send)."""
    if is_admin(user):
        return True
    row = (
        db.query(models.WhatsAppLineUserAccess.can_send)
        .filter(
            models.WhatsAppLineUserAccess.user_id == user.id,
            models.WhatsAppLineUserAccess.line_id == line_id,
        )
        .first()
    )
    return bool(row[0]) if row is not None else False


# --------------------------------------------------------------------------- #
# No leídos POR usuario (whatsapp_conversation_reads)
# --------------------------------------------------------------------------- #
def unread_conditions(user_id: int):
    """
    Condiciones reutilizables para "mensaje inbound no leído por el usuario":
    devuelve (join_condition, where_clause) sobre WhatsAppMessage (M) y Read (R).
    """
    M = models.WhatsAppMessage
    R = models.WhatsAppConversationRead
    join_cond = and_(R.conversation_id == M.conversation_id, R.user_id == user_id)
    where = and_(
        M.direction == DIRECTION_INBOUND,
        or_(R.last_read_message_id.is_(None), M.id > R.last_read_message_id),
    )
    return join_cond, where


def unread_counts_for(
    db: Session, user_id: int, conversation_ids: List[int]
) -> Dict[int, int]:
    """
    {conversation_id: unread_count} para el usuario, en UNA sola consulta (sin N+1).

    unread = mensajes inbound con id > last_read_message_id del usuario; si no hay fila
    de lectura, todos los inbound cuentan. Los outbound nunca cuentan.
    """
    if not conversation_ids:
        return {}
    M = models.WhatsAppMessage
    R = models.WhatsAppConversationRead
    join_cond, where = unread_conditions(user_id)
    rows = (
        db.query(M.conversation_id, func.count(M.id))
        .outerjoin(R, join_cond)
        .filter(M.conversation_id.in_(conversation_ids), where)
        .group_by(M.conversation_id)
        .all()
    )
    counts = {cid: int(n) for (cid, n) in rows}
    return {cid: counts.get(cid, 0) for cid in conversation_ids}


def unread_count_single(db: Session, user_id: int, conversation_id: int) -> int:
    return unread_counts_for(db, user_id, [conversation_id]).get(conversation_id, 0)


# --------------------------------------------------------------------------- #
# Cargas por lote para el listado (sin N+1)
# --------------------------------------------------------------------------- #
def last_messages_for(
    db: Session, conversation_ids: List[int]
) -> Dict[int, models.WhatsAppMessage]:
    """
    {conversation_id: ÚLTIMO mensaje} donde "último" = ORDER BY created_at DESC, id DESC.

    NO usa max(id): un mensaje con id mayor pero created_at anterior no es el último.
    Se resuelve en UN lote (sin N+1) con `row_number()` particionado, compatible con
    PostgreSQL y SQLite (window functions).
    """
    if not conversation_ids:
        return {}
    M = models.WhatsAppMessage
    rn = (
        func.row_number()
        .over(partition_by=M.conversation_id, order_by=(M.created_at.desc(), M.id.desc()))
        .label("rn")
    )
    sub = (
        db.query(M.id.label("mid"), rn)
        .filter(M.conversation_id.in_(conversation_ids))
        .subquery()
    )
    last_ids = [row.mid for row in db.query(sub.c.mid).filter(sub.c.rn == 1).all()]
    if not last_ids:
        return {}
    msgs = db.query(M).filter(M.id.in_(last_ids)).all()
    return {m.conversation_id: m for m in msgs}


# --------------------------------------------------------------------------- #
# Cursor pagination (keyset) para el historial de mensajes
# --------------------------------------------------------------------------- #
def encode_cursor(created_at, message_id: int) -> str:
    """Cursor opaco que representa (created_at, id) del último mensaje entregado."""
    raw = f"{created_at.isoformat()}|{int(message_id)}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str):
    """
    Devuelve (created_at: datetime, id: int) o lanza ValueError si el cursor es inválido.

    El cursor es solo una POSICIÓN de keyset; no otorga acceso: la consulta siempre queda
    acotada a la conversación autorizada, así que un cursor de otra conversación solo
    posiciona dentro de ESTA (no filtra mensajes ajenos).
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        iso, id_str = raw.rsplit("|", 1)
        return datetime.fromisoformat(iso), int(id_str)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("cursor inválido") from exc


def masked_phones_for(db: Session, contact_ids: List[int]) -> Dict[int, str]:
    """{contact_id: teléfono enmascarado} — prefiere phone_e164, si no wa_id."""
    if not contact_ids:
        return {}
    I = models.WhatsAppContactIdentifier
    rows = (
        db.query(I.contact_id, I.identifier_type, I.identifier_value)
        .filter(
            I.contact_id.in_(contact_ids),
            I.identifier_type.in_([_PHONE_TYPE, _WA_ID_TYPE]),
        )
        .all()
    )
    best: Dict[int, tuple] = {}
    for cid, itype, value in rows:
        cur = best.get(cid)
        if cur is None or (itype == _PHONE_TYPE and cur[0] != _PHONE_TYPE):
            best[cid] = (itype, value)
    return {cid: mask_identifier(value) for cid, (itype, value) in best.items()}


def users_by_ids(db: Session, user_ids: List[int]) -> Dict[int, models.User]:
    ids = [uid for uid in user_ids if uid is not None]
    if not ids:
        return {}
    return {u.id: u for u in db.query(models.User).filter(models.User.id.in_(ids)).all()}


def lines_by_ids(db: Session, line_ids: List[int]) -> Dict[int, models.WhatsAppLine]:
    ids = list({lid for lid in line_ids if lid is not None})
    if not ids:
        return {}
    return {
        l.id: l
        for l in db.query(models.WhatsAppLine).filter(models.WhatsAppLine.id.in_(ids)).all()
    }


def contacts_by_ids(db: Session, contact_ids: List[int]) -> Dict[int, models.WhatsAppContact]:
    ids = list({cid for cid in contact_ids if cid is not None})
    if not ids:
        return {}
    return {
        c.id: c
        for c in db.query(models.WhatsAppContact)
        .filter(models.WhatsAppContact.id.in_(ids))
        .all()
    }


# --------------------------------------------------------------------------- #
# Búsqueda: escape de patrones LIKE (el término se trata como literal)
# --------------------------------------------------------------------------- #
def escape_like(term: str) -> str:
    """Escapa `\\ % _` para usar el término como literal dentro de un LIKE/ILIKE."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
