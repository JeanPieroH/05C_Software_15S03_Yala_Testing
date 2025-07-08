from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from database.models import User, Account, Transaction, Currency
from services.exchange_service import ExchangeService
from services.email_service import send_transaction_notification

import time


# MockExchangeService para simular tasas de cambio
class MockExchangeService:
    MOCKED_RATES = {
        ("PEN", "USD"): 0.27,
        ("USD", "PEN"): 3.70,
        ("EUR", "USD"): 1.08,
        ("USD", "EUR"): 0.92,
        ("PEN", "EUR"): 0.25,
        ("EUR", "PEN"): 4.00,
        ("GBP", "USD"): 1.25,
        ("JPY", "USD"): 0.0068,
        ("CAD", "USD"): 0.73,
        ("AUD", "USD"): 0.66,
    }

    def get_exchange_rate(self, from_currency_code: str, to_currency_code: str) -> float:
        time.sleep(0.5)
        rate = self.MOCKED_RATES.get((from_currency_code, to_currency_code))
        if rate is None:
            inverse_rate = self.MOCKED_RATES.get((to_currency_code, from_currency_code))
            if inverse_rate:
                return 1 / inverse_rate
            raise ValueError(f"No hay tasa de cambio mockeada disponible para {from_currency_code} a {to_currency_code}")
        return rate


class TransactionCreate(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: float
    description: Optional[str] = None


class TransactionService:
    def __init__(self, db: Session, use_mocked_exchange: bool):
        self.db = db
        self.use_mocked_exchange = use_mocked_exchange
        self.exchange_service = (
            MockExchangeService() if use_mocked_exchange else ExchangeService()
        )

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

        source_currency = self.db.query(Currency).filter(
            Currency.id == source_account.currency_id
        ).first()
        destination_currency = self.db.query(Currency).filter(
            Currency.id == destination_account.currency_id
        ).first()

        # Calcular monto de destino y tipo de cambio
        if source_currency.code != destination_currency.code:
            exchange_rate = self.exchange_service.get_exchange_rate(
                source_currency.code, destination_currency.code
            )
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

        # Enviar notificaciones por correo (solo si se usa servicio real)
        if not self.use_mocked_exchange:
            try:
                receiver = self.db.query(User).filter(
                    User.id == destination_account.user_id
                ).first()

                send_transaction_notification(
                    current_user.email,
                    current_user.full_name,
                    new_transaction,
                    source_currency.code,
                    destination_currency.code,
                    is_sender=True
                )

            except Exception as e:
                print(f"Error al enviar la notificación: {e}")  # Usar logging en producción

        return new_transaction

    def get_user_transactions(self, user_id: int):
        transactions = self.db.query(Transaction).filter(
            (Transaction.sender_id == user_id) |
            (Transaction.receiver_id == user_id)
        ).order_by(Transaction.timestamp.desc()).all()

        return transactions
