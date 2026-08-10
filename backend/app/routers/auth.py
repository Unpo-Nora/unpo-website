from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import database, crud, schemas_auth
from ..database import get_db
from ..utils import auth
from datetime import timedelta
from jose import JWTError, jwt

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    """Usuario autenticado o None (para endpoints con respuesta pública reducida)."""
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None

@router.post("/login", response_model=schemas_auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Determinar expiración según el rol
    if user.role in ["admin", "vendedor"]:
        expires_delta = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES_STAFF)
    else:
        expires_delta = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    access_token = auth.create_access_token(
        data={"sub": user.email}, 
        expires_delta=expires_delta
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas_auth.UserResponse)
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user

# NOTA DE SEGURIDAD (Etapa 0A): se eliminaron los endpoints HTTP sin autenticación
# `GET /auth/reset-nico`, `GET /auth/fix-roles` y `GET /auth/setup-admin`. Permitían,
# de forma anónima, resetear contraseñas, mutar roles y crear un admin por defecto.
# Ya no se registran como rutas (responden 404). El mantenimiento de usuarios, cuando
# hace falta, se ejecuta manualmente con los scripts de `backend/scripts/maintenance/`,
# fuera de la API pública.
