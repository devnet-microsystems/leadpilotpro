"""
provider_adapter.py

Defines the Provider abstraction and typed result model for outbound execution.
Includes MockAdapter for DRY-RUN testing.
"""
from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any
import enum
import time

class TransportState(str, enum.Enum):
    REQUEST_NOT_SENT = "REQUEST_NOT_SENT"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    REQUEST_SENT_OUTCOME_UNKNOWN = "REQUEST_SENT_OUTCOME_UNKNOWN"
    DELIVERED = "DELIVERED"
    BOUNCED = "BOUNCED"

@dataclass
class ProviderResult:
    state: TransportState
    provider_request_id: Optional[str] = None
    last_error: Optional[str] = None
    # For simulating rate limits or wait times
    retry_after_seconds: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class EmailProvider(Protocol):
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        idempotency_metadata: Dict[str, str]
    ) -> ProviderResult:
        ...

class MockAdapter:
    """
    Deterministic DRY-RUN adapter with ZERO network access.
    Can simulate specific network states based on the recipient email.
    """
    def __init__(self):
        self.call_history = []

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        idempotency_metadata: Dict[str, str]
    ) -> ProviderResult:
        self.call_history.append({
            "to": to_email,
            "subject": subject,
            "body": body_text,
            "metadata": idempotency_metadata
        })

        if "dns-fail@" in to_email or "conn-fail@" in to_email:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="Simulated network connection failure"
            )

        if "timeout-before@" in to_email:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="Timeout before transmission"
            )

        if "timeout-after@" in to_email:
            return ProviderResult(
                state=TransportState.REQUEST_SENT_OUTCOME_UNKNOWN,
                last_error="Timeout waiting for provider response"
            )

        if "rate-limit@" in to_email:
            return ProviderResult(
                state=TransportState.PROVIDER_REJECTED,
                last_error="429 Too Many Requests",
                retry_after_seconds=60
            )

        if "auth-fail@" in to_email:
            return ProviderResult(
                state=TransportState.PROVIDER_REJECTED,
                last_error="401 Unauthorized"
            )

        if "malformed@" in to_email:
            return ProviderResult(
                state=TransportState.PROVIDER_REJECTED,
                last_error="400 Bad Request"
            )

        if "bounce@" in to_email:
            return ProviderResult(
                state=TransportState.PROVIDER_REJECTED,
                last_error="Recipient Rejected"
            )
            
        # Default Success
        return ProviderResult(
            state=TransportState.PROVIDER_ACCEPTED,
            provider_request_id=f"mock-{int(time.time() * 1000)}"
        )
