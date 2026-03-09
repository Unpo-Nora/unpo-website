from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import database, crud, schemas_auth
from ..utils import auth
from jose import JWTError, jwt
import os

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey_change_me_in_production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

@router.post("/login", response_model=schemas_auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas_auth.UserResponse)
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user

@router.get("/setup-admin")
async def setup_initial_admin(db: Session = Depends(get_db)):
    from .. import models
    # Check if any user exists
    user_count = db.query(models.User).count()
    if user_count > 0:
        return {"status": "error", "message": "Admin already exists"}
    
    # Create default admin
    crud.create_user(db, {
        "email": "admin@unpo.com.ar",
        "password": "admin",
        "full_name": "Administrador Principal",
        "role": "admin"
    })
    return {"status": "success", "message": "Initial admin created. Email: admin@unpo.com.ar / Password: admin"}
