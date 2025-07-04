import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import timedelta

from services.auth_service import AuthService
from database.models import User
# Assuming core.security and config are structured as expected
from core.security import verify_password, create_access_token, hash_password
# To mock ACCESS_TOKEN_EXPIRE_MINUTES, we might need to patch 'services.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES'
# or ensure it's available during tests. For simplicity, we can define it if it's just a constant.
# If it's loaded from env, that needs consideration.
# Let's assume it's patchable or we define a test value.

# Test value for token expiration
TEST_ACCESS_TOKEN_EXPIRE_MINUTES = 30

@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.first.return_value = None # Default: user not found
    return session

@pytest.fixture
@patch('services.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES', TEST_ACCESS_TOKEN_EXPIRE_MINUTES)
def auth_service(mock_db_session):
    # The patch ensures that when AuthService is instantiated, it uses the test value
    return AuthService(db=mock_db_session)

@pytest.fixture
def mock_user_data():
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": "hashed_super_secret_password" # Example hashed password
    }

@pytest.fixture
def mock_db_user(mock_user_data):
    return User(**mock_user_data)


# --- Test Cases for authenticate_user ---
@patch('services.auth_service.verify_password')
def test_authenticate_user_success(mock_verify_password, auth_service, mock_db_session, mock_db_user):
    mock_db_session.query(User).filter.return_value.first.return_value = mock_db_user
    mock_verify_password.return_value = True # Password matches

    email = mock_db_user.email
    password = "password123" # Plain text password for testing

    authenticated_user = auth_service.authenticate_user(email, password)

    assert authenticated_user == mock_db_user
    mock_db_session.query(User).filter.assert_called_once() # Basic check, arg check can be added
    mock_verify_password.assert_called_once_with(password, mock_db_user.hashed_password)

@patch('services.auth_service.verify_password')
def test_authenticate_user_wrong_password(mock_verify_password, auth_service, mock_db_session, mock_db_user):
    mock_db_session.query(User).filter.return_value.first.return_value = mock_db_user
    mock_verify_password.return_value = False # Password does not match

    email = mock_db_user.email
    password = "wrongpassword"

    authenticated_user = auth_service.authenticate_user(email, password)

    assert authenticated_user is None
    mock_verify_password.assert_called_once_with(password, mock_db_user.hashed_password)

def test_authenticate_user_not_found(auth_service, mock_db_session):
    mock_db_session.query(User).filter.return_value.first.return_value = None # User not found

    email = "nonexistent@example.com"
    password = "password123"

    authenticated_user = auth_service.authenticate_user(email, password)

    assert authenticated_user is None
    # verify_password should not be called if user is not found
    # This depends on the implementation detail of not calling verify_password if user is None
    # from `if not user or not verify_password(...)` short-circuiting.

# --- Test Cases for create_access_token_for_user ---
@patch('services.auth_service.create_access_token')
@patch('services.auth_service.timedelta') # To assert expires_delta
def test_create_access_token_for_user(mock_timedelta, mock_create_access_token, auth_service, mock_db_user):
    expected_token = "sample_jwt_token"
    mock_create_access_token.return_value = expected_token

    # Mock timedelta to check if it's called with the correct minutes
    mock_expires_delta = timedelta(minutes=TEST_ACCESS_TOKEN_EXPIRE_MINUTES)
    mock_timedelta.return_value = mock_expires_delta

    token = auth_service.create_access_token_for_user(mock_db_user)

    assert token == expected_token
    mock_timedelta.assert_called_once_with(minutes=TEST_ACCESS_TOKEN_EXPIRE_MINUTES)
    mock_create_access_token.assert_called_once_with(
        data={"sub": mock_db_user.email},
        expires_delta=mock_expires_delta
    )

# --- Test Cases for register_new_user ---
@patch('services.auth_service.hash_password')
@patch('services.auth_service.send_welcome_email')
def test_register_new_user_success(mock_send_welcome_email, mock_hash_password, auth_service, mock_db_session, mock_user_data):
    # User does not exist initially
    mock_db_session.query(User).filter.return_value.first.return_value = None

    username = mock_user_data["username"]
    email = mock_user_data["email"]
    password = "new_password123" # Plain text
    full_name = mock_user_data["full_name"]

    hashed_pw_return = "hashed_new_password"
    mock_hash_password.return_value = hashed_pw_return

    # Capture the User object passed to db.add and db.refresh
    added_user_capture = None
    def db_add_side_effect(user_obj):
        nonlocal added_user_capture
        added_user_capture = user_obj
    def db_refresh_side_effect(user_obj):
        # Simulate SQLAlchemy refresh behavior: copy relevant attributes or ensure it's the same obj
        user_obj.id = mock_user_data["id"] # Simulate ID assignment after commit

    mock_db_session.add.side_effect = db_add_side_effect
    mock_db_session.refresh.side_effect = db_refresh_side_effect

    new_user = auth_service.register_new_user(username, email, password, full_name)

    assert new_user is not None
    assert new_user.username == username
    assert new_user.email == email
    assert new_user.full_name == full_name
    assert new_user.hashed_password == hashed_pw_return
    assert new_user.id == mock_user_data["id"] # Check if ID was set (simulated by refresh)

    mock_hash_password.assert_called_once_with(password)
    mock_db_session.add.assert_called_once_with(added_user_capture) # Check that the captured object was added
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(added_user_capture)

    mock_send_welcome_email.assert_called_once_with(email, full_name)

def test_register_new_user_email_exists(auth_service, mock_db_session, mock_db_user):
    # User with this email already exists
    mock_db_session.query(User).filter.return_value.first.return_value = mock_db_user

    with pytest.raises(ValueError, match="El correo electrónico ya está registrado"):
        auth_service.register_new_user("newuser", mock_db_user.email, "password", "New Name")

@patch('services.auth_service.hash_password')
@patch('services.auth_service.send_welcome_email', side_effect=Exception("Email service down"))
def test_register_new_user_welcome_email_fails(mock_send_welcome_email_error, mock_hash_password, auth_service, mock_db_session, mock_user_data):
    mock_db_session.query(User).filter.return_value.first.return_value = None
    hashed_pw_return = "hashed_new_password"
    mock_hash_password.return_value = hashed_pw_return

    def db_refresh_side_effect(user_obj):
        user_obj.id = mock_user_data["id"]
    mock_db_session.refresh.side_effect = db_refresh_side_effect

    # We expect the user to be created even if email fails, and an error to be printed.
    with patch('builtins.print') as mock_print:
        new_user = auth_service.register_new_user(
            mock_user_data["username"], mock_user_data["email"], "password", mock_user_data["full_name"]
        )
        mock_print.assert_called_with(f"Error al enviar el correo de bienvenida: Email service down")

    assert new_user is not None
    assert new_user.email == mock_user_data["email"]
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_send_welcome_email_error.assert_called_once()


# Test for the AuthService class name change (if it was previously something else)
# This is more of a structural check, ensuring the class is named as expected by the tests.
def test_auth_service_class_name():
    assert AuthService.__name__ == "AuthService"
    # If there was an old name like AuthenticationService, this would ensure it's updated.
    # from services.auth_service import AuthenticationService # would fail if renamed
    # assert AuthenticationService is None # Or check it doesn't exist / raises ImportError.
    # This is mostly useful if refactoring from an old name.
    # For now, just asserting the current name is fine.

# It's good practice to ensure mocks are reset or don't leak between tests.
# Pytest fixtures handle this well for fixture-scoped mocks.
# For module-level patches (like ACCESS_TOKEN_EXPIRE_MINUTES), ensure they are correctly managed.
# The @patch decorator on the fixture `auth_service` scopes the patch to that fixture's lifecycle.
# If `ACCESS_TOKEN_EXPIRE_MINUTES` was imported at the top of `services.auth_service`
# like `from config import ACCESS_TOKEN_EXPIRE_MINUTES`, then patching
# `services.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES` is the correct way.
# If it was `import config` and then `config.ACCESS_TOKEN_EXPIRE_MINUTES`,
# you'd patch `services.auth_service.config.ACCESS_TOKEN_EXPIRE_MINUTES`.
# The current patch `services.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES` assumes it's directly available
# in the auth_service module's namespace. If `config.py` is simple and directly imported,
# this will work. If `config.py` uses `python-dotenv` to load at runtime, testing might need
# environment variable manipulation or more complex patching of the config loading mechanism.
# Given `from config import ACCESS_TOKEN_EXPIRE_MINUTES` in `auth_service.py`, the patch is correct.
# `patch('services.auth_service.ACCESS_TOKEN_EXPIRE_MINUTES', ...)` modifies it where it's used.

# Example of how to test the filter conditions more precisely if needed:
# from sqlalchemy.sql.expression import column
# def test_authenticate_user_filter_precision(auth_service, mock_db_session, mock_db_user):
#     mock_db_session.query(User).filter.return_value.first.return_value = mock_db_user
#     auth_service.authenticate_user(mock_db_user.email, "password")
#
#     # Get the actual SQLAlchemy expression passed to filter
#     filter_expression = mock_db_session.query(User).filter.call_args[0][0]
#
#     # Check the left side of the binary expression
#     assert filter_expression.left.name == User.email.name # or .key
#     # Check the right side (the value)
#     assert filter_expression.right.value == mock_db_user.email
#     # Check the operator if necessary (e.g., equality)
#     # This level of detail can be brittle if the query structure changes slightly.
#     # Usually, checking the side effects (correct user returned, mocks called) is sufficient.
#     pass
