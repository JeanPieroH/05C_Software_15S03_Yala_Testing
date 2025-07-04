from abc import ABC, abstractmethod
from typing import Dict, List

class ExchangeAPIInterface(ABC):
    """Interfaz para las API de ExchangeRate"""
    
    @abstractmethod
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtener el tipo de cambio de una moneda a otra"""
        pass
    
    @abstractmethod
    def get_supported_currencies(self) -> Dict[str, str]:
        """Obtener la lista de divisas admitidas"""
        pass
    
    @abstractmethod
    def is_currency_supported(self, currency_code: str) -> bool:
        """Comprobar si la API acepeeta esta divisa"""
        pass
