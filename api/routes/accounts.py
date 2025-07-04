from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from pydantic import BaseModel
from datetime import datetime

from database.database import get_db
from database.models import User, Account, Currency, Transaction
from core.security import get_current_user
from services.email_service import send_account_statement

router = APIRouter()

class CurrencyInfo(BaseModel):
    id: int
    code: str
    name: str
    
    class Config:
        orm_mode = True

class AccountInfo(BaseModel):
    id: int
    currency: CurrencyInfo
    balance: float
    
    class Config:
        orm_mode = True

class TransactionInfo(BaseModel):
    id: int
    source_amount: float
    source_currency_id: int
    destination_amount: float
    destination_currency_id: int
    exchange_rate: float
    description: str = None
    timestamp: datetime
    
    class Config:
        orm_mode = True

class AccountWithTransactionsResponse(BaseModel):
    account: AccountInfo
    transactions: List[TransactionInfo]

@router.get("/", response_model=List[AccountInfo])
async def get_user_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(
        Account.user_id == current_user.id
    ).join(Currency).options(
        joinedload(Account.currency)
    ).all()
    
    return accounts

@router.get("/{account_id}", response_model=AccountWithTransactionsResponse)
async def get_account_details(
    account_id: int, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(
        Account.id == account_id, 
        Account.user_id == current_user.id
    ).join(Currency).options(
        joinedload(Account.currency)
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    transactions = db.query(Transaction).filter(
        (Transaction.source_account_id == account_id) | 
        (Transaction.destination_account_id == account_id)
    ).order_by(Transaction.timestamp.desc()).all()
    
    return {"account": account, "transactions": transactions}

@router.post("/{account_id}/export")
async def export_account_statement(
    account_id: int,
    format: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(
        Account.id == account_id, 
        Account.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        
    transactions = db.query(Transaction).filter(
        (Transaction.source_account_id == account_id) | 
        (Transaction.destination_account_id == account_id)
    ).order_by(Transaction.timestamp.desc()).all()
    
    try:
        send_account_statement(current_user.email, current_user.full_name, account, transactions, format)
        return {"message": f"El estado de cuenta en formato {format.upper()} ha sido enviado a tu correo electrónico"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el estado de cuenta: {str(e)}")
