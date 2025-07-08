from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime

from database.models import User, Account, Currency, Transaction
from services.email_service import send_account_statement # Asegúrate de que este servicio sea accesible

class AccountService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_accounts(self, user_id: int):
        accounts = self.db.query(Account).filter(
            Account.user_id == user_id
        ).join(Currency).options(
            joinedload(Account.currency)
        ).all()
        return accounts

    def get_account_details(self, account_id: int, user_id: int):
        account = self.db.query(Account).filter(
            Account.id == account_id, 
            Account.user_id == user_id
        ).join(Currency).options(
            joinedload(Account.currency)
        ).first()
        
        if not account:
            return None, None # Indica que la cuenta no fue encontrada
        
        transactions = self.db.query(Transaction).filter(
            (Transaction.source_account_id == account_id) | 
            (Transaction.destination_account_id == account_id)
        ).order_by(Transaction.timestamp.desc()).all()
        
        return account, transactions

    def export_account_statement(self, account_id: int, format: str, current_user: User):
        account = self.db.query(Account).filter(
            Account.id == account_id, 
            Account.user_id == current_user.id
        ).first()
        
        if not account:
            raise ValueError("Cuenta no encontrada")
            
        transactions = self.db.query(Transaction).filter(
            (Transaction.source_account_id == account_id) | 
            (Transaction.destination_account_id == account_id)
        ).order_by(Transaction.timestamp.desc()).all()
        
        send_account_statement(current_user.email, current_user.full_name, account, transactions, format)
        return True # Indica que el envío fue exitoso

    # --- Nuevo método para realizar un depósito ---
    def deposit_to_account(self, account_id: int, amount: float):
        """
        Realiza un depósito a una cuenta específica.
        """
        if amount <= 0:
            raise ValueError("El monto del depósito debe ser positivo.")

        account = self.db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise ValueError("Cuenta no encontrada para el depósito.")
        
        # Actualizar balance
        account.balance += amount
        
        # Opcional: registrar el depósito como una transacción especial
        # Esto depende de cómo quieras modelar los depósitos en tu sistema.
        # Podrías crear un tipo de transacción 'DEPOSIT' o no registrarlo
        # como una transacción regular entre cuentas si es un ingreso externo.
        # Por simplicidad, aquí solo actualizamos el balance.
        
        self.db.add(account) # Asegurarse de que los cambios sean seguidos
        self.db.commit()
        self.db.refresh(account) # Refrescar para obtener el balance actualizado
        
        return account # Retorna la cuenta actualizada