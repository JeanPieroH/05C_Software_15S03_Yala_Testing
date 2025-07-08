from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field # Importa Field para validación
from datetime import datetime

from database.database import get_db
from database.models import User 
from core.security import get_current_user
from services.account_service import AccountService 

router = APIRouter()

# --- Modelos Pydantic existentes ---
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
    description: Optional[str] 
    timestamp: datetime
    
    class Config:
        orm_mode = True

class AccountWithTransactionsResponse(BaseModel):
    account: AccountInfo
    transactions: List[TransactionInfo]

# --- Nuevo modelo Pydantic para el depósito ---
class DepositRequest(BaseModel):
    amount: float = Field(..., gt=0, description="El monto a depositar debe ser mayor que cero.")

# --- Endpoints existentes ---
@router.get("/", response_model=List[AccountInfo], summary="Obtener todas las cuentas del usuario")
async def get_user_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_service = AccountService(db)
    accounts = account_service.get_user_accounts(current_user.id)
    return accounts

@router.get("/{account_id}", response_model=AccountWithTransactionsResponse, summary="Obtener detalles de una cuenta y sus transacciones")
async def get_account_details(
    account_id: int, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    account_service = AccountService(db)
    account, transactions = account_service.get_account_details(account_id, current_user.id)
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada o no pertenece al usuario")
    
    return {"account": account, "transactions": transactions}

@router.post("/{account_id}/export", summary="Exportar estado de cuenta por correo electrónico")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        # Aquí se podría añadir un log detallado del error
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al enviar el estado de cuenta: {str(e)}")

# --- Nuevo endpoint para el depósito ---
@router.post("/{account_id}/deposit", response_model=AccountInfo, summary="Realizar un depósito en una cuenta")
async def deposit_to_account(
    account_id: int,
    deposit_request: DepositRequest, # Usa el nuevo modelo Pydantic para el cuerpo de la solicitud
    db: Session = Depends(get_db)
):
    account_service = AccountService(db)
    try:
        updated_account = account_service.deposit_to_account(account_id, deposit_request.amount)
        return updated_account # Retorna la información de la cuenta actualizada
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) # 404 si la cuenta no existe, o 400 si el monto es inválido
    except Exception as e:
        # Aquí se podría añadir un log detallado del error
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al procesar el depósito: {str(e)}")