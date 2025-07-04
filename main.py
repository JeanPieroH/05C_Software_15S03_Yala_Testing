from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os

from database.database import get_db, create_db_and_tables, init_db_data
from api.routes import auth, users, accounts, transactions
from services.exchange_service import ExchangeService

app = FastAPI(title="YALA ¿Ya la tienes?", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Cuentas"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transacciones"])

os.makedirs("data", exist_ok=True)

exchange_service = ExchangeService()

@app.on_event("startup")
async def startup():
    create_db_and_tables()
    init_db_data()

@app.get("/")
async def root():
    return {"message": "YALA está funcionando"}

@app.get("/api/exchange-rates/{from_currency}/{to_currency}")
async def get_exchange_rate(from_currency: str, to_currency: str):
    rate = exchange_service.get_exchange_rate(from_currency, to_currency)
    return {"from": from_currency, "to": to_currency, "rate": rate}

@app.get("/api/supported-currencies")
async def get_supported_currencies():
    return exchange_service.get_supported_currencies()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
