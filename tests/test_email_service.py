import pytest
from unittest.mock import MagicMock, patch, mock_open
import smtplib
import os
import unicodedata
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
import io # Added for StringIO

# Modules to test
from services import email_service
from services.email_service import (
    normalize_text,
    send_email,
    send_welcome_email,
    send_transaction_notification,
    create_csv_export,
    create_xml_export,
    send_account_statement,
)

# Mock config values (these would normally come from config.py)
# Patch them where they are used in the email_service module.
# We use patch.object or patch directly on email_service.CONFIG_VAR
TEST_SMTP_SERVER = "smtp.test.com"
TEST_SMTP_PORT = 587
TEST_SMTP_USERNAME = "testuser"
TEST_SMTP_PASSWORD = "testpassword" # Normal space, no NBSP
TEST_EMAIL_FROM = "noreply@yala.com"

@pytest.fixture(autouse=True)
def mock_config_values(monkeypatch):
    monkeypatch.setattr(email_service, 'SMTP_SERVER', TEST_SMTP_SERVER)
    monkeypatch.setattr(email_service, 'SMTP_PORT', TEST_SMTP_PORT)
    monkeypatch.setattr(email_service, 'SMTP_USERNAME', TEST_SMTP_USERNAME)
    monkeypatch.setattr(email_service, 'SMTP_PASSWORD', TEST_SMTP_PASSWORD)
    monkeypatch.setattr(email_service, 'EMAIL_FROM', TEST_EMAIL_FROM)

# --- Test normalize_text ---
def test_normalize_text_empty_or_none():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""

def test_normalize_text_nbsp_replacement():
    assert normalize_text("Hello\xa0World") == "Hello World"

def test_normalize_text_nfc_normalization():
    # Example: U+0061 (a) + U+0301 (combining acute accent) -> U+00E1 (á)
    decomposed_a_acute = "a\u0301" # a + combining acute
    composed_a_acute = "\u00e1"    # á (NFC form)
    assert normalize_text(decomposed_a_acute) == composed_a_acute
    assert normalize_text("Caf\u00e9") == "Café" # Already NFC

# --- Test send_email ---
@patch('services.email_service.smtplib.SMTP')
def test_send_email_success(mock_smtp_constructor):
    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance

    to_email = "recipient@example.com"
    subject = "Test Subject"
    body_html = "<p>Test Body</p>"
    attachments = {"test.txt": "Hello content"}

    result = send_email(to_email, subject, body_html, attachments)

    assert result is True
    mock_smtp_constructor.assert_called_once_with(TEST_SMTP_SERVER, TEST_SMTP_PORT)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with(TEST_SMTP_USERNAME, TEST_SMTP_PASSWORD)

    # Check sendmail arguments (more complex due to MIMEMultipart)
    assert mock_smtp_instance.sendmail.call_count == 1
    call_args = mock_smtp_instance.sendmail.call_args
    assert call_args[1]['from_addr'] == TEST_EMAIL_FROM
    assert call_args[1]['to_addrs'] == [to_email]

    # Verify message content (simplified check)
    # Checking the raw message string for subject can be unreliable due to encoding.
    # The subject is set on the msg object. We can assume Header handles encoding correctly.
    # The content of the attachment is base64 encoded in the message_string, so direct check is not simple.
    message_string = call_args[1]['msg']
    assert f"To: {to_email}" in message_string
    assert "Content-Type: text/html" in message_string # Check for HTML part
    assert "Content-Disposition: attachment; filename=\"test.txt\"" in message_string # Check for attachment header
    # assert "Hello content" in message_string # This will fail as content is base64 encoded.
                                              # A more robust check would decode the relevant part.

@patch('services.email_service.smtplib.SMTP')
def test_send_email_no_attachments(mock_smtp_constructor):
    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance

    result = send_email("r@e.com", "Sub", "<p>Body</p>", None)
    assert result is True
    message_string = mock_smtp_instance.sendmail.call_args[1]['msg']
    assert "Content-Disposition: attachment" not in message_string

@patch('services.email_service.smtplib.SMTP')
def test_send_email_smtp_login_fails(mock_smtp_constructor, capsys):
    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "Auth failed")

    result = send_email("r@e.com", "Sub", "<p>Body</p>")
    assert result is False
    captured = capsys.readouterr()
    assert "Error de correo: (535, 'Auth failed')" in captured.out # Corrected: no b''

@patch('services.email_service.smtplib.SMTP')
def test_send_email_generic_exception(mock_smtp_constructor, capsys):
    mock_smtp_constructor.side_effect = Exception("Connection refused")
    result = send_email("r@e.com", "Sub", "<p>Body</p>")
    assert result is False
    captured = capsys.readouterr()
    assert "Error de correo: Connection refused" in captured.out

@patch('services.email_service.smtplib.SMTP')
def test_send_email_unicode_error_in_subject(mock_smtp_constructor, capsys):
    # This test is tricky because the error might happen during Header creation or MIMEMultipart.as_string()
    # Let's simulate it by making normalize_text return something problematic for `Header`
    # or by making the subject itself problematic if `normalize_text` doesn't catch it.
    # For this test, let's assume the error happens at `msg.as_string()` if a bad char gets through.

    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance

    # If a subject contains surrogates, Header() itself will raise UnicodeEncodeError.
    # The send_email function's try-except for UnicodeEncodeError is for later stages (msg.as_string, sendmail).
    # This test verifies that such an error from Header creation is not silently caught by those later blocks.
    problematic_subject = "Invalid\udcffSubject" # Contains a surrogate character
    with pytest.raises(UnicodeEncodeError, match="'utf-8' codec can't encode character '\\\\udcff' in position 7: surrogates not allowed"):
        result = send_email("r@e.com", problematic_subject, "<p>Body</p>")

    # send_email should not be reached if Header() fails, so no SMTP calls.
    mock_smtp_constructor.assert_not_called()

# --- Test send_welcome_email ---
@patch('services.email_service.send_email')
def test_send_welcome_email(mock_send_email):
    mock_send_email.return_value = True
    user_email = "newuser@example.com"
    user_name = "New User"

    result = send_welcome_email(user_email, user_name)

    assert result is True
    mock_send_email.assert_called_once()
    args, _ = mock_send_email.call_args
    assert args[0] == user_email
    assert "¡Bienvenido a YALA!" in args[1] # Subject
    assert f"¡Bienvenido a YALA, {user_name}!" in args[2] # Body

# --- Test send_transaction_notification ---
@patch('services.email_service.send_email')
def test_send_transaction_notification_sender(mock_send_email):
    mock_send_email.return_value = True
    mock_transaction = MagicMock()
    mock_transaction.source_amount = 100.0
    mock_transaction.destination_amount = 85.0
    mock_transaction.timestamp = datetime.now()
    mock_transaction.description = "Payment for goods"

    result = send_transaction_notification(
        "sender@example.com", "Sender Name", mock_transaction, "USD", "EUR", is_sender=True
    )
    assert result is True
    args, _ = mock_send_email.call_args
    expected_subject = f"Notificación de Transacción - Enviado {mock_transaction.source_amount} USD"
    assert args[1] == expected_subject
    assert "Has enviado una transacción:" in args[2] # Body
    assert "Monto: 100.0 USD" in args[2]

@patch('services.email_service.send_email')
def test_send_transaction_notification_receiver(mock_send_email):
    mock_send_email.return_value = True
    mock_transaction = MagicMock()
    mock_transaction.source_amount = 100.0
    mock_transaction.destination_amount = 85.0
    mock_transaction.timestamp = datetime.now()
    mock_transaction.description = None # Test no description

    result = send_transaction_notification(
        "receiver@example.com", "Receiver Name", mock_transaction, "USD", "EUR", is_sender=False
    )
    assert result is True
    args, _ = mock_send_email.call_args
    expected_subject = f"Notificación de Transacción - Recibido {mock_transaction.destination_amount} EUR"
    assert args[1] == expected_subject
    assert "Has recibido una transacción:" in args[2] # Body
    assert "Monto: 85.0 EUR" in args[2]
    assert "Sin descripción" in args[2]


# --- Test create_csv_export ---
@patch('services.email_service.tempfile.NamedTemporaryFile')
@patch('services.email_service.os.unlink')
@patch('services.email_service.csv.writer') # To inspect what's written
def test_create_csv_export(mock_csv_writer, mock_os_unlink, mock_tempfile): # mock_csv_writer added
    mock_user = MagicMock(full_name="Test User", email="user@example.com")
    mock_currency = MagicMock(code="USD")
    mock_account = MagicMock(id=1, currency=mock_currency, balance=1000.0)
    mock_tx1 = MagicMock(id=101, timestamp=datetime(2023,1,1,10,0,0), description="Sent money", source_account_id=1, source_amount=50.0, destination_amount=40.0)
    mock_tx2 = MagicMock(id=102, timestamp=datetime(2023,1,2,11,0,0), description="Received payment", source_account_id=99, destination_account_id=1, source_amount=30.0, destination_amount=30.0)
    transactions = [mock_tx1, mock_tx2]

    # Mock the temp file behavior
    mock_file_io = io.StringIO() # Use StringIO for csv.writer compatibility
    mock_file_io.name = "dummy_temp_file.csv" # <--- This is the crucial line

    mock_tempfile.return_value.__enter__.return_value = mock_file_io
    # The object 'tmp' in 'with ... as tmp' will be mock_file_io.
    # So, tmp.name will be "dummy_temp_file.csv".
    # os.unlink will be called with this name too.

    # We need to mock `open` because the function re-opens the temp file to read its content
    with patch('services.email_service.open', mock_open(read_data="dummy csv content")) as mock_builtin_open:
        csv_content = create_csv_export(mock_user, mock_account, transactions)

    mock_tempfile.assert_called_once() # Check it was called
    assert mock_tempfile.call_args[1]['suffix'] == ".csv" # Check suffix

    mock_csv_writer.assert_called_once_with(mock_file_io)

    # Check the returned content (from the mocked open)
    assert csv_content == "dummy csv content"
    mock_builtin_open.assert_called_with("dummy_temp_file.csv", "r", encoding="utf-8")
    mock_os_unlink.assert_called_once_with("dummy_temp_file.csv")

# --- Test create_xml_export ---
def test_create_xml_export():
    mock_user = MagicMock(full_name="XML User", email="xml@example.com")
    mock_currency = MagicMock(code="EUR")
    mock_account = MagicMock(id=2, currency=mock_currency, balance=2000.0)
    mock_tx = MagicMock(id=201, timestamp=datetime(2023,2,1,12,0,0), description="XML transaction", source_account_id=2, source_amount=75.0, destination_amount=70.0)
    transactions = [mock_tx]

    xml_bytes = create_xml_export(mock_user, mock_account, transactions)
    assert isinstance(xml_bytes, bytes)

    # Parse the XML and check some values
    root = ET.fromstring(xml_bytes.decode('utf-8'))
    assert root.tag == "EstadoDeCuenta"
    assert root.find("Usuario/Nombre").text == "XML User"
    assert root.find("Cuenta/ID").text == "2"
    assert root.find("Cuenta/Moneda").text == "EUR"
    assert root.find("Transacciones/Transaccion/ID").text == "201"
    assert root.find("Transacciones/Transaccion/Monto").text == "-75.0" # Outgoing

# --- Test send_account_statement ---
@patch('services.email_service.send_email')
@patch('services.email_service.create_csv_export')
@patch('services.email_service.create_xml_export')
def test_send_account_statement_csv(mock_create_xml, mock_create_csv, mock_send_email):
    mock_send_email.return_value = True
    mock_create_csv.return_value = "csv data"

    mock_user = MagicMock(full_name="Statement User", email="statement@example.com")
    mock_currency = MagicMock(code="GBP")
    # The account object needs a 'user' attribute that points back to mock_user for the export functions
    mock_account = MagicMock(id=3, currency=mock_currency, balance=500.0, user=mock_user)
    transactions = [MagicMock()]

    result = send_account_statement(mock_user.email, mock_user.full_name, mock_account, transactions, fmt="csv")

    assert result is True
    mock_create_csv.assert_called_once_with(mock_user, mock_account, transactions)
    mock_create_xml.assert_not_called()

    mock_send_email.assert_called_once()
    args, kwargs = mock_send_email.call_args
    assert args[0] == mock_user.email # to_email
    assert f"Cuenta en {mock_currency.code}" in args[1] # subject
    assert "formato CSV" in args[2] # body

    attachments = args[3]
    assert len(attachments) == 1
    filename = list(attachments.keys())[0]
    assert filename.startswith(f"estado_cuenta_{mock_account.id}")
    assert filename.endswith(".csv")
    assert attachments[filename] == "csv data"

@patch('services.email_service.send_email')
@patch('services.email_service.create_csv_export')
@patch('services.email_service.create_xml_export')
def test_send_account_statement_xml(mock_create_xml, mock_create_csv, mock_send_email):
    mock_send_email.return_value = True
    mock_create_xml.return_value = b"<xml_data/>"

    mock_user = MagicMock(full_name="Statement User", email="statement@example.com")
    mock_currency = MagicMock(code="JPY")
    mock_account = MagicMock(id=4, currency=mock_currency, balance=10000.0, user=mock_user)
    transactions = []

    result = send_account_statement(mock_user.email, mock_user.full_name, mock_account, transactions, fmt="xml")

    assert result is True
    mock_create_xml.assert_called_once_with(mock_user, mock_account, transactions)
    mock_create_csv.assert_not_called()

    args, kwargs = mock_send_email.call_args
    assert "formato XML" in args[2] # body
    attachments = args[3]
    filename = list(attachments.keys())[0]
    assert filename.endswith(".xml")
    assert attachments[filename] == b"<xml_data/>"


def test_send_account_statement_unsupported_format(capsys): # Add capsys if it prints error
    mock_user = MagicMock()
    mock_account = MagicMock(currency=MagicMock(code="AUD"))
    with pytest.raises(ValueError, match="Formato no soportado: pdf"):
        send_account_statement("e@e.com", "N", mock_account, [], fmt="pdf")

# Test SMTP_PASSWORD with non-breaking space (NBSP)
# This tests if normalize_text is correctly applied to SMTP_PASSWORD in send_email
@patch('services.email_service.smtplib.SMTP')
def test_send_email_password_with_nbsp(mock_smtp_constructor, monkeypatch):
    # Override SMTP_PASSWORD for this specific test
    nbsp_password = "test\xa0password" # Password with NBSP
    monkeypatch.setattr(email_service, 'SMTP_PASSWORD', nbsp_password)

    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance

    send_email("r@e.com", "Sub", "<p>Body</p>")

    # normalize_text should convert NBSP to space for login
    expected_clean_password = "test password"
    mock_smtp_instance.login.assert_called_once_with(TEST_SMTP_USERNAME, expected_clean_password)

    # Restore original for other tests if not using autouse fixture for this specific patch
    # (autouse=True on mock_config_values handles general restoration)

# Test normalize_text with various inputs
@pytest.mark.parametrize("input_text, expected_output", [
    ("Hello\u00A0World", "Hello World"),  # NBSP
    ("Caf\u0065\u0301", "Café"),          # e + combining acute -> é
    ("Bj\u00F8rn", "Bjørn"),             # Already NFC
    ("", ""),                            # Empty string
    (None, ""),                          # None input
    ("  Spaces  ", "  Spaces  "),        # Leading/trailing spaces preserved
    ("Text\r\nWith\nNewlines", "Text\r\nWith\nNewlines") # Newlines preserved
])
def test_normalize_text_parametrized(input_text, expected_output):
    assert normalize_text(input_text) == expected_output


# Test specific attachment headers
@patch('services.email_service.smtplib.SMTP')
def test_send_email_attachment_headers(mock_smtp_constructor):
    mock_smtp_instance = MagicMock()
    mock_smtp_constructor.return_value.__enter__.return_value = mock_smtp_instance

    attachments = {
        "data.csv": "col1,col2\nval1,val2",
        "image.xml": "<data></data>", # Using .xml to test that type
        "doc.pdf": b"%PDF-1.4..." # Some binary data
    }
    send_email("r@e.com", "Attach Test", "<p>Test</p>", attachments)

    # Get the message parts from the sendmail call
    # This is complex because the message is a MIMEMultipart object
    # We'd need to parse the message string or mock MIMEApplication more deeply.
    # For simplicity, we assume that if MIMEApplication is called with right params, it works.
    # The test for this would involve mocking MIMEApplication and checking its `add_header` calls.

    # Let's try to assert on the `add_header` calls of the mocked MIMEApplication instance
    # This requires patching MIMEApplication
    with patch('services.email_service.MIMEApplication') as mock_mime_app_constructor:
        mock_mime_instance_csv = MagicMock()
        mock_mime_instance_xml = MagicMock()
        mock_mime_instance_pdf = MagicMock()
        # Simulate different instances for different attachments
        mock_mime_app_constructor.side_effect = [mock_mime_instance_csv, mock_mime_instance_xml, mock_mime_instance_pdf]

        send_email("r@e.com", "Attach Test", "<p>Test</p>", attachments)

        # Check calls for CSV
        mock_mime_instance_csv.add_header.assert_any_call('Content-Disposition', 'attachment', filename='data.csv')
        mock_mime_instance_csv.add_header.assert_any_call('Content-Type', 'text/csv; charset=utf-8')

        # Check calls for XML
        mock_mime_instance_xml.add_header.assert_any_call('Content-Disposition', 'attachment', filename='image.xml')
        mock_mime_instance_xml.add_header.assert_any_call('Content-Type', 'application/xml; charset=utf-8')

        # Check calls for PDF (default MIME type, no special Content-Type header added by our code)
        mock_mime_instance_pdf.add_header.assert_any_call('Content-Disposition', 'attachment', filename='doc.pdf')
        # Ensure the specific Content-Type for CSV/XML was *not* called for PDF

        # Check that the specific content type was not added for pdf
        pdf_header_calls = [call[0] for call in mock_mime_instance_pdf.add_header.call_args_list]
        assert ('Content-Type', 'text/csv; charset=utf-8') not in pdf_header_calls
        assert ('Content-Type', 'application/xml; charset=utf-8') not in pdf_header_calls
