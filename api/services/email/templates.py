"""Rendered bodies for transactional emails."""


def build_password_reset_email(reset_url: str, expiry_minutes: int) -> tuple[str, str]:
    """Return ``(text_body, html_body)`` for the password-reset email."""
    text_body = (
        "We received a request to reset your Bellerophone password.\n\n"
        f"Reset your password using the link below (valid for {expiry_minutes} "
        "minutes):\n\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email — your "
        "password won't change."
    )

    html_body = f"""\
<!doctype html>
<html>
  <body style="font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #111;">
    <h2>Reset your Bellerophone password</h2>
    <p>We received a request to reset your password.</p>
    <p>
      <a href="{reset_url}"
         style="display: inline-block; padding: 10px 18px; background: #111; color: #fff; text-decoration: none; border-radius: 6px;">
        Reset password
      </a>
    </p>
    <p style="color: #555; font-size: 13px;">
      This link is valid for {expiry_minutes} minutes. If the button doesn't work,
      copy and paste this URL into your browser:
    </p>
    <p style="word-break: break-all; font-size: 13px;"><a href="{reset_url}">{reset_url}</a></p>
    <p style="color: #555; font-size: 13px;">
      If you didn't request this, you can safely ignore this email — your password won't change.
    </p>
  </body>
</html>"""

    return text_body, html_body
