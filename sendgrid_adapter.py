import requests
import time
from typing import Dict, Any
from provider_adapter import EmailProvider, ProviderResult, TransportState

class SendGridAdapter(EmailProvider):
    def __init__(self, api_key: str, dry_run: bool = True):
        self.api_key = api_key
        self.dry_run = dry_run # In P6.2 this MUST be True
        self.base_url = "https://api.sendgrid.com/v3/mail/send"
        
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        idempotency_metadata: Dict[str, str]
    ) -> ProviderResult:
        if not self.dry_run:
            raise RuntimeError("Live mode is completely disabled in P6.2")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "custom_args": idempotency_metadata
                }
            ],
            "from": {"email": "outbound@example.com"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body_text}
            ]
        }

        try:
            # We use a short timeout because if it drops after transmission, it's ambiguous
            resp = requests.post(self.base_url, json=payload, headers=headers, timeout=(3.0, 5.0))
            
            if resp.status_code == 202:
                # SendGrid Mail Send v3 returns 202 Accepted on success
                return ProviderResult(
                    state=TransportState.PROVIDER_ACCEPTED,
                    provider_request_id=resp.headers.get("X-Message-Id", "unknown")
                )
            elif resp.status_code == 429:
                return ProviderResult(
                    state=TransportState.PROVIDER_REJECTED,
                    last_error="429 Too Many Requests",
                    retry_after_seconds=int(resp.headers.get("Retry-After", 60))
                )
            elif resp.status_code in (401, 403):
                return ProviderResult(
                    state=TransportState.PROVIDER_REJECTED,
                    last_error=f"{resp.status_code} Auth/Config Failure"
                )
            elif resp.status_code == 400:
                return ProviderResult(
                    state=TransportState.PROVIDER_REJECTED,
                    last_error="400 Bad Request"
                )
            else:
                return ProviderResult(
                    state=TransportState.PROVIDER_REJECTED,
                    last_error=f"Unexpected status: {resp.status_code} {resp.text}"
                )
                
        except requests.exceptions.Timeout as e:
            # Differentiate between connection timeout and read timeout
            if isinstance(e, requests.exceptions.ConnectTimeout):
                return ProviderResult(
                    state=TransportState.REQUEST_NOT_SENT,
                    last_error="ConnectTimeout: Timeout before transmission"
                )
            elif isinstance(e, requests.exceptions.ReadTimeout):
                return ProviderResult(
                    state=TransportState.REQUEST_SENT_OUTCOME_UNKNOWN,
                    last_error="ReadTimeout: Timeout after transmission (AMBIGUOUS)"
                )
            else:
                # Generic timeout
                return ProviderResult(
                    state=TransportState.REQUEST_SENT_OUTCOME_UNKNOWN,
                    last_error="Timeout: AMBIGUOUS"
                )
        except requests.exceptions.ConnectionError:
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error="ConnectionError: Network failure"
            )
        except Exception as e:
            # Catch-all
            return ProviderResult(
                state=TransportState.REQUEST_NOT_SENT,
                last_error=f"Unknown exception: {str(e)}"
            )
