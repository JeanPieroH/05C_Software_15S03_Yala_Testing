import requests
from typing import Dict
from .interface import ExchangeAPIInterface
from config import EXCHANGE_API1_KEY, SUPPORTED_CURRENCIES


class ExchangeRateAPI(ExchangeAPIInterface):
    """Adaptador para ExchangeRate-API"""
    
    def __init__(self):
        self.base_url = "https://v6.exchangerate-api.com/v6"
        self.api_key = EXCHANGE_API1_KEY
        self.cache = {}
        
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtener el tipo de cambio de una moneda a otra utilizando ExchangeRate-API"""
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        url = f"{self.base_url}/{self.api_key}/pair/{from_currency}/{to_currency}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data["result"] == "success":
                rate = data["conversion_rate"]
                self.cache[cache_key] = rate
                return rate
        
        raise ValueError(f"Could not get exchange rate from {from_currency} to {to_currency}")
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """Obtener la lista de divisas admitidas"""
        return SUPPORTED_CURRENCIES
    
    def is_currency_supported(self, currency_code: str) -> bool:
        """Comprobar si la API acepeeta esta divisa"""
        return currency_code in SUPPORTED_CURRENCIES
