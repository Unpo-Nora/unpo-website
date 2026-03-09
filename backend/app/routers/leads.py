from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from .. import crud, models, schemas, database, meta_api
from ..utils import importer
import urllib.parse
import os

router = APIRouter(
    prefix="/leads",
    tags=["leads"]
)

get_db = database.get_db

@router.post("/", response_model=schemas.LeadResponse)
def create_lead(lead: schemas.LeadCreate, db: Session = Depends(get_db)):
    created_lead = crud.create_lead(db=db, lead=lead)
    
    # Simple Logic to generate a customized WhatsApp link
    base_url = "https://wa.me/5491131488378"
    interest = lead.product_interest or lead.category_interest or "productos"
    message = f"Hola, soy {lead.full_name}. Estoy interesado en {interest}."
    encoded_message = urllib.parse.quote(message)
    whatsapp_link = f"{base_url}?text={encoded_message}"
    
    # In a real scenario, we might return this link or trigger an automated message via an external API
    # For now, we'll just log it or include it in a hypothetical response (if we changed the schema)
    
    return created_lead

from .auth import get_current_user

@router.get("/", response_model=List[schemas.LeadResponse])
def read_leads(
    skip: int = 0, 
    limit: int = 1000, 
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print(f"DEBUG: User {current_user.email} with role {current_user.role} requesting leads. status={status}")
    if current_user.role == "admin":
        results = crud.get_leads(db, skip=skip, limit=limit, status=status)
        print(f"DEBUG: Admin results count: {len(results)}")
        return results
    
    # For sellers:
    # 1. If searching for NEW, show all NEW.
    # 2. If searching for CONTACTED, show only OWNED.
    # 3. If no status (initial fetch), return all NEW + OWNED CONTACTED.
    
    if status == "NEW":
        return crud.get_leads(db, skip=skip, limit=limit, status="NEW")
    elif status == "CONTACTED":
        return crud.get_leads(db, skip=skip, limit=limit, status="CONTACTED", seller=current_user.email)
    elif status == "CLIENT":
        return crud.get_leads(db, skip=skip, limit=limit, status="CLIENT", seller=current_user.email)
    elif status:
        return crud.get_leads(db, skip=skip, limit=limit, status=status, seller=current_user.email)
    else:
        # Prioritize owned contacted leads
        owned_contacted = crud.get_leads(db, limit=limit, status="CONTACTED", seller=current_user.email)
        remaining_limit = limit - len(owned_contacted)
        all_new = []
        if remaining_limit > 0:
            all_new = crud.get_leads(db, limit=remaining_limit, status="NEW")
        return owned_contacted + all_new

@router.patch("/{lead_id}", response_model=schemas.LeadResponse)
def update_lead(
    lead_id: int, 
    lead_update: schemas.LeadUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Here we could add logic to prevent a seller from updating a lead owned by someone else
    # But for now, we'll allow any authenticated staff to update (basic security)
    updated_lead = crud.update_lead(db, lead_id, lead_update.model_dump(exclude_unset=True))
    if not updated_lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return updated_lead

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
                            lead_create = schemas.LeadCreate(**transformed)
                            # Verify if lead doesn't exist already to avoid dupes (basic check)
                            crud.create_lead(db=db, lead=lead_create)
                            print(f"✅ Lead {leadgen_id} guardado exitosamente.")
                        else:
                            print(f"❌ Error: Graph API no devolvió datos para auth token. ¿Token vencido o sin permisos?")
    return {"status": "ok"}

@router.post("/import/")
async def import_leads_excel(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Endpoint para subir y procesar archivos Excel de leads. Solo Admins.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta acción")
        
    if not file.filename.endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use .xlsx o .xlsm")
    
    content = await file.read()
    result = importer.process_excel_leads(content, file.filename, db)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result
