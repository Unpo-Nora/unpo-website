from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, models, schemas, database
from .auth import get_current_user
from ..dependencies.permissions import require_roles
from ..utils.auth import verify_password

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)

@router.get("/capital_ivas/list", response_model=List[schemas.CapitalIva])
def get_all_capital_ivas(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    return crud.get_capital_ivas(db)

@router.post("/capital_ivas/", response_model=schemas.CapitalIva)
def create_capital_iva(
    iva: schemas.CapitalIvaCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    if iva.amount <= 0:
        raise HTTPException(status_code=400, detail="Monto no puede ser cero o negativo")
    return crud.create_capital_iva(db, iva, current_user.email)

@router.delete("/capital_ivas/{iva_id}")
def delete_capital_iva(
    iva_id: int, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    success = crud.delete_capital_iva(db, iva_id)
    if not success:
        raise HTTPException(status_code=404, detail="IVA no encontrado")
    return {"status": "ok"}

# Claves legibles por cualquier usuario autenticado (staff); el resto es solo admin.
STAFF_READABLE_SETTINGS = {"manual_exchange_rate"}

@router.get("/{key}", response_model=schemas.Settings)
def get_setting(
    key: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if key not in STAFF_READABLE_SETTINGS and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para leer esta configuración")
    setting = crud.get_setting(db, key=key)
    if not setting:
        # Provide sensible default if missing
        if key == "manual_exchange_rate":
            return schemas.Settings(key=key, value="1450")
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting

@router.put("/{key}", response_model=schemas.Settings)
def update_setting(
    key: str, 
    setting_data: schemas.SettingsUpdate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    # Security check for sensitive settings
    if key == "manual_exchange_rate":
        if not setting_data.password:
            raise HTTPException(status_code=400, detail="Se requiere confirmación de contraseña para cambiar la cotización")
            
        if not verify_password(setting_data.password, current_user.hashed_password):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    return crud.update_setting(db, key=key, value=setting_data.value)
