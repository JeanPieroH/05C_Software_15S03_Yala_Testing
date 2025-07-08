from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    accounts = relationship("Account", back_populates="user")
    sent_transactions = relationship("Transaction", foreign_keys="Transaction.sender_id", back_populates="sender")
    received_transactions = relationship("Transaction", foreign_keys="Transaction.receiver_id", back_populates="receiver")

class Currency(Base):
    __tablename__ = "currencies"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), unique=True, index=True)
    name = Column(String)
    
    accounts = relationship("Account", back_populates="currency")

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    currency_id = Column(Integer, ForeignKey("currencies.id"))
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="accounts")
    currency = relationship("Currency", back_populates="accounts")
    transactions_out = relationship("Transaction", foreign_keys="Transaction.source_account_id", back_populates="source_account")
    transactions_in = relationship("Transaction", foreign_keys="Transaction.destination_account_id", back_populates="destination_account")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    
    source_account_id = Column(Integer, ForeignKey("accounts.id"))
    destination_account_id = Column(Integer, ForeignKey("accounts.id"))

    source_amount = Column(Float)
    source_currency_id = Column(Integer, ForeignKey("currencies.id"))
    destination_amount = Column(Float)
    destination_currency_id = Column(Integer, ForeignKey("currencies.id"))
    exchange_rate = Column(Float)
    
    description = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_transactions")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_transactions")
    source_account = relationship("Account", foreign_keys=[source_account_id], back_populates="transactions_out")
    destination_account = relationship("Account", foreign_keys=[destination_account_id], back_populates="transactions_in")
    source_currency = relationship("Currency", foreign_keys=[source_currency_id])
    destination_currency = relationship("Currency", foreign_keys=[destination_currency_id])