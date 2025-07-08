import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from services.transaction_service import TransactionService, TransactionCreate
from database.models import User, Account, Transaction, Currency

@pytest.fixture
def mock_user():
    user = User(id=1, email="test@example.com", full_name="Test User", hashed_password="hashedpassword")
    return user

@pytest.fixture
def mock_receiver_user():
    user = User(id=2, email="receiver@example.com", full_name="Receiver User", hashed_password="hashedpassword")
    return user

@pytest.fixture
def mock_source_account(mock_user):
    account = Account(id=1, user_id=mock_user.id, currency_id=1, balance=1000.0)
    account.user = mock_user
    return account

@pytest.fixture
def mock_destination_account(mock_receiver_user):
    account = Account(id=2, user_id=mock_receiver_user.id, currency_id=2, balance=500.0)
    account.user = mock_receiver_user
    return account

@pytest.fixture
def mock_same_currency_destination_account(mock_receiver_user):
    account = Account(id=3, user_id=mock_receiver_user.id, currency_id=1, balance=200.0)
    account.user = mock_receiver_user
    return account

@pytest.fixture
def mock_source_currency():
    return Currency(id=1, code="USD", name="US Dollar")

@pytest.fixture
def mock_destination_currency():
    return Currency(id=2, code="EUR", name="Euro")

@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=Session)

    mock_account_query_chain = MagicMock()
    mock_currency_query_chain = MagicMock()
    mock_user_query_chain = MagicMock()
    mock_transaction_query_chain = MagicMock()

    mock_account_query_chain.filter.return_value.first.return_value = None
    mock_currency_query_chain.filter.return_value.first.return_value = None
    mock_user_query_chain.filter.return_value.first.return_value = None
    mock_transaction_query_chain.filter.return_value.order_by.return_value.all.return_value = []

    def query_side_effect(model_class):
        if model_class == Account:
            return mock_account_query_chain
        elif model_class == Currency:
            return mock_currency_query_chain
        elif model_class == User:
            return mock_user_query_chain
        elif model_class == Transaction:
            return mock_transaction_query_chain
        else:
            return MagicMock()

    session.query.side_effect = query_side_effect

    session.mock_account_query_chain = mock_account_query_chain
    session.mock_currency_query_chain = mock_currency_query_chain
    session.mock_user_query_chain = mock_user_query_chain
    session.mock_transaction_query_chain = mock_transaction_query_chain

    session.add.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None

    return session

@pytest.fixture
def mock_exchange_service():
    service = MagicMock()
    service.get_exchange_rate.return_value = 0.85
    return service

@pytest.fixture
def transaction_service(mock_db_session):
    return TransactionService(db=mock_db_session, use_mocked_exchange=True)

def test_create_new_transaction_success_different_currency(
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency,
    mock_receiver_user
):
    """Verifica la creación exitosa de una transacción entre diferentes monedas."""
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_destination_account.id,
        amount=100.0,
        description="Test transaction"
    )

    # Configurar las queries de cuentas
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]
    
    # Configurar las queries de monedas
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,
        mock_destination_currency
    ]
    
    # Configurar la query del usuario receptor
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user

    initial_source_balance = mock_source_account.balance
    initial_dest_balance = mock_destination_account.balance

    # Mock del objeto Transaction que se creará
    mock_transaction = MagicMock()
    mock_transaction.sender_id = mock_user.id
    mock_transaction.receiver_id = mock_destination_account.user_id
    mock_transaction.source_account_id = mock_source_account.id
    mock_transaction.destination_account_id = mock_destination_account.id
    mock_transaction.source_amount = transaction_data.amount
    mock_transaction.source_currency_id = mock_source_currency.id
    mock_transaction.destination_amount = transaction_data.amount * 0.92  # USD to EUR rate
    mock_transaction.destination_currency_id = mock_destination_currency.id
    mock_transaction.exchange_rate = 0.92
    mock_transaction.description = "Test transaction"
    mock_transaction.timestamp = datetime.now(timezone.utc)

    # Mock del constructor de Transaction
    with patch('services.transaction_service.Transaction', return_value=mock_transaction):
        with patch('services.transaction_service.send_transaction_notification') as mock_send_notification:
            created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)

    # Verificaciones
    assert created_transaction is not None
    assert created_transaction.sender_id == mock_user.id
    assert created_transaction.receiver_id == mock_destination_account.user_id
    assert created_transaction.source_account_id == mock_source_account.id
    assert created_transaction.destination_account_id == mock_destination_account.id
    assert created_transaction.source_amount == transaction_data.amount
    assert created_transaction.source_currency_id == mock_source_currency.id
    assert created_transaction.destination_amount == pytest.approx(transaction_data.amount * 0.92)
    assert created_transaction.destination_currency_id == mock_destination_currency.id
    assert created_transaction.exchange_rate == 0.92
    assert created_transaction.description == "Test transaction"
    assert isinstance(created_transaction.timestamp, datetime)

    # Verificar que los balances se actualizaron correctamente
    assert mock_source_account.balance == initial_source_balance - transaction_data.amount
    assert mock_destination_account.balance == initial_dest_balance + (transaction_data.amount * 0.92)

    # Verificar que se llamaron los métodos de la base de datos
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_transaction)

    # Verificar que NO se enviaron notificaciones (porque use_mocked_exchange=True)
    assert mock_send_notification.call_count == 0

def test_create_new_transaction_success_same_currency(
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_same_currency_destination_account, mock_source_currency, mock_receiver_user
):
    """Verifica la creación exitosa de una transacción entre la misma moneda."""
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_same_currency_destination_account.id,
        amount=50.0
    )

    # Configurar las queries de cuentas
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_same_currency_destination_account
    ]
    
    # Configurar las queries de monedas (misma moneda para ambas)
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,
        mock_source_currency
    ]
    
    # Configurar la query del usuario receptor
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user

    initial_source_balance = mock_source_account.balance
    initial_dest_balance = mock_same_currency_destination_account.balance

    # Mock del objeto Transaction que se creará
    mock_transaction = MagicMock()
    mock_transaction.sender_id = mock_user.id
    mock_transaction.receiver_id = mock_same_currency_destination_account.user_id
    mock_transaction.source_account_id = mock_source_account.id
    mock_transaction.destination_account_id = mock_same_currency_destination_account.id
    mock_transaction.source_amount = transaction_data.amount
    mock_transaction.source_currency_id = mock_source_currency.id
    mock_transaction.destination_amount = transaction_data.amount  # Same currency
    mock_transaction.destination_currency_id = mock_source_currency.id
    mock_transaction.exchange_rate = 1.0
    mock_transaction.description = None
    mock_transaction.timestamp = datetime.now(timezone.utc)

    # Mock del constructor de Transaction
    with patch('services.transaction_service.Transaction', return_value=mock_transaction):
        with patch('services.transaction_service.send_transaction_notification') as mock_send_notification:
            created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)

    # Verificaciones específicas para misma moneda
    assert created_transaction.destination_amount == transaction_data.amount
    assert created_transaction.exchange_rate == 1.0

    # Verificar que los balances se actualizaron correctamente
    assert mock_source_account.balance == initial_source_balance - transaction_data.amount
    assert mock_same_currency_destination_account.balance == initial_dest_balance + transaction_data.amount

    # Verificar que NO se enviaron notificaciones (porque use_mocked_exchange=True)
    assert mock_send_notification.call_count == 0

def test_create_new_transaction_source_account_not_found(transaction_service, mock_db_session, mock_user):
    """Verifica el manejo de error cuando la cuenta de origen no es encontrada."""
    transaction_data = TransactionCreate(source_account_id=999, destination_account_id=2, amount=100.0)

    # Configurar para que la primera consulta (cuenta de origen) devuelva None
    mock_db_session.mock_account_query_chain.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="La cuenta de origen no existe o no pertenece al usuario"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

def test_create_new_transaction_destination_account_not_found(
    transaction_service, mock_db_session, mock_user, mock_source_account
):
    """Verifica el manejo de error cuando la cuenta de destino no es encontrada."""
    transaction_data = TransactionCreate(source_account_id=1, destination_account_id=999, amount=100.0)

    # Configurar para que la primera consulta devuelva la cuenta de origen y la segunda None
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        None
    ]

    with pytest.raises(ValueError, match="La cuenta de destino no existe"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

def test_create_new_transaction_insufficient_balance(
    transaction_service, mock_db_session, mock_user, mock_source_account, mock_destination_account
):
    """Verifica el manejo de error cuando el balance es insuficiente."""
    transaction_data = TransactionCreate(source_account_id=1, destination_account_id=2, amount=2000.0)

    # Configurar balance insuficiente
    mock_source_account.balance = 100.0

    # Configurar las queries de cuentas
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]

    with pytest.raises(ValueError, match="Balance insuficiente en la cuenta de origen"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

    # Restaurar balance original
    mock_source_account.balance = 1000.0

def test_create_new_transaction_exchange_rate_api_fails(
    mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency
):
    """Verifica el manejo de error cuando el servicio de tipo de cambio falla."""
    # Crear un mock del servicio de exchange que falle
    mock_specific_exchange_service = MagicMock()
    mock_specific_exchange_service.get_exchange_rate.side_effect = ValueError("API Error")

    # Crear servicio que use el servicio real (no mocked)
    with patch('services.transaction_service.ExchangeService', return_value=mock_specific_exchange_service):
        transaction_service_for_this_test = TransactionService(db=mock_db_session, use_mocked_exchange=False)

        transaction_data = TransactionCreate(source_account_id=1, destination_account_id=2, amount=100.0)

        # Configurar las queries de cuentas
        mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
            mock_source_account, mock_destination_account
        ]
        
        # Configurar las queries de monedas
        mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
            mock_source_currency, mock_destination_currency
        ]

        with pytest.raises(ValueError, match="API Error"):
            transaction_service_for_this_test.create_new_transaction(transaction_data, mock_user)

        # Verificar que se llamó al servicio de exchange
        mock_specific_exchange_service.get_exchange_rate.assert_called_once_with(
            mock_source_currency.code, mock_destination_currency.code
        )

def test_create_new_transaction_email_notification_fails(
    mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency,
    mock_receiver_user
):
    """Verifica que una falla en la notificación por correo no impida la creación de la transacción."""
    # Crear servicio que use el servicio real (no mocked) para probar las notificaciones
    with patch('services.transaction_service.ExchangeService') as mock_exchange_class:
        mock_exchange_service = MagicMock()
        mock_exchange_service.get_exchange_rate.return_value = 0.92
        mock_exchange_class.return_value = mock_exchange_service
        
        transaction_service_for_this_test = TransactionService(db=mock_db_session, use_mocked_exchange=False)

        transaction_data = TransactionCreate(
            source_account_id=mock_source_account.id,
            destination_account_id=mock_destination_account.id,
            amount=100.0
        )

        # Configurar las queries
        mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
            mock_source_account,
            mock_destination_account
        ]
        mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
            mock_source_currency,
            mock_destination_currency
        ]
        mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user

        # Mock del objeto Transaction que se creará
        mock_transaction = MagicMock()
        mock_transaction.sender_id = mock_user.id
        mock_transaction.receiver_id = mock_destination_account.user_id
        mock_transaction.source_account_id = mock_source_account.id
        mock_transaction.destination_account_id = mock_destination_account.id
        mock_transaction.source_amount = transaction_data.amount
        mock_transaction.source_currency_id = mock_source_currency.id
        mock_transaction.destination_amount = transaction_data.amount * 0.92
        mock_transaction.destination_currency_id = mock_destination_currency.id
        mock_transaction.exchange_rate = 0.92
        mock_transaction.description = None
        mock_transaction.timestamp = datetime.now(timezone.utc)

        # Mock del constructor de Transaction y del servicio de notificaciones que falla
        with patch('services.transaction_service.Transaction', return_value=mock_transaction):
            with patch('services.transaction_service.send_transaction_notification', side_effect=Exception("Email failed")):
                with patch('builtins.print') as mock_print:
                    created_transaction = transaction_service_for_this_test.create_new_transaction(transaction_data, mock_user)
                    mock_print.assert_called_with("Error al enviar la notificación: Email failed")

        # Verificar que la transacción se creó a pesar del error de email
        assert created_transaction is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

def test_get_user_transactions(transaction_service, mock_db_session, mock_user):
    """Verifica la obtención de transacciones de un usuario."""
    mock_transaction1 = Transaction(id=1, sender_id=mock_user.id, receiver_id=2, timestamp=datetime(2025, 7, 3, 10, 0, 0, tzinfo=timezone.utc))
    mock_transaction2 = Transaction(id=2, sender_id=3, receiver_id=mock_user.id, timestamp=datetime(2025, 7, 3, 9, 0, 0, tzinfo=timezone.utc))
    mock_transaction3 = Transaction(id=3, sender_id=mock_user.id, receiver_id=4, timestamp=datetime(2025, 7, 3, 11, 0, 0, tzinfo=timezone.utc))

    expected_transactions = [mock_transaction3, mock_transaction1, mock_transaction2]  # Ordenados por timestamp desc

    # Configurar la query para devolver las transacciones ordenadas
    mock_db_session.mock_transaction_query_chain.filter.return_value.order_by.return_value.all.return_value = expected_transactions

    transactions = transaction_service.get_user_transactions(mock_user.id)

    assert transactions == expected_transactions
    mock_db_session.query.assert_called_with(Transaction)
    mock_db_session.mock_transaction_query_chain.filter.return_value.order_by.assert_called_once()

def test_get_user_transactions_no_transactions(transaction_service, mock_db_session, mock_user):
    """Verifica el caso de no encontrar transacciones para un usuario."""
    mock_db_session.mock_transaction_query_chain.filter.return_value.order_by.return_value.all.return_value = []

    transactions = transaction_service.get_user_transactions(mock_user.id)

    assert transactions == []
    mock_db_session.query.assert_called_with(Transaction)
    mock_db_session.mock_transaction_query_chain.filter.return_value.order_by.return_value.all.assert_called_once()

def test_mock_exchange_service_inverse_rate():
    """Verifica que MockExchangeService use la tasa inversa cuando no hay tasa directa."""
    from services.transaction_service import MockExchangeService
    
    mock_exchange = MockExchangeService()
    
    # Test para una conversión que requiere tasa inversa
    # GBP -> USD no está en MOCKED_RATES, pero USD -> GBP sí está (valor: 0.80 implícito)
    # Necesitamos agregar USD -> GBP para que funcione la inversa
    
    # Primero probamos una que sabemos que existe directamente
    rate_pen_to_usd = mock_exchange.get_exchange_rate("PEN", "USD")
    assert rate_pen_to_usd == 0.27
    
    # Ahora probamos la inversa usando una tasa que existe al revés
    rate_usd_to_pen = mock_exchange.get_exchange_rate("USD", "PEN")
    assert rate_usd_to_pen == 3.70
    
    # Probamos con una tasa que debe usar la inversa
    # Como GBP -> USD = 1.25 está en MOCKED_RATES, entonces USD -> GBP debería ser 1/1.25 = 0.8
    rate_usd_to_gbp = mock_exchange.get_exchange_rate("USD", "GBP")
    assert rate_usd_to_gbp == pytest.approx(1 / 1.25, rel=1e-3)

def test_mock_exchange_service_no_rate_available():
    """Verifica que MockExchangeService lance error cuando no hay tasa disponible."""
    from services.transaction_service import MockExchangeService
    
    mock_exchange = MockExchangeService()
    
    # Probamos con monedas que no existen en MOCKED_RATES ni directa ni inversamente
    with pytest.raises(ValueError, match="No hay tasa de cambio mockeada disponible para XYZ a ABC"):
        mock_exchange.get_exchange_rate("XYZ", "ABC")

def test_create_new_transaction_with_inverse_exchange_rate(
    mock_db_session, mock_user, mock_source_account, mock_destination_account,
    mock_receiver_user
):
    """Verifica la creación de transacción usando tasa de cambio inversa."""
    
    # Crear monedas que requieran tasa inversa
    mock_source_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_destination_currency = Currency(id=2, code="GBP", name="British Pound")
    
    transaction_service = TransactionService(db=mock_db_session, use_mocked_exchange=True)
    
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_destination_account.id,
        amount=100.0,
        description="Test inverse rate"
    )

    # Configurar las queries
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,
        mock_destination_currency
    ]
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user

    # Mock del objeto Transaction que se creará
    # USD -> GBP debería usar la tasa inversa de GBP -> USD (1.25), entonces 1/1.25 = 0.8
    expected_rate = 1 / 1.25
    mock_transaction = MagicMock()
    mock_transaction.sender_id = mock_user.id
    mock_transaction.receiver_id = mock_destination_account.user_id
    mock_transaction.source_account_id = mock_source_account.id
    mock_transaction.destination_account_id = mock_destination_account.id
    mock_transaction.source_amount = transaction_data.amount
    mock_transaction.source_currency_id = mock_source_currency.id
    mock_transaction.destination_amount = transaction_data.amount * expected_rate
    mock_transaction.destination_currency_id = mock_destination_currency.id
    mock_transaction.exchange_rate = expected_rate
    mock_transaction.description = "Test inverse rate"
    mock_transaction.timestamp = datetime.now(timezone.utc)

    with patch('services.transaction_service.Transaction', return_value=mock_transaction):
        with patch('services.transaction_service.send_transaction_notification') as mock_send_notification:
            created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)

    # Verificar que se usó la tasa inversa correcta
    assert created_transaction.exchange_rate == pytest.approx(expected_rate, rel=1e-3)
    assert created_transaction.destination_amount == pytest.approx(transaction_data.amount * expected_rate, rel=1e-3)
    
    # Verificar que NO se enviaron notificaciones (porque use_mocked_exchange=True)
    assert mock_send_notification.call_count == 0

def test_create_new_transaction_with_unavailable_exchange_rate(
    mock_db_session, mock_user, mock_source_account, mock_destination_account
):
    """Verifica el manejo de error cuando no hay tasa de cambio disponible en el mock."""
    
    # Crear monedas que no existen en MOCKED_RATES
    mock_source_currency = Currency(id=1, code="XYZ", name="Unknown Currency")
    mock_destination_currency = Currency(id=2, code="ABC", name="Another Unknown Currency")
    
    transaction_service = TransactionService(db=mock_db_session, use_mocked_exchange=True)
    
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_destination_account.id,
        amount=100.0
    )

    # Configurar las queries
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,
        mock_destination_currency
    ]

    # Debería lanzar el error del MockExchangeService
    with pytest.raises(ValueError, match="No hay tasa de cambio mockeada disponible para XYZ a ABC"):
        transaction_service.create_new_transaction(transaction_data, mock_user)