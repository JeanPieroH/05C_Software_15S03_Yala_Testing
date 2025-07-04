from sqlalchemy.orm import Session
from typing import Optional

from database.models import User

class UserService: # Clase renombrada a UserService
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Obtiene un usuario de la base de datos por su ID.
        Retorna el objeto User si se encuentra, de lo contrario None.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        return user

    def get_current_user_profile(self, current_user: User) -> User:
        """
        Retorna el objeto del usuario actualmente autenticado.
        Esta función sirve como un simple passthrough para la dependencia de FastAPI.
        """
        return current_user