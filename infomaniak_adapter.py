"""
infomaniak_adapter.py

SMTP Adapter for Infomaniak.
Implements the EmailProvider protocol.
"""
import smtplib
from email.message import EmailMessage
import os
import socket
import logging
from typing import Dict, Any

from provider_adapter import EmailProvider, ProviderResult, TransportState

logger = logging.getLogger(__name__)

class InfomaniakSMTPAdapter(EmailProvider):
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.smtp_host = os.environ.get("SMTP_HOST", "mail.infomaniak.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.username = os.environ.get("SMTP_USERNAME", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")

    def validate_connection(self) -> bool:
        """
        Validates SMTP connection and authentication without sending an email.
        """
        if self.dry_run:
            return True
            
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=5) as server:
                server.starttls()
                server.login(self.username, self.password)
                return True
        except Exception as e:
            logger.error(f"Connection validation failed: {type(e).__name__}")
            return False

    def send_test_message(self, test_recipient: str) -> ProviderResult:
        """
        Controlled test path for exactly ONE message addressed to the operator's mailbox.
        """
        return self.send_email(
            to_email=test_recipient,
            subject="Test LeadPilot",
            body_text="This is a controlled test message from LeadPilot.",
            idempotency_metadata={"type": "test_message"}
        )

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        idempotency_metadata: Dict[str, str]
    ) -> ProviderResult:
        if self.dry_run:
            # Deterministic dry-run without connection
            return ProviderResult(
                state=TransportState.PROVIDER_ACCEPTED,
                provider_request_id="dryrun-infomaniak"
            )

        msg = EmailMessage()
        msg.set_content(body_text)
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = to_email
        
        # Add metadata as headers (e.g. X-LeadPilot-Campaign-Id)
        for k, v in idempotency_metadata.items():
            msg[f"X-LeadPilot-{k.capitalize()}"] = v

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=5) as server:
                server.starttls()
                server.login(self.username, self.password)
                # Set a smaller timeout for the actual send operation
                server.timeout = 5
                
                try:
                    server.send_message(msg)
                    return ProviderResult(
                        state=TransportState.PROVIDER_ACCEPTED,
                        provider_request_id=None # SMTP standard doesn't guarantee a standard tracking ID on accept
                    )
                except smtplib.SMTPSenderRefused as e:
                    return ProviderResult(state=TransportState.PROVIDER_REJECTED, last_error=f"SMTPSenderRefused (5xx): Configuration error")
                except smtplib.SMTPRecipientsRefused as e:
                    return ProviderResult(state=TransportState.PROVIDER_REJECTED, last_error=f"SMTPRecipientsRefused (5xx): Recipient Rejected")
                except smtplib.SMTPDataError as e:
                    # 4xx or 5xx
                    code = e.smtp_code
                    if 400 <= code < 500:
                        return ProviderResult(state=TransportState.PROVIDER_REJECTED, last_error=f"{code} Temporary Failure")
                    else:
                        return ProviderResult(state=TransportState.PROVIDER_REJECTED, last_error=f"{code} Permanent Failure")
                except socket.timeout:
                    # Timeout during the data transmission is ambiguous
                    return ProviderResult(
                        state=TransportState.REQUEST_SENT_OUTCOME_UNKNOWN,
                        last_error="Timeout after transmission started (AMBIGUOUS)"
                    )
                    
        except smtplib.SMTPAuthenticationError:
            return ProviderResult(
                state=TransportState.PROVIDER_REJECTED,
                last_error="SMTP_AUTH_FAILURE"
            )
        except (smtplib.SMTPConnectError, ConnectionRefusedError):
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="Connection Refused"
            )
        except socket.gaierror:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="DNS Failure"
            )
        except socket.timeout:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="Timeout before transmission (connection timeout)"
            )
        except Exception as e:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error=f"Unknown exception: {type(e).__name__}"
            )
