import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from services.transaction_service import TransactionService, TransactionCreate
from database.models import User, Account, Transaction, Currency

# Mock User for testing
@pytest.fixture
def mock_user():
    user = User(id=1, email="test@example.com", full_name="Test User", hashed_password="hashedpassword")
    return user

@pytest.fixture
def mock_receiver_user():
    user = User(id=2, email="receiver@example.com", full_name="Receiver User", hashed_password="hashedpassword")
    return user

# Mock Account for testing
@pytest.fixture
def mock_source_account(mock_user):
    account = Account(id=1, user_id=mock_user.id, currency_id=1, balance=1000.0)
    account.user = mock_user # Simulate relationship
    return account

@pytest.fixture
def mock_destination_account(mock_receiver_user):
    account = Account(id=2, user_id=mock_receiver_user.id, currency_id=2, balance=500.0)
    account.user = mock_receiver_user # Simulate relationship
    return account

@pytest.fixture
def mock_same_currency_destination_account(mock_receiver_user):
    account = Account(id=3, user_id=mock_receiver_user.id, currency_id=1, balance=200.0)
    account.user = mock_receiver_user
    return account


# Mock Currency for testing
@pytest.fixture
def mock_source_currency():
    return Currency(id=1, code="USD", name="US Dollar")

@pytest.fixture
def mock_destination_currency():
    return Currency(id=2, code="EUR", name="Euro")

# Mock SQLAlchemy Session
@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=Session)

    # Create specific mocks for different types of queries
    mock_account_query_chain = MagicMock()
    mock_currency_query_chain = MagicMock()
    mock_user_query_chain = MagicMock() # For querying User model, e.g., for receiver
    mock_transaction_query_chain = MagicMock() # For querying Transaction model

    # Default behaviors for these chains (can be overridden in tests)
    mock_account_query_chain.filter.return_value.first.return_value = None
    mock_currency_query_chain.filter.return_value.first.return_value = None
    mock_user_query_chain.filter.return_value.first.return_value = None
    mock_transaction_query_chain.filter.return_value.order_by.return_value.all.return_value = []


    def query_side_effect(model_class):
        if model_class == Account:
            # Reset call_args_list for chained calls if necessary, or use new mocks
            # For simplicity here, we assume tests will set specific return_values
            return mock_account_query_chain
        elif model_class == Currency:
            return mock_currency_query_chain
        elif model_class == User:
            return mock_user_query_chain
        elif model_class == Transaction:
            return mock_transaction_query_chain
        else:
            # Fallback for any other unexpected queries
            print(f"Warning: Unmocked query for model: {model_class}")
            return MagicMock()

    session.query.side_effect = query_side_effect

    # Store these specific mocks on the session mock itself for easy access in tests
    session.mock_account_query_chain = mock_account_query_chain
    session.mock_currency_query_chain = mock_currency_query_chain
    session.mock_user_query_chain = mock_user_query_chain
    session.mock_transaction_query_chain = mock_transaction_query_chain

    return session

# Mock ExchangeService
@pytest.fixture
def mock_exchange_service():
    service = MagicMock()
    service.get_exchange_rate.return_value = 0.85 # Default rate USD to EUR
    return service

@pytest.fixture
@patch('services.transaction_service.ExchangeService')
def transaction_service(MockExchangeService, mock_db_session, mock_exchange_service):
    MockExchangeService.return_value = mock_exchange_service # Use the MagicMock instance
    return TransactionService(db=mock_db_session)

def test_create_new_transaction_success_different_currency(
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency,
    mock_exchange_service, mock_receiver_user
):
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_destination_account.id,
        amount=100.0,
        description="Test transaction"
    )

    # Configure mocks for specific query chains
    # Order of calls to first() matters here if filter() is called multiple times on the same chain object
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,    # For source_account query
        mock_destination_account # For destination_account query
    ]
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,   # For source_currency query
        mock_destination_currency # For destination_currency query
    ]
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user # For receiver user query for email

    initial_source_balance = mock_source_account.balance
    initial_dest_balance = mock_destination_account.balance

    with patch('services.transaction_service.send_transaction_notification') as mock_send_notification:
        created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)

    assert created_transaction is not None
    assert created_transaction.sender_id == mock_user.id
    assert created_transaction.receiver_id == mock_destination_account.user_id
    assert created_transaction.source_account_id == mock_source_account.id
    assert created_transaction.destination_account_id == mock_destination_account.id
    assert created_transaction.source_amount == transaction_data.amount
    assert created_transaction.source_currency_id == mock_source_currency.id
    assert created_transaction.destination_amount == transaction_data.amount * 0.85 # 100 * 0.85
    assert created_transaction.destination_currency_id == mock_destination_currency.id
    assert created_transaction.exchange_rate == 0.85
    assert created_transaction.description == "Test transaction"
    assert isinstance(created_transaction.timestamp, datetime)

    mock_exchange_service.get_exchange_rate.assert_called_once_with("USD", "EUR")

    assert mock_source_account.balance == initial_source_balance - transaction_data.amount
    assert mock_destination_account.balance == initial_dest_balance + (transaction_data.amount * 0.85)

    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_transaction)

    assert mock_send_notification.call_count == 2
    mock_send_notification.assert_any_call(
        mock_user.email, mock_user.full_name, created_transaction, "USD", "EUR", is_sender=True
    )
    mock_send_notification.assert_any_call(
        mock_receiver_user.email, mock_receiver_user.full_name, created_transaction, "USD", "EUR", is_sender=False
    )


def test_create_new_transaction_success_same_currency(
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_same_currency_destination_account, mock_source_currency, mock_exchange_service, mock_receiver_user
):
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_same_currency_destination_account.id,
        amount=50.0
    )

    # Configure mocks
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_same_currency_destination_account
    ]
    # Both source and destination currency are the same
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency, # For source currency
        mock_source_currency  # For destination currency (which is the same)
    ]
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user

    initial_source_balance = mock_source_account.balance
    initial_dest_balance = mock_same_currency_destination_account.balance

    with patch('services.transaction_service.send_transaction_notification') as mock_send_notification:
        created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)

    assert created_transaction.destination_amount == transaction_data.amount
    assert created_transaction.exchange_rate == 1.0
    mock_exchange_service.get_exchange_rate.assert_not_called()

    assert mock_source_account.balance == initial_source_balance - transaction_data.amount
    assert mock_same_currency_destination_account.balance == initial_dest_balance + transaction_data.amount

    assert mock_send_notification.call_count == 2


def test_create_new_transaction_source_account_not_found(transaction_service, mock_db_session, mock_user):
    transaction_data = TransactionCreate(source_account_id=999, destination_account_id=2, amount=100.0)

    mock_db_session.query(Account).filter.return_value.first.return_value = None # Source account not found

    with pytest.raises(ValueError, match="La cuenta de origen no existe o no pertenece al usuario"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

def test_create_new_transaction_destination_account_not_found(
    transaction_service, mock_db_session, mock_user, mock_source_account
):
    transaction_data = TransactionCreate(source_account_id=1, destination_account_id=999, amount=100.0)

    # Source account found, destination not
    mock_db_session.query(Account).filter.return_value.first.side_effect = [
        mock_source_account, # Source account
        None                 # Destination account
    ]

    with pytest.raises(ValueError, match="La cuenta de destino no existe"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

def test_create_new_transaction_insufficient_balance(
    transaction_service, mock_db_session, mock_user, mock_source_account, mock_destination_account
):
    transaction_data = TransactionCreate(source_account_id=1, destination_account_id=2, amount=2000.0) # More than balance

    mock_source_account.balance = 100.0 # Set balance lower than amount

    mock_db_session.query(Account).filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]

    with pytest.raises(ValueError, match="Balance insuficiente en la cuenta de origen"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

    mock_source_account.balance = 1000.0 # Reset balance

def test_create_new_transaction_exchange_rate_api_fails(
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency,
    mock_exchange_service
):
    transaction_data = TransactionCreate(source_account_id=1, destination_account_id=2, amount=100.0)

    mock_db_session.query(Account).filter.return_value.first.side_effect = [
        mock_source_account, mock_destination_account
    ]
    mock_db_session.query(Currency).filter.return_value.first.side_effect = [
        mock_source_currency, mock_destination_currency
    ]

    mock_exchange_service.get_exchange_rate.side_effect = ValueError("API Error")

    with pytest.raises(ValueError, match="API Error"):
        transaction_service.create_new_transaction(transaction_data, mock_user)

@patch('services.transaction_service.send_transaction_notification', side_effect=Exception("Email failed"))
def test_create_new_transaction_email_notification_fails(
    mock_send_email_func, # The patched function
    transaction_service, mock_db_session, mock_user, mock_source_account,
    mock_destination_account, mock_source_currency, mock_destination_currency,
    mock_exchange_service, mock_receiver_user
):
    transaction_data = TransactionCreate(
        source_account_id=mock_source_account.id,
        destination_account_id=mock_destination_account.id,
        amount=100.0
    )

    # Configure mocks
    mock_db_session.mock_account_query_chain.filter.return_value.first.side_effect = [
        mock_source_account,
        mock_destination_account
    ]
    mock_db_session.mock_currency_query_chain.filter.return_value.first.side_effect = [
        mock_source_currency,
        mock_destination_currency
    ]
    mock_db_session.mock_user_query_chain.filter.return_value.first.return_value = mock_receiver_user


    # We expect the transaction to still be created, but an error logged (which we can't directly check here without capturing stdout)
    # The main thing is that the email exception doesn't stop the transaction.
    with patch('builtins.print') as mock_print: # To check if the error is printed
        created_transaction = transaction_service.create_new_transaction(transaction_data, mock_user)
        mock_print.assert_called_with("Error al enviar la notificación: Email failed")

    assert created_transaction is not None # Transaction should still go through
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert mock_send_email_func.call_count > 0 # Email sending was attempted


def test_get_user_transactions(transaction_service, mock_db_session, mock_user):
    mock_transaction1 = Transaction(sender_id=mock_user.id, receiver_id=2, timestamp=datetime.now(timezone.utc))
    mock_transaction2 = Transaction(sender_id=3, receiver_id=mock_user.id, timestamp=datetime.now(timezone.utc))
    mock_transaction3 = Transaction(sender_id=mock_user.id, receiver_id=4, timestamp=datetime.now(timezone.utc))

    expected_transactions = [mock_transaction3, mock_transaction1, mock_transaction2] # Assuming order by desc timestamp

    # Configure the mock to return the transactions
    mock_db_session.query(Transaction).filter.return_value.order_by.return_value.all.return_value = expected_transactions

    transactions = transaction_service.get_user_transactions(mock_user.id)

    assert transactions == expected_transactions
    # Check that filter was called with an OR condition for sender_id or receiver_id
    # This is a bit complex to assert directly with MagicMock's call_args,
    # but we can infer it from the logic and ensure the query method was called.
    mock_db_session.query.assert_called_with(Transaction)
    # Further inspection of the filter call would require deeper mocking or specific argument matching.
    # For now, we assume the filter correctly implements (Transaction.sender_id == user_id) | (Transaction.receiver_id == user_id)
    # And that order_by was called.
    mock_db_session.query(Transaction).filter.return_value.order_by.assert_called_once()


def test_get_user_transactions_no_transactions(transaction_service, mock_db_session, mock_user):
    mock_db_session.query(Transaction).filter.return_value.order_by.return_value.all.return_value = []

    transactions = transaction_service.get_user_transactions(mock_user.id)

    assert transactions == []
    mock_db_session.query.assert_called_with(Transaction)
    mock_db_session.query(Transaction).filter.return_value.order_by.return_value.all.assert_called_once()

# Example of how to reset mocks if they were module-level and modified by tests
# For fixture-based mocks, this is usually handled by pytest re-running fixtures.
# @pytest.fixture(autouse=True)
# def reset_mocks():
#     # If you had module-level mocks that get changed, reset them here.
#     # e.g., if ExchangeService was a real singleton being patched globally.
#     pass
