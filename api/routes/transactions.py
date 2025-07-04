from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database.database import get_db
from database.models import User # Solo User es necesario para Depends
from core.security import get_current_user
from services.transaction_service import TransactionService, TransactionCreate # Importa el nuevo servicio y el BaseModel

router = APIRouter()

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
    transaction_service = TransactionService(db)
    try:
        new_transaction = transaction_service.create_new_transaction(transaction_data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado: {e}")

    # Construir la respuesta de TransactionResponse
    transaction_response = TransactionResponse(
        id=new_transaction.id,
        source_amount=new_transaction.source_amount,
        source_currency_id=new_transaction.source_currency_id,
        destination_amount=new_transaction.destination_amount,
        destination_currency_id=new_transaction.destination_currency_id,
        exchange_rate=new_transaction.exchange_rate,
        description=new_transaction.description,
        timestamp=new_transaction.timestamp # datetime ya es un tipo compatible
    )
    return transaction_response


@router.get("/", response_model=List[TransactionResponse])
async def get_user_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction_service = TransactionService(db)
    transactions = transaction_service.get_user_transactions(current_user.id)
    return transactions