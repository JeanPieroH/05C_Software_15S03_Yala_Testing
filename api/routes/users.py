from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.database import get_db
from database.models import User # Solo User es necesario para Depends
from core.security import get_current_user
from services.user_service import UserService # ¡Aquí está el cambio de importación!

router = APIRouter()

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    
    class Config:
        orm_mode = True

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    # La lógica de obtener el usuario "me" ya está en Depends(get_current_user),
    # así que aquí simplemente se retorna.
    # Si hubiera lógica adicional para "mi" perfil, iría al servicio.
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # Se mantiene para verificación de autenticación si es necesario
):
    user_service = UserService(db) # Instancia de UserService
    user = user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return user