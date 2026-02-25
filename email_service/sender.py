"""Email sender — Mandrill (preferred) with SendGrid fallback."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Result of a single email send attempt."""
    success: bool
    recipient: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: Optional[datetime] = None


@dataclass
class BulkSendResult:
    """Result of a bulk email send."""
    total_sent: int = 0
    total_failed: int = 0
    results: List[SendResult] = field(default_factory=list)


class MandrillSender:
    """Send transactional emails via Mailchimp Mandrill."""

    def __init__(self):
        self._client = None
        if settings.mandrill_api_key:
            try:
                import mailchimp_transactional as MailchimpTransactional
                self._client = MailchimpTransactional.Client(api_key=settings.mandrill_api_key)
                self._client.users.ping()
                logger.info("Mandrill client initialized and connected")
            except ImportError:
                logger.warning("mailchimp-transactional package not installed — Mandrill disabled")
            except Exception as e:
                logger.error(f"Mandrill connection failed: {e}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def send(self, to_email: str, subject: str, html_content: str, text_content: str) -> SendResult:
        if not self.is_configured:
            return SendResult(success=False, recipient=to_email, error="Mandrill not configured")

        try:
            message = {
                "from_email": settings.email_from_address,
                "from_name": settings.resolved_email_from_name,
                "subject": subject,
                "html": html_content,
                "text": text_content,
                "to": [{"email": to_email, "type": "to"}],
                "track_opens": True,
                "track_clicks": True,
            }
            result = self._client.messages.send({"message": message})

            if result and result[0]["status"] in ("sent", "queued"):
                msg_id = result[0].get("_id", "")
                logger.info(f"Mandrill: sent to {to_email} (id: {msg_id})")
                return SendResult(
                    success=True, recipient=to_email,
                    message_id=msg_id, sent_at=datetime.utcnow(),
                )
            else:
                error = result[0].get("reject_reason", "Unknown") if result else "No response"
                logger.error(f"Mandrill: rejected for {to_email}: {error}")
                return SendResult(success=False, recipient=to_email, error=error)

        except Exception as e:
            logger.error(f"Mandrill send error for {to_email}: {e}")
            return SendResult(success=False, recipient=to_email, error=str(e))


class SendGridSender:
    """Send emails via SendGrid (fallback provider)."""

    def __init__(self):
        self._client = None
        if settings.sendgrid_api_key:
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(api_key=settings.sendgrid_api_key)
                logger.info("SendGrid client initialized")
            except ImportError:
                logger.warning("sendgrid package not installed — SendGrid disabled")
            except Exception as e:
                logger.error(f"SendGrid init failed: {e}")

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def send(self, to_email: str, subject: str, html_content: str, text_content: str) -> SendResult:
        if not self.is_configured:
            return SendResult(success=False, recipient=to_email, error="SendGrid not configured")

        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content

            message = Mail(
                from_email=Email(settings.email_from_address, settings.resolved_email_from_name),
                to_emails=To(to_email),
                subject=subject,
            )
            message.add_content(Content("text/plain", text_content))
            message.add_content(Content("text/html", html_content))

            response = self._client.send(message)

            if response.status_code in (200, 201, 202):
                msg_id = response.headers.get("X-Message-Id", "")
                logger.info(f"SendGrid: sent to {to_email} (id: {msg_id})")
                return SendResult(
                    success=True, recipient=to_email,
                    message_id=msg_id, sent_at=datetime.utcnow(),
                )
            else:
                error = f"Status {response.status_code}: {response.body}"
                logger.error(f"SendGrid: failed for {to_email}: {error}")
                return SendResult(success=False, recipient=to_email, error=error)

        except Exception as e:
            logger.error(f"SendGrid send error for {to_email}: {e}")
            return SendResult(success=False, recipient=to_email, error=str(e))


class EmailSender:
    """Unified email sender — tries Mandrill first, falls back to SendGrid."""

    def __init__(self):
        self._mandrill = MandrillSender()
        self._sendgrid = SendGridSender()

        if self._mandrill.is_configured:
            self._provider = self._mandrill
            logger.info("Email provider: Mandrill")
        elif self._sendgrid.is_configured:
            self._provider = self._sendgrid
            logger.info("Email provider: SendGrid")
        else:
            self._provider = None
            logger.warning("No email provider configured — email sending disabled")

    @property
    def is_configured(self) -> bool:
        return self._provider is not None

    @property
    def provider_name(self) -> str:
        if self._mandrill.is_configured:
            return "mandrill"
        elif self._sendgrid.is_configured:
            return "sendgrid"
        return "none"

    def send(
        self, to_email: str, subject: str, html_content: str, text_content: str,
    ) -> SendResult:
        """Send a single email via the active provider."""
        if not self.is_configured:
            logger.warning(f"Email not sent to {to_email} — no provider configured")
            return SendResult(
                success=False, recipient=to_email,
                error="No email provider configured",
            )
        return self._provider.send(to_email, subject, html_content, text_content)

    def send_digest(
        self, to_email: str, recipient_org: dict, matches: list,
    ) -> SendResult:
        """Build and send a digest email."""
        from email_service.builder import email_builder

        digest = email_builder.build_digest(recipient_org, matches)
        return self.send(
            to_email=to_email,
            subject=digest["subject"],
            html_content=digest["html"],
            text_content=digest["text"],
        )

    def send_bulk_digests(self, digests: List[dict]) -> BulkSendResult:
        """Send digest emails to multiple recipients."""
        bulk_result = BulkSendResult()

        for item in digests:
            result = self.send_digest(
                to_email=item["to_email"],
                recipient_org=item["recipient_org"],
                matches=item["matches"],
            )
            bulk_result.results.append(result)
            if result.success:
                bulk_result.total_sent += 1
            else:
                bulk_result.total_failed += 1

        logger.info(
            f"Bulk send complete: {bulk_result.total_sent} sent, "
            f"{bulk_result.total_failed} failed (via {self.provider_name})"
        )
        return bulk_result


# Singleton instance
email_sender = EmailSender()
