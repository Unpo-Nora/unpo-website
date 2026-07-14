from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List
from .. import crud, models, schemas, database, meta_api
from ..utils import importer
from ..dependencies.permissions import require_roles
import urllib.parse
import os
import json
import hmac
import hashlib

router = APIRouter(
    prefix="/leads",
    tags=["leads"]
)

get_db = database.get_db

@router.post("/", response_model=schemas.LeadResponse)
def create_lead(lead: schemas.LeadCreate, db: Session = Depends(get_db)):
    created_lead = crud.create_lead(db=db, lead=lead)
    return created_lead

from .auth import get_current_user

@router.get("/", response_model=List[schemas.LeadResponse])
def read_leads(
    skip: int = 0,
    limit: int = 5000,
    status: str = Query(None),
    brand: str = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print(f"DEBUG: User {current_user.email} with role {current_user.role} requesting leads. status={status} brand={brand}")
    if current_user.role == "admin":
        results = crud.get_leads(db, skip=skip, limit=limit, status=status, brand=brand)
        print(f"DEBUG: Admin results count: {len(results)}")
        return results

    # For sellers:
    # 1. If searching for NEW, show all NEW.
    # 2. If searching for CONTACTED, show only OWNED.
    # 3. If no status (initial fetch), return all NEW + OWNED CONTACTED.

    if status == "NEW":
        return crud.get_leads(db, skip=skip, limit=limit, status="NEW", brand=brand)
    elif status == "CONTACTED":
        return crud.get_leads(db, skip=skip, limit=limit, status="CONTACTED", seller=current_user.email, brand=brand)
    elif status == "CLIENT":
        return crud.get_leads(db, skip=skip, limit=limit, status="CLIENT", seller=current_user.email, brand=brand)
    elif status:
        return crud.get_leads(db, skip=skip, limit=limit, status=status, seller=current_user.email, brand=brand)
    else:
        # Prioritize owned contacted leads
        owned_contacted = crud.get_leads(db, limit=limit, status="CONTACTED", seller=current_user.email, brand=brand)
        remaining_limit = limit - len(owned_contacted)
        all_new = []
        if remaining_limit > 0:
            all_new = crud.get_leads(db, limit=remaining_limit, status="NEW", brand=brand)
        return owned_contacted + all_new

@router.patch("/{lead_id}", response_model=schemas.LeadResponse)
def update_lead(
    lead_id: int,
    lead_update: schemas.LeadUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    """
    Actualiza un lead con aislamiento por vendedor.

    - Admin: puede modificar cualquier lead, incluido reasignar `seller` y estados.
    - Vendedor: solo puede modificar leads que le pertenecen (lead.seller == su email)
      y únicamente los campos `status`, `notes`, `feedback_status`. NO puede tocar
      `seller` de ninguna forma (ni liberar con null ni apropiarse enviando su email),
      ni `assigned_seller_phone`/tracking (no forman parte de LeadUpdate). Los leads
      NEW globales se toman exclusivamente por PUT /leads/{id}/mark-contacted, no por
      este PATCH.
    """
    payload = lead_update.model_dump(exclude_unset=True)

    if current_user.role != "admin":
        # Un vendedor no puede reasignar el responsable bajo ninguna forma
        # (incluye seller=null para liberar y seller=<su email> para apropiarse).
        if "seller" in payload:
            raise HTTPException(
                status_code=403,
                detail="Un vendedor no puede reasignar el responsable (seller) de un lead.",
            )
        # Ownership: solo sobre leads propios.
        db_lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
        if not db_lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
        if db_lead.seller != current_user.email:
            raise HTTPException(
                status_code=403,
                detail="No podés modificar un lead que no te pertenece. Los leads nuevos se toman desde 'Contactar'.",
            )
        # Whitelist de campos editables por un vendedor.
        payload = {k: v for k, v in payload.items() if k in {"status", "notes", "feedback_status"}}

    updated_lead = crud.update_lead(db, lead_id, payload)
    if not updated_lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return updated_lead

@router.put("/{lead_id}/mark-contacted")
def mark_contacted(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    """
    Toma/marca un lead como contactado, con protección contra carrera entre vendedores.

    - Admin: puede marcar cualquier lead (sin robar el `seller` si ya tiene dueño).
    - Vendedor: solo puede tomar un lead libre (sin seller) o ya propio. Si el lead
      pertenece a otro vendedor -> 403.

    Serializa la toma simultánea con `with_for_update()` (bloqueo de fila en Postgres)
    y revalida `seller`/`status` después de adquirir el lock, de modo que ante dos
    vendedores tomando el mismo lead solo uno lo reclama y el otro recibe 403.
    Idempotente: si el lead ya está CONTACTED y es del mismo vendedor no re-escribe
    `contacted_at`.
    """
    db_lead = (
        db.query(models.Lead)
        .filter(models.Lead.id == lead_id)
        .with_for_update()
        .first()
    )
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    owned_by_me = db_lead.seller == current_user.email

    if current_user.role != "admin" and db_lead.seller and not owned_by_me:
        # Ya tomado por otro vendedor (incluye al perdedor de una carrera).
        raise HTTPException(status_code=403, detail="Este lead ya fue tomado por otro vendedor.")

    # Idempotencia: ya contactado y propio -> no re-escribir contacted_at.
    if db_lead.status == models.LeadStatus.CONTACTED and owned_by_me:
        return {"status": "success", "idempotent": True}

    updates = {"status": "CONTACTED"}
    # No robar el seller si el lead ya tiene dueño (caso admin sobre lead ajeno).
    if not db_lead.seller or owned_by_me:
        updates["seller"] = current_user.email

    updated_lead = crud.update_lead(db, lead_id, updates)
    if not updated_lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"status": "success"}

@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    verify_token = os.getenv("META_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        print("Webhook verified successfully!")
        # Meta expects the raw integer hub_challenge
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    print("Received webhook event:", body)
    
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if change.get("field") == "leadgen":
                    leadgen_id = value.get("leadgen_id")
                    if leadgen_id:
                        print(f"DEBUG: Extracted leadgen_id: {leadgen_id}, llamando a Meta Graph API...")
                        access_token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
                        lead_data = await meta_api.get_lead_data(leadgen_id, access_token)
                        
                        if lead_data:
                            print(f"DEBUG: Data cruda de Meta: {lead_data}")
                            transformed = meta_api.transform_meta_lead_to_schemas(lead_data)
                            from .. import crud, schemas
                            transformed['status'] = "NEW"
                            lead_create = schemas.LeadCreate(**transformed)
                            # Verify if lead doesn't exist already to avoid dupes (basic check)
                            crud.create_lead(db=db, lead=lead_create)
                            print(f"✅ Lead {leadgen_id} guardado exitosamente.")
                        else:
                            print(f"❌ Error: Graph API no devolvió datos para auth token. ¿Token vencido o sin permisos?")
    return {"status": "ok"}

# --- Webhook Meta Lead Ads NORA (marca NORA, separado del webhook UNPO de arriba) ---

def _verify_meta_signature(app_secret: str, raw_body: bytes, signature_header: str) -> bool:
    """
    Valida la firma X-Hub-Signature-256 de Meta: HMAC-SHA256 del body crudo con el
    App Secret. Comparación en tiempo constante. No logea ni el secreto ni el body.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received = signature_header.split("=", 1)[1]
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.get("/nora/webhook")
async def verify_nora_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Verificación (handshake) del webhook de Meta Lead Ads para NORA. Usa su propio
    verify token (NORA_META_VERIFY_TOKEN), separado del de UNPO. Si el token no
    está configurado en el entorno, falla de forma controlada (503) en vez de
    validar contra un string vacío.
    """
    verify_token = os.getenv("NORA_META_VERIFY_TOKEN", "")
    if not verify_token:
        raise HTTPException(
            status_code=503,
            detail="NORA_META_VERIFY_TOKEN no está configurado en el entorno.",
        )
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, verify_token):
        print("[nora-webhook] verificación OK")
        # Meta espera el echo del hub.challenge como texto plano.
        return PlainTextResponse(content=hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/nora/webhook")
async def receive_nora_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingesta de leads de Meta Lead Ads como Prospectos NORA.

    - Valida la firma X-Hub-Signature-256 cuando META_APP_SECRET está configurado
      (si no está, en local se omite la validación de firma de forma controlada).
    - Usa NORA_META_PAGE_ACCESS_TOKEN (separado de UNPO) para pedir el detalle del
      lead a la Graph API.
    - Crea leads NORA con source FACEBOOK_NORA / INSTAGRAM_NORA (la asignación del
      vendedor NORA la hace crud.create_lead).
    - Modo test local: si el `value` del cambio trae `field_data` embebido, se usa
      directamente sin llamar a la Graph API (permite probar sin Meta real).
    - No logea tokens ni payloads con datos personales.
    """
    raw_body = await request.body()

    # 1) Validación de firma (sólo si hay App Secret configurado).
    app_secret = os.getenv("META_APP_SECRET", "")
    if app_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_meta_signature(app_secret, raw_body, signature):
            raise HTTPException(status_code=403, detail="Firma X-Hub-Signature-256 inválida")
    else:
        print("[nora-webhook] META_APP_SECRET no configurado: validación de firma omitida (modo local)")

    # 2) Parseo controlado del JSON.
    try:
        body = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload JSON inválido")

    if body.get("object") != "page":
        return {"status": "ignored", "reason": "objeto no soportado"}

    page_token = os.getenv("NORA_META_PAGE_ACCESS_TOKEN", "")
    created = 0

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            value = change.get("value", {})

            # Modo test local: field_data embebido evita llamar a la Graph API.
            if value.get("field_data") is not None:
                lead_data = {
                    "field_data": value.get("field_data"),
                    "platform": value.get("platform"),
                    "created_time": value.get("created_time"),
                    "ad_name": value.get("ad_name"),
                    "campaign_name": value.get("campaign_name"),
                }
            else:
                leadgen_id = value.get("leadgen_id")
                if not leadgen_id:
                    continue
                if not page_token:
                    # Falla controlada: sin token no se puede pedir el detalle a Meta.
                    raise HTTPException(
                        status_code=503,
                        detail="NORA_META_PAGE_ACCESS_TOKEN no está configurado en el entorno.",
                    )
                lead_data = await meta_api.get_lead_data(leadgen_id, page_token)
                if lead_data is None:
                    print(f"[nora-webhook] Graph API no devolvió datos para leadgen_id={leadgen_id}")
                    continue

            transformed = meta_api.transform_meta_lead_to_schemas(lead_data, brand="nora")
            transformed["status"] = "NEW"
            lead_create = schemas.LeadCreate(**transformed)
            crud.create_lead(db=db, lead=lead_create)
            created += 1
            print(f"[nora-webhook] prospecto NORA creado (source={transformed.get('source')})")

    return {"status": "ok", "created": created}

@router.post("/import/")
async def import_leads_excel(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Endpoint para subir y procesar archivos Excel de leads. Solo Admins.
    """
    if current_user.role not in ["admin", "vendedor"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta acción")
        
    if not file.filename.endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use .xlsx o .xlsm")
    
    content = await file.read()
    result = importer.process_excel_leads(content, file.filename, db)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result
@router.delete("/cleanup/2025")
def cleanup_old_leads(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Elimina permanentemente leads del año 2025. Solo Admins.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta acción")
    
    deleted_count = crud.delete_old_leads(db, year=2025)
    
    return {"status": "success", "message": f"Se eliminaron {deleted_count} leads del 2025."}
