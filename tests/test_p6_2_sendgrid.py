import pytest
import requests
from unittest.mock import patch, Mock
from provider_adapter import TransportState
from sendgrid_adapter import SendGridAdapter

@pytest.fixture
def adapter():
    return SendGridAdapter(api_key="SG.fake", dry_run=True)

def test_sendgrid_live_mode_disabled():
    with pytest.raises(RuntimeError, match="Live mode is completely disabled"):
        live_adapter = SendGridAdapter(api_key="SG.fake", dry_run=False)
        live_adapter.send_email("test@example.com", "Subject", "Body", {})

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_202_accepted(mock_post, adapter):
    mock_response = Mock()
    mock_response.status_code = 202
    mock_response.headers = {"X-Message-Id": "msg-123"}
    mock_post.return_value = mock_response

    result = adapter.send_email("test@example.com", "Subj", "Body", {"campaign_id": "1"})
    assert result.state == TransportState.PROVIDER_ACCEPTED
    assert result.provider_request_id == "msg-123"
    
    # Verify custom args are passed correctly
    kwargs = mock_post.call_args.kwargs
    payload = kwargs["json"]
    assert payload["personalizations"][0]["custom_args"]["campaign_id"] == "1"

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_429_rate_limit(mock_post, adapter):
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "120"}
    mock_post.return_value = mock_response

    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert result.retry_after_seconds == 120
    assert "429" in result.last_error

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_401_auth_failure(mock_post, adapter):
    mock_response = Mock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "401" in result.last_error

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_400_bad_request(mock_post, adapter):
    mock_response = Mock()
    mock_response.status_code = 400
    mock_post.return_value = mock_response

    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.PROVIDER_REJECTED
    assert "400" in result.last_error

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_connection_timeout(mock_post, adapter):
    mock_post.side_effect = requests.exceptions.ConnectTimeout("Connect timeout")
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_NOT_SENT
    assert "ConnectTimeout" in result.last_error

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_read_timeout_is_ambiguous(mock_post, adapter):
    mock_post.side_effect = requests.exceptions.ReadTimeout("Read timeout")
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_SENT_OUTCOME_UNKNOWN
    assert "AMBIGUOUS" in result.last_error

@patch("sendgrid_adapter.requests.post")
def test_sendgrid_network_failure(mock_post, adapter):
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    result = adapter.send_email("test@example.com", "Subj", "Body", {})
    assert result.state == TransportState.REQUEST_NOT_SENT
    assert "ConnectionError" in result.last_error
