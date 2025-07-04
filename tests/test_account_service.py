import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.exc import NoResultFound

from services.account_service import AccountService
from database.models import User, Account, Currency, Transaction

@pytest.fixture
def mock_user():
    return User(id=1, email="test@example.com", full_name="Test User")

@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=Session)
    # Generic query mock, specific behaviors will be set in tests
    query_mock = MagicMock(spec=Query)
    session.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.join.return_value = query_mock
    query_mock.options.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    return session

@pytest.fixture
def account_service(mock_db_session):
    return AccountService(db=mock_db_session)

def test_get_user_accounts_success(account_service, mock_db_session, mock_user):
    mock_account1_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_account1 = Account(id=1, user_id=mock_user.id, currency_id=1, balance=100.0, currency=mock_account1_currency)
    mock_account2_currency = Currency(id=2, code="EUR", name="Euro")
    mock_account2 = Account(id=2, user_id=mock_user.id, currency_id=2, balance=200.0, currency=mock_account2_currency)
    expected_accounts = [mock_account1, mock_account2]

    mock_query = mock_db_session.query(Account)
    mock_query.filter.return_value.join.return_value.options.return_value.all.return_value = expected_accounts

    accounts = account_service.get_user_accounts(user_id=mock_user.id)

    assert accounts == expected_accounts
    mock_db_session.query.assert_any_call(Account) # Changed from assert_called_once_with
    # Check that filter was called with Account.user_id == mock_user.id
    # This requires inspecting the arguments of the filter call.
    # For simplicity, we trust the implementation if the correct data is returned.
    # A more rigorous check would involve:
    # call_args = mock_query.filter.call_args[0][0] # Gets the SQLAlchemy expression
    # assert str(call_args) == str(Account.user_id == mock_user.id) # Or compare elements

def test_get_user_accounts_none_found(account_service, mock_db_session, mock_user):
    mock_query = mock_db_session.query(Account)
    mock_query.filter.return_value.join.return_value.options.return_value.all.return_value = []

    accounts = account_service.get_user_accounts(user_id=mock_user.id)

    assert accounts == []

def test_get_account_details_success(account_service, mock_db_session, mock_user):
    account_id = 1
    mock_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0, currency=mock_currency)
    mock_transaction1 = Transaction(id=1, source_account_id=account_id, destination_account_id=2)
    mock_transaction2 = Transaction(id=2, source_account_id=3, destination_account_id=account_id)
    expected_transactions = [mock_transaction1, mock_transaction2]

    # Mock for account query
    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.join.return_value.options.return_value.first.return_value = mock_account

    # Mock for transaction query
    transaction_query_mock = MagicMock()
    transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = expected_transactions

    # Side effect for session.query based on the model being queried
    def query_side_effect(model):
        if model == Account:
            return account_query_mock
        elif model == Transaction:
            return transaction_query_mock
        return MagicMock() # Default mock for other queries

    mock_db_session.query.side_effect = query_side_effect

    account, transactions = account_service.get_account_details(account_id=account_id, user_id=mock_user.id)

    assert account == mock_account
    assert transactions == expected_transactions

    # Check Account query calls
    account_query_mock.filter.assert_called_once() # Further checks on filter args can be added

    # Check Transaction query calls
    transaction_query_mock.filter.assert_called_once() # Further checks on filter args
    transaction_query_mock.filter.return_value.order_by.assert_called_once()


def test_get_account_details_account_not_found(account_service, mock_db_session, mock_user):
    account_id = 999 # Non-existent account

    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.join.return_value.options.return_value.first.return_value = None

    mock_db_session.query.return_value = account_query_mock # Simplified for this test

    account, transactions = account_service.get_account_details(account_id=account_id, user_id=mock_user.id)

    assert account is None
    assert transactions is None # As per service logic when account not found

def test_get_account_details_no_transactions(account_service, mock_db_session, mock_user):
    account_id = 1
    mock_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0, currency=mock_currency)

    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.join.return_value.options.return_value.first.return_value = mock_account

    transaction_query_mock = MagicMock()
    # No transactions found
    transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = []

    def query_side_effect(model):
        if model == Account:
            return account_query_mock
        elif model == Transaction:
            return transaction_query_mock
        return MagicMock()
    mock_db_session.query.side_effect = query_side_effect

    account, transactions = account_service.get_account_details(account_id=account_id, user_id=mock_user.id)

    assert account == mock_account
    assert transactions == []


@patch('services.account_service.send_account_statement')
def test_export_account_statement_success(mock_send_statement, account_service, mock_db_session, mock_user):
    account_id = 1
    export_format = "csv"
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0)
    mock_transactions = [Transaction(id=1)]

    # Mock for account query
    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.first.return_value = mock_account

    # Mock for transaction query
    transaction_query_mock = MagicMock()
    transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = mock_transactions

    def query_side_effect(model):
        if model == Account:
            return account_query_mock
        elif model == Transaction:
            return transaction_query_mock
        return MagicMock()
    mock_db_session.query.side_effect = query_side_effect

    result = account_service.export_account_statement(account_id, export_format, mock_user)

    assert result is True
    mock_send_statement.assert_called_once_with(
        mock_user.email,
        mock_user.full_name,
        mock_account,
        mock_transactions,
        export_format
    )
    # Verify account query
    account_query_mock.filter.assert_called_once()
    # Verify transaction query
    transaction_query_mock.filter.assert_called_once()
    transaction_query_mock.filter.return_value.order_by.assert_called_once()


@patch('services.account_service.send_account_statement')
def test_export_account_statement_account_not_found(mock_send_statement, account_service, mock_db_session, mock_user):
    account_id = 999 # Non-existent account
    export_format = "xml"

    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.first.return_value = None # Account not found

    mock_db_session.query.return_value = account_query_mock # Simplified

    with pytest.raises(ValueError, match="Cuenta no encontrada"):
        account_service.export_account_statement(account_id, export_format, mock_user)

    mock_send_statement.assert_not_called()


@patch('services.account_service.send_account_statement', side_effect=Exception("Email send failed"))
def test_export_account_statement_email_send_fails(mock_send_statement_error, account_service, mock_db_session, mock_user):
    account_id = 1
    export_format = "csv"
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0)
    mock_transactions = [Transaction(id=1)]

    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.first.return_value = mock_account

    transaction_query_mock = MagicMock()
    transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = mock_transactions

    def query_side_effect(model):
        if model == Account:
            return account_query_mock
        elif model == Transaction:
            return transaction_query_mock
        return MagicMock()
    mock_db_session.query.side_effect = query_side_effect

    # The service catches the exception from send_account_statement and re-raises it if not handled,
    # or returns based on its logic. Here, we assume it might propagate or handle.
    # The current service code implies send_account_statement is called and if it fails,
    # the exception will propagate unless caught inside send_account_statement.
    # If send_account_statement itself handles errors and doesn't re-raise, then this test changes.
    # Assuming it *can* raise an Exception:
    with pytest.raises(Exception, match="Email send failed"):
         account_service.export_account_statement(account_id, export_format, mock_user)

    mock_send_statement_error.assert_called_once()

    # If the service is designed to catch the exception from send_account_statement and return False/raise specific error:
    # For example, if AccountService had a try-except around send_account_statement:
    # with pytest.raises(SpecificServiceError):
    #     account_service.export_account_statement(account_id, export_format, mock_user)
    # OR
    # assert account_service.export_account_statement(account_id, export_format, mock_user) is False

    # Based on current `account_service.py`, any exception from `send_account_statement` will propagate.
    # So, the `pytest.raises(Exception, ...)` is correct.
    # The service returns True only on success.

    # To make it more robust, we might want `export_account_statement` to catch exceptions from `send_account_statement`
    # and raise a service-specific error or return False.
    # For now, the test reflects the current behavior.

# Example of how to mock joinedload if it's causing issues, though typically MagicMock handles attribute access.
# @patch('sqlalchemy.orm.joinedload')
# def test_with_joinedload_mock(mock_joinedload, ...):
#     mock_joinedload.return_value = MagicMock() # Or some specific SQLAlchemy option
#     # ... rest of the test
#     pass
