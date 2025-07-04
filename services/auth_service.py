from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from database.models import User
from core.security import verify_password, create_access_token, hash_password
from services.email_service import send_welcome_email
from config import ACCESS_TOKEN_EXPIRE_MINUTES # Asegúrate de que esto sea accesible

class AuthService: # Nombre de la clase cambiado a AuthService
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token_for_user(self, user: User) -> str:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        return access_token

    def register_new_user(self, username: str, email: str, password: str, full_name: str) -> User:
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("El correo electrónico ya está registrado")

        hashed_password = hash_password(password)
        
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name
        )
        
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        
        try:
            send_welcome_email(new_user.email, new_user.full_name)
        except Exception as e:
            print(f"Error al enviar el correo de bienvenida: {e}") # Considera un sistema de logging más robusto
        
        return new_user