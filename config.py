import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'app.db')}"

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_password")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Currency Exchange <your_email@gmail.com>")

EXCHANGE_API1_KEY = os.getenv("EXCHANGE_API1_KEY", "your-api1-key")
EXCHANGE_API2_KEY = os.getenv("EXCHANGE_API2_KEY", "your-api2-key")

SUPPORTED_CURRENCIES = {
    "PEN": "Sol Peruano",
    "USD": "Dolar Estadounidense",
    "EUR": "Euro",
    "GBP": "Libra Esterlina",
    "JPY": "Yen Japonés",
    "CAD": "Dolar Canadiense",
    "AUD": "Dolar Australiano",
}

DEFAULT_ACCOUNTS = {
    "cristhian": {"PEN": 100, "USD": 200},
    "Y": {"PEN": 50, "USD": 100}
}
