from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.database import get_db
from database.models import User # Solo User es necesario para Depends
from services.auth_service import AuthService # ¡Aquí está el cambio de importación!

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login", response_model=Token)
async def login_for_access_token(login_data: LoginRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db) # Instancia de AuthService
    user = auth_service.authenticate_user(login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token_for_user(user)
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    auth_service = AuthService(db) # Instancia de AuthService
    try:
        new_user = auth_service.register_new_user(
            user_data.username, 
            user_data.email, 
            user_data.password, 
            user_data.full_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado durante el registro: {e}")
    
    access_token = auth_service.create_access_token_for_user(new_user)
    
    return {"access_token": access_token, "token_type": "bearer"}