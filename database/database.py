from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt
import os

from config import DATABASE_URL, DEFAULT_ACCOUNTS
from database.models import Base, User, Account, Transaction, Currency

os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
    
def init_db_data():
    """Inicializamos la BD con datos por defecto"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        if db.query(User).count() > 0:
            return
            
        from config import SUPPORTED_CURRENCIES
        for code, name in SUPPORTED_CURRENCIES.items():
            currency = Currency(code=code, name=name)
            db.add(currency)
        
        hashed_password = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        user_x = User(
            username="cristhian",
            email="cpaz@prueba.com",
            hashed_password=hashed_password,
            full_name="Cristhian Paz"
        )
        db.add(user_x)
        db.flush()
        
        user_y = User(
            username="Y",
            email="y@example.com",
            hashed_password=hashed_password,
            full_name="User Y"
        )
        db.add(user_y)
        db.flush()
        
        for username, balances in DEFAULT_ACCOUNTS.items():
            user = db.query(User).filter(User.username == username).first()
            
            for currency_code, balance in balances.items():
                currency = db.query(Currency).filter(Currency.code == currency_code).first()
                account = Account(
                    user_id=user.id,
                    currency_id=currency.id,
                    balance=balance
                )
                db.add(account)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error initializing database: {e}")
    finally:
        db.close()
