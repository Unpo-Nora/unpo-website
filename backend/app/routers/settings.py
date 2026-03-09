from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, models, schemas, database
from .auth import get_current_user
from passlib.context import CryptContext

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

@router.get("/{key}", response_model=schemas.Settings)
def get_setting(key: str, db: Session = Depends(database.get_db)):
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
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para editar configuraciones")
        
    # Security check for sensitive settings
    if key == "manual_exchange_rate":
        if not setting_data.password:
            raise HTTPException(status_code=400, detail="Se requiere confirmación de contraseña para cambiar la cotización")
            
        if not verify_password(setting_data.password, current_user.hashed_password):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    return crud.update_setting(db, key=key, value=setting_data.value)
