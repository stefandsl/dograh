"""Outbound transactional email.

Currently backs the local (OSS) password-reset flow. Email is sent over SMTP
when ``SMTP_HOST`` is configured; otherwise the message is logged so that
self-hosted deployments without a mail server can still complete the flow (the
reset link appears in the API logs).
"""

from api.services.email.sender import is_smtp_configured, send_email
from api.services.email.templates import build_password_reset_email

__all__ = [
    "send_email",
    "is_smtp_configured",
    "build_password_reset_email",
]
