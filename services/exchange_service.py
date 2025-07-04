from typing import Dict, Optional
from core.exchange.interface import ExchangeAPIInterface
from core.exchange.api1_adapter import ExchangeRateAPI
from core.exchange.api2_adapter import CurrencyConverterAPI

class ExchangeService:
    """Singleton para el servicio de Exchange"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExchangeService, cls).__new__(cls)
            cls._instance._primary_api = ExchangeRateAPI()
            cls._instance._fallback_api = CurrencyConverterAPI()
            cls._instance._current_api = cls._instance._primary_api
        return cls._instance
    
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtenemos el tipo de cambio de una moneda a otra, intentando primero con la API primaria y luego con la secundaria si falla"""
        try:
            return self._current_api.get_exchange_rate(from_currency, to_currency)
        except Exception:
            old_api = self._current_api
            self._current_api = self._fallback_api if self._current_api == self._primary_api else self._primary_api
            try:
                return self._current_api.get_exchange_rate(from_currency, to_currency)
            except Exception:
                self._current_api = old_api
                raise ValueError(f"Could not get exchange rate from {from_currency} to {to_currency} from any API")
    
    def switch_api(self) -> None:
        """Hacemos switch entre las APIs primaria y secundaria"""
        self._current_api = self._fallback_api if self._current_api == self._primary_api else self._primary_api
    
    def get_api_name(self) -> str:
        """Obtener el nombre de la API actual"""
        return self._current_api.__class__.__name__
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """Obtener la lista de divisas admitidas por la API actual"""
        return self._current_api.get_supported_currencies()
