from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.database import get_db
from database.models import User
from core.security import verify_password, create_access_token
from services.email_service import send_welcome_email
from config import ACCESS_TOKEN_EXPIRE_MINUTES

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
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")

    from core.security import hash_password
    hashed_password = hash_password(user_data.password)
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    try:
        send_welcome_email(new_user.email, new_user.full_name)
    except Exception as e:
        print(f"Error al enviar el correo de bienvenida: {e}")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
