import pytest
import smtplib
import socket
from unittest.mock import patch, MagicMock

from infomaniak_adapter import InfomaniakSMTPAdapter
from provider_adapter import TransportState

@pytest.fixture
def adapter():
    # dry_run = False so we can test the mocked SMTP flow
    return InfomaniakSMTPAdapter(dry_run=False)

def test_infomaniak_dry_run():
    dry_adapter = InfomaniakSMTPAdapter(dry_run=True)
    result = dry_adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_ACCEPTED
    assert result.provider_request_id == "dryrun-infomaniak"

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_validate_connection(mock_smtp):
    adapter = InfomaniakSMTPAdapter(dry_run=False)
    assert adapter.validate_connection() is True

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_validate_connection_failure(mock_smtp):
    mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
    adapter = InfomaniakSMTPAdapter(dry_run=False)
    assert adapter.validate_connection() is False

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_send_success(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    result = adapter.send_email("test@example.com", "Subj", "Body", {"campaign_id": "1"})
    
    assert result.state == TransportState.PROVIDER_ACCEPTED
    assert mock_instance.starttls.called
    assert mock_instance.login.called
    assert mock_instance.send_message.called
    
    # Check metadata headers are attached to message
    msg = mock_instance.send_message.call_args[0][0]
    assert msg["X-LeadPilot-Campaign_id"] == "1"

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_auth_failure(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "SMTP_AUTH_FAILURE" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_connection_refused(mock_smtp, adapter):
    mock_smtp.side_effect = ConnectionRefusedError("Connection refused")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_NOT_SENT
    assert "Connection Refused" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_dns_failure(mock_smtp, adapter):
    mock_smtp.side_effect = socket.gaierror("Name or service not known")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_NOT_SENT
    assert "DNS Failure" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_timeout_before_transmission(mock_smtp, adapter):
    mock_smtp.side_effect = socket.timeout("timeout")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_NOT_SENT
    assert "Timeout before transmission" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_timeout_after_transmission_started(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.send_message.side_effect = socket.timeout("timeout")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_SENT_OUTCOME_UNKNOWN
    assert "AMBIGUOUS" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_smtp_temporary_failure(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.send_message.side_effect = smtplib.SMTPDataError(451, b"Temporary failure")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "451 Temporary Failure" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_smtp_permanent_failure(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.send_message.side_effect = smtplib.SMTPDataError(554, b"Transaction failed")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "554 Permanent Failure" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_recipient_rejected(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.send_message.side_effect = smtplib.SMTPRecipientsRefused({"test@example.com": (550, b"User unknown")})
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "Recipient Rejected" in result.last_error

@patch("infomaniak_adapter.smtplib.SMTP")
def test_infomaniak_sender_refused(mock_smtp, adapter):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    mock_instance.send_message.side_effect = smtplib.SMTPSenderRefused(550, b"Sender denied", "sender@example.com")
    
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "SMTPSenderRefused" in result.last_error
