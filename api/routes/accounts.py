from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database.database import get_db
from database.models import User # Solo User es necesario para Depends
from core.security import get_current_user
from services.account_service import AccountService # Importa el nuevo servicio

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
    description: Optional[str] # Cambiado a Optional para evitar errores si es None
    timestamp: datetime
    
    class Config:
        orm_mode = True

class AccountWithTransactionsResponse(BaseModel):
    account: AccountInfo
    transactions: List[TransactionInfo]

@router.get("/", response_model=List[AccountInfo])
async def get_user_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_service = AccountService(db)
    accounts = account_service.get_user_accounts(current_user.id)
    return accounts

@router.get("/{account_id}", response_model=AccountWithTransactionsResponse)
async def get_account_details(
    account_id: int, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    account_service = AccountService(db)
    account, transactions = account_service.get_account_details(account_id, current_user.id)
    
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    return {"account": account, "transactions": transactions}

@router.post("/{account_id}/export")
async def export_account_statement(
    account_id: int,
    format: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    account_service = AccountService(db)
    try:
        account_service.export_account_statement(account_id, format, current_user)
        return {"message": f"El estado de cuenta en formato {format.upper()} ha sido enviado a tu correo electrónico"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el estado de cuenta: {str(e)}")