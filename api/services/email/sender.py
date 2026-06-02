"""SMTP email sender with a log-only fallback.

The actual ``smtplib`` calls are blocking, so they run in a worker thread via
``asyncio.to_thread`` to avoid stalling the event loop.
"""

import asyncio
import smtplib
from email.message import EmailMessage

from loguru import logger

from api.constants import (
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)


def is_smtp_configured() -> bool:
    """True when enough SMTP config is present to attempt delivery."""
    return bool(SMTP_HOST)


def _send_sync(message: EmailMessage) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        if SMTP_USERNAME and SMTP_PASSWORD:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)


async def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> bool:
    """Send an email, or log it when SMTP is not configured.

    Returns ``True`` if the message was handed off to an SMTP server, ``False``
    if it was only logged (no SMTP configured) or delivery failed. Callers in
    the password-reset flow intentionally ignore the result so the response
    doesn't leak whether an account exists.
    """
    if not is_smtp_configured():
        logger.warning(
            "SMTP not configured (SMTP_HOST unset) — not sending email to {to}. "
            "Subject: {subject}\n{body}",
            to=to_email,
            subject=subject,
            body=text_body,
        )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await asyncio.to_thread(_send_sync, message)
        logger.info("Sent email to {to} (subject: {subject})", to=to_email, subject=subject)
        return True
    except Exception:
        logger.exception("Failed to send email to {to}", to=to_email)
        return False
