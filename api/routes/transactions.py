from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from database.database import get_db
from database.models import User, Account, Transaction, Currency
from core.security import get_current_user
from services.exchange_service import ExchangeService
from services.email_service import send_transaction_notification

router = APIRouter()

class TransactionCreate(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: float
    description: Optional[str] = None

class TransactionResponse(BaseModel):
    id: int
    source_amount: float
    source_currency_id: int
    destination_amount: float
    destination_currency_id: int
    exchange_rate: float
    description: Optional[str]
    timestamp: Optional[datetime]
    
    class Config:
        orm_mode = True

@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: TransactionCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    source_account = db.query(Account).filter(
        Account.id == transaction_data.source_account_id,
        Account.user_id == current_user.id
    ).first()
    
    if not source_account:
        raise HTTPException(status_code=404, detail="La cuenta de origen no existe o no pertenece al usuario")
    
    destination_account = db.query(Account).filter(
        Account.id == transaction_data.destination_account_id
    ).first()
    
    if not destination_account:
        raise HTTPException(status_code=404, detail="La cuenta de destino no existe")
    
    if source_account.balance < transaction_data.amount:
        raise HTTPException(status_code=400, detail="Balance insuficiente en la cuenta de origen")
    
    source_currency = db.query(Currency).filter(Currency.id == source_account.currency_id).first()
    destination_currency = db.query(Currency).filter(Currency.id == destination_account.currency_id).first()
    
    exchange_service = ExchangeService()
    if source_currency.code != destination_currency.code:
        exchange_rate = exchange_service.get_exchange_rate(source_currency.code, destination_currency.code)
        destination_amount = transaction_data.amount * exchange_rate
    else:
        exchange_rate = 1.0
        destination_amount = transaction_data.amount
    
    now = datetime.now(timezone.utc)

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
    
    source_account.balance -= transaction_data.amount
    destination_account.balance += destination_amount
    
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    
    receiver = db.query(User).filter(User.id == destination_account.user_id).first()
    
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
        print(f"Error el enviar la notificacion: {e}")

    transaction_response = TransactionResponse(
    id=new_transaction.id,
    source_amount=new_transaction.source_amount,
    source_currency_id=new_transaction.source_currency_id,
    destination_amount=new_transaction.destination_amount,
    destination_currency_id=new_transaction.destination_currency_id,
    exchange_rate=new_transaction.exchange_rate,
    description=new_transaction.description,
    timestamp=new_transaction.timestamp.isoformat() if new_transaction.timestamp else None
)

    return transaction_response


@router.get("/", response_model=List[TransactionResponse])
async def get_user_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transactions = db.query(Transaction).filter(
        (Transaction.sender_id == current_user.id) | 
        (Transaction.receiver_id == current_user.id)
    ).order_by(Transaction.timestamp.desc()).all()
    
    return transactions
