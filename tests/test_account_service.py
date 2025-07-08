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
    query_mock = MagicMock(spec=Query)
    query_mock.filter.return_value = query_mock
    query_mock.join.return_value = query_mock
    query_mock.options.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    session.query.return_value = query_mock 

    query_mock.first.return_value = None
    query_mock.all.return_value = []
    
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

    mock_db_session.query.return_value.filter.return_value.join.return_value.options.return_value.all.return_value = expected_accounts

    accounts = account_service.get_user_accounts(user_id=mock_user.id)

    assert accounts == expected_accounts
    mock_db_session.query.assert_any_call(Account) 

def test_get_user_accounts_none_found(account_service, mock_db_session, mock_user):
    mock_db_session.query.return_value.filter.return_value.join.return_value.options.return_value.all.return_value = []

    accounts = account_service.get_user_accounts(user_id=mock_user.id)

    assert accounts == []

def test_get_account_details_success(account_service, mock_db_session, mock_user):
    account_id = 1
    mock_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0, currency=mock_currency)
    mock_transaction1 = Transaction(id=1, source_account_id=account_id, destination_account_id=2)
    mock_transaction2 = Transaction(id=2, source_account_id=3, destination_account_id=account_id)
    expected_transactions = [mock_transaction1, mock_transaction2]

    def query_side_effect(model):
        if model == Account:
            mock_filter = MagicMock()
            mock_filter.join.return_value.options.return_value.first.return_value = mock_account
            return_value_for_query = MagicMock()
            return_value_for_query.filter.return_value = mock_filter
            return return_value_for_query
        elif model == Transaction:
            mock_filter = MagicMock()
            mock_filter.order_by.return_value.all.return_value = expected_transactions
            return_value_for_query = MagicMock()
            return_value_for_query.filter.return_value = mock_filter
            return return_value_for_query
        return MagicMock() 

    mock_db_session.query.side_effect = query_side_effect

    account, transactions = account_service.get_account_details(account_id=account_id, user_id=mock_user.id)

    assert account == mock_account
    assert transactions == expected_transactions

    mock_db_session.query.assert_any_call(Account)
    mock_db_session.query.assert_any_call(Transaction)


def test_get_account_details_account_not_found(account_service, mock_db_session, mock_user):
    account_id = 999 

    mock_db_session.query.return_value.filter.return_value.join.return_value.options.return_value.first.return_value = None

    account, transactions = account_service.get_account_details(account_id=account_id, user_id=mock_user.id)

    assert account is None
    assert transactions is None 

def test_get_account_details_no_transactions(account_service, mock_db_session, mock_user):
    account_id = 1
    mock_currency = Currency(id=1, code="USD", name="US Dollar")
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0, currency=mock_currency)

    def query_side_effect(model):
        if model == Account:
            mock_filter = MagicMock()
            mock_filter.join.return_value.options.return_value.first.return_value = mock_account
            query_for_account = MagicMock()
            query_for_account.filter.return_value = mock_filter
            return query_for_account
        elif model == Transaction:
            mock_filter = MagicMock()
            mock_filter.order_by.return_value.all.return_value = []
            query_for_transaction = MagicMock()
            query_for_transaction.filter.return_value = mock_filter
            return query_for_transaction
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

    def query_side_effect(model):
        if model == Account:
            account_query_mock = MagicMock()
            account_query_mock.filter.return_value.first.return_value = mock_account
            return account_query_mock
        elif model == Transaction:
            transaction_query_mock = MagicMock()
            transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = mock_transactions
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
    mock_db_session.query.assert_any_call(Account)
    mock_db_session.query.assert_any_call(Transaction)


@patch('services.account_service.send_account_statement')
def test_export_account_statement_account_not_found(mock_send_statement, account_service, mock_db_session, mock_user):
    account_id = 999 
    export_format = "xml"

    mock_db_session.query.return_value.filter.return_value.first.return_value = None 

    with pytest.raises(ValueError, match="Cuenta no encontrada"):
        account_service.export_account_statement(account_id, export_format, mock_user)

    mock_send_statement.assert_not_called()


@patch('services.account_service.send_account_statement', side_effect=Exception("Email send failed"))
def test_export_account_statement_email_send_fails(mock_send_statement_error, account_service, mock_db_session, mock_user):
    account_id = 1
    export_format = "csv"
    mock_account = Account(id=account_id, user_id=mock_user.id, currency_id=1, balance=100.0)
    mock_transactions = [Transaction(id=1)]

    def query_side_effect(model):
        if model == Account:
            account_query_mock = MagicMock()
            account_query_mock.filter.return_value.first.return_value = mock_account
            return account_query_mock
        elif model == Transaction:
            transaction_query_mock = MagicMock()
            transaction_query_mock.filter.return_value.order_by.return_value.all.return_value = mock_transactions
            return transaction_query_mock
        return MagicMock()
    mock_db_session.query.side_effect = query_side_effect

    with pytest.raises(Exception, match="Email send failed"):
        account_service.export_account_statement(account_id, export_format, mock_user)

    mock_send_statement_error.assert_called_once()

# --- NUEVAS PRUEBAS PARA DEPOSITAR A UNA CUENTA ---

def test_deposit_to_account_success(account_service, mock_db_session):
    account_id = 1
    initial_balance = 100.0
    deposit_amount = 50.0
    expected_balance = initial_balance + deposit_amount

    mock_account = MagicMock(spec=Account, id=account_id, balance=initial_balance)
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account

    updated_account = account_service.deposit_to_account(account_id, deposit_amount)

    assert updated_account.balance == expected_balance
    
    mock_db_session.query.assert_called_once_with(Account)
    # Ya no verificamos el argumento exacto de filter porque su BinaryExpression cambia
    mock_db_session.query.return_value.filter.assert_called_once() 
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    
    mock_db_session.add.assert_called_once_with(mock_account)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_account)

def test_deposit_to_account_invalid_amount(account_service, mock_db_session):
    account_id = 1
    
    with pytest.raises(ValueError, match="El monto del depósito debe ser positivo."):
        account_service.deposit_to_account(account_id, 0.0)
    
    with pytest.raises(ValueError, match="El monto del depósito debe ser positivo."):
        account_service.deposit_to_account(account_id, -10.0)
    
    mock_db_session.query.assert_not_called()
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.refresh.assert_not_called()

def test_deposit_to_account_not_found(account_service, mock_db_session):
    account_id = 999 
    deposit_amount = 50.0

    mock_db_session.query.return_value.filter.return_value.first.return_value = None 

    with pytest.raises(ValueError, match="Cuenta no encontrada para el depósito."):
        account_service.deposit_to_account(account_id, deposit_amount)

    mock_db_session.query.assert_called_once_with(Account)
    # Ya no verificamos el argumento exacto de filter
    mock_db_session.query.return_value.filter.assert_called_once() 
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.refresh.assert_not_called()