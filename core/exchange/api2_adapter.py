import requests
from typing import Dict
from .interface import ExchangeAPIInterface
from config import EXCHANGE_API2_KEY, SUPPORTED_CURRENCIES

class CurrencyConverterAPI(ExchangeAPIInterface):
    
    def __init__(self):
        self.base_url = "https://free.currconv.com/api/v7"
        self.api_key = EXCHANGE_API2_KEY
        self.cache = {}
        
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtener el tipo de cambio de una moneda a otra utilizando CurrencyConverter API"""
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        query = f"{from_currency}_{to_currency}"
        url = f"{self.base_url}/convert?q={query}&compact=ultra&apiKey={self.api_key}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if query in data:
                rate = data[query]
                self.cache[cache_key] = rate
                return rate
        
        raise ValueError(f"Could not get exchange rate from {from_currency} to {to_currency}")
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """Obtener la lista de divisas admitidas"""
        return SUPPORTED_CURRENCIES
    
    def is_currency_supported(self, currency_code: str) -> bool:
        """Comprobar si la API acepeeta esta divisa"""
        return currency_code in SUPPORTED_CURRENCIES
