import pytest
from unittest.mock import MagicMock
from services.exchange_service import ExchangeService
from core.exchange.api1_adapter import ExchangeRateAPI
from core.exchange.api2_adapter import CurrencyConverterAPI

@pytest.fixture
def exchange_service():
    # Reset singleton instance for each test
    ExchangeService._instance = None
    service = ExchangeService()
    # Mock the API instances
    service._primary_api = MagicMock(spec=ExchangeRateAPI)
    service._fallback_api = MagicMock(spec=CurrencyConverterAPI)
    service._current_api = service._primary_api
    return service

def test_get_exchange_rate_primary_api_success(exchange_service):
    exchange_service._primary_api.get_exchange_rate.return_value = 0.85
    rate = exchange_service.get_exchange_rate("USD", "EUR")
    assert rate == 0.85
    exchange_service._primary_api.get_exchange_rate.assert_called_once_with("USD", "EUR")
    exchange_service._fallback_api.get_exchange_rate.assert_not_called()

def test_get_exchange_rate_primary_api_fails_fallback_succeeds(exchange_service):
    exchange_service._primary_api.get_exchange_rate.side_effect = Exception("API Error")
    exchange_service._fallback_api.get_exchange_rate.return_value = 0.88
    rate = exchange_service.get_exchange_rate("USD", "EUR")
    assert rate == 0.88
    exchange_service._primary_api.get_exchange_rate.assert_called_once_with("USD", "EUR")
    exchange_service._fallback_api.get_exchange_rate.assert_called_once_with("USD", "EUR")
    assert exchange_service._current_api == exchange_service._fallback_api

def test_get_exchange_rate_both_apis_fail(exchange_service):
    exchange_service._primary_api.get_exchange_rate.side_effect = Exception("Primary API Error")
    exchange_service._fallback_api.get_exchange_rate.side_effect = Exception("Fallback API Error")

    with pytest.raises(ValueError, match="Could not get exchange rate from USD to EUR from any API"):
        exchange_service.get_exchange_rate("USD", "EUR")

    exchange_service._primary_api.get_exchange_rate.assert_called_once_with("USD", "EUR")
    exchange_service._fallback_api.get_exchange_rate.assert_called_once_with("USD", "EUR")
    # Ensure current_api is reverted to the original one if fallback also fails
    assert exchange_service._current_api == exchange_service._primary_api


def test_switch_api(exchange_service):
    assert exchange_service._current_api == exchange_service._primary_api
    exchange_service.switch_api()
    assert exchange_service._current_api == exchange_service._fallback_api
    exchange_service.switch_api()
    assert exchange_service._current_api == exchange_service._primary_api

def test_get_api_name(exchange_service):
    exchange_service._current_api.__class__.__name__ = "MockPrimaryAPI"
    assert exchange_service.get_api_name() == "MockPrimaryAPI"
    exchange_service.switch_api()
    exchange_service._current_api.__class__.__name__ = "MockFallbackAPI"
    assert exchange_service.get_api_name() == "MockFallbackAPI"

def test_get_supported_currencies(exchange_service):
    expected_currencies = {"USD": "United States Dollar", "EUR": "Euro"}
    exchange_service._primary_api.get_supported_currencies.return_value = expected_currencies

    currencies = exchange_service.get_supported_currencies()
    assert currencies == expected_currencies
    exchange_service._primary_api.get_supported_currencies.assert_called_once()

    exchange_service.switch_api()
    expected_currencies_fallback = {"GBP": "British Pound"}
    exchange_service._fallback_api.get_supported_currencies.return_value = expected_currencies_fallback

    currencies = exchange_service.get_supported_currencies()
    assert currencies == expected_currencies_fallback
    exchange_service._fallback_api.get_supported_currencies.assert_called_once()

def test_singleton_behavior():
    service1 = ExchangeService()
    service2 = ExchangeService()
    assert service1 is service2

    # Modify service1's API and check if service2 reflects the change
    service1._primary_api = MagicMock()
    service1._fallback_api = MagicMock()
    service1._current_api = service1._fallback_api

    assert service2._current_api == service1._fallback_api

    # Reset for other tests
    ExchangeService._instance = None

def test_get_exchange_rate_fallback_api_initially_current_and_fails_primary_succeeds(exchange_service):
    # Set fallback as current initially
    exchange_service._current_api = exchange_service._fallback_api

    exchange_service._fallback_api.get_exchange_rate.side_effect = Exception("Fallback API Error")
    exchange_service._primary_api.get_exchange_rate.return_value = 0.90

    rate = exchange_service.get_exchange_rate("USD", "GBP")
    assert rate == 0.90
    exchange_service._fallback_api.get_exchange_rate.assert_called_once_with("USD", "GBP")
    exchange_service._primary_api.get_exchange_rate.assert_called_once_with("USD", "GBP")
    assert exchange_service._current_api == exchange_service._primary_api

def test_get_exchange_rate_fallback_api_initially_current_and_both_fail(exchange_service):
    # Set fallback as current initially
    exchange_service._current_api = exchange_service._fallback_api

    exchange_service._fallback_api.get_exchange_rate.side_effect = Exception("Fallback API Error")
    exchange_service._primary_api.get_exchange_rate.side_effect = Exception("Primary API Error")

    with pytest.raises(ValueError, match="Could not get exchange rate from USD to GBP from any API"):
        exchange_service.get_exchange_rate("USD", "GBP")

    exchange_service._fallback_api.get_exchange_rate.assert_called_once_with("USD", "GBP")
    exchange_service._primary_api.get_exchange_rate.assert_called_once_with("USD", "GBP")
    # Ensure current_api is reverted to the original one (fallback in this case) if the other also fails
    assert exchange_service._current_api == exchange_service._fallback_api
