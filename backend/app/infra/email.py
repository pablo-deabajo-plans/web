from __future__ import annotations

import os

import resend


def send_password_reset_email(to: str, reset_url: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    from_email = os.getenv("FROM_EMAIL", "noreply@gordon-betscanner.com")
    resend.api_key = api_key
    resend.Emails.send({
        "from": from_email,
        "to": [to],
        "subject": "Restablecer contraseña — Gordon BetScanner",
        "html": (
            "<p>Hemos recibido una solicitud para restablecer tu contraseña.</p>"
            f'<p><a href="{reset_url}">Haz clic aquí para restablecer tu contraseña</a></p>'
            "<p>Este enlace caduca en 1 hora. Si no solicitaste este cambio, ignora este correo.</p>"
        ),
    })
