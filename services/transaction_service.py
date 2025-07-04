from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from database.models import User, Account, Transaction, Currency
from services.exchange_service import ExchangeService
from services.email_service import send_transaction_notification
from pydantic import BaseModel # Importa BaseModel para TransactionCreate

class TransactionCreate(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: float
    description: Optional[str] = None

class TransactionService:
    def __init__(self, db: Session):
        self.db = db
        self.exchange_service = ExchangeService()

    def create_new_transaction(self, transaction_data: TransactionCreate, current_user: User):
        # Validar cuenta de origen
        source_account = self.db.query(Account).filter(
            Account.id == transaction_data.source_account_id,
            Account.user_id == current_user.id
        ).first()

        if not source_account:
            raise ValueError("La cuenta de origen no existe o no pertenece al usuario")

        # Validar cuenta de destino
        destination_account = self.db.query(Account).filter(
            Account.id == transaction_data.destination_account_id
        ).first()

        if not destination_account:
            raise ValueError("La cuenta de destino no existe")
        
        # Validar balance
        if source_account.balance < transaction_data.amount:
            raise ValueError("Balance insuficiente en la cuenta de origen")

        source_currency = self.db.query(Currency).filter(Currency.id == source_account.currency_id).first()
        destination_currency = self.db.query(Currency).filter(Currency.id == destination_account.currency_id).first()

        # Calcular monto de destino y tipo de cambio
        if source_currency.code != destination_currency.code:
            exchange_rate = self.exchange_service.get_exchange_rate(source_currency.code, destination_currency.code)
            destination_amount = transaction_data.amount * exchange_rate
        else:
            exchange_rate = 1.0
            destination_amount = transaction_data.amount
        
        now = datetime.now(timezone.utc)

        # Crear nueva transacción
        new_transaction = Transaction(
            sender_id=current_user.id,
            receiver_id=destination_account.user_id,
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            source_amount=transaction_data.amount,
            source_currency_id=source_currency.id,
            destination_amount=destination_amount,
            destination_currency_id=destination_currency.id,
            exchange_rate=exchange_rate,
            description=transaction_data.description,
            timestamp=now
        )
        
        # Actualizar balances
        source_account.balance -= transaction_data.amount
        destination_account.balance += destination_amount
        
        self.db.add(new_transaction)
        self.db.commit()
        self.db.refresh(new_transaction)
        
        # Enviar notificaciones por correo
        receiver = self.db.query(User).filter(User.id == destination_account.user_id).first()
        try:
            send_transaction_notification(
                current_user.email,
                current_user.full_name, 
                new_transaction, 
                source_currency.code,
                destination_currency.code,
                is_sender=True
            )
            
            send_transaction_notification(
                receiver.email,
                receiver.full_name,
                new_transaction,
                source_currency.code,
                destination_currency.code,
                is_sender=False
            )
        except Exception as e:
            print(f"Error al enviar la notificación: {e}") # Considerar un sistema de logging más robusto
        
        return new_transaction

    def get_user_transactions(self, user_id: int):
        transactions = self.db.query(Transaction).filter(
            (Transaction.sender_id == user_id) | 
            (Transaction.receiver_id == user_id)
        ).order_by(Transaction.timestamp.desc()).all()
        
        return transactions