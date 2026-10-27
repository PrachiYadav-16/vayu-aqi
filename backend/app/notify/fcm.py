"""Push delivery via Firebase Cloud Messaging.

Enabled when VAYU_FIREBASE_CREDENTIALS_FILE points at a service-account JSON.
Without it, pushes are logged and the alert still lands in the in-app inbox,
which the PWA polls and can surface as a local browser notification.
"""

from __future__ import annotations

import logging

from app.config import get_settings

log = logging.getLogger(__name__)
_app = None


def _firebase():
    global _app
    if _app is not None:
        return _app
    path = get_settings().firebase_credentials_file
    if not path:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        _app = firebase_admin.initialize_app(credentials.Certificate(path))
        return _app
    except Exception as exc:  # pragma: no cover - depends on credentials
        log.error("Firebase init failed: %s", exc)
        return None


def push_enabled() -> bool:
    return _firebase() is not None


def send(tokens: list[str], title: str, body: str, data: dict | None = None) -> list[str]:
    """Send to device tokens. Returns tokens that FCM reports as invalid so callers can prune them."""
    if not tokens:
        return []
    if _firebase() is None:
        log.info("[push:dev] %s | %s -> %d device(s)", title, body, len(tokens))
        return []
    from firebase_admin import messaging  # pragma: no cover

    msg = messaging.MulticastMessage(  # pragma: no cover
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        webpush=messaging.WebpushConfig(
            notification=messaging.WebpushNotification(icon="/icons/icon-192.png", badge="/icons/badge-72.png"),
            fcm_options=messaging.WebpushFCMOptions(link=(data or {}).get("link", "/alerts")),
        ),
    )
    resp = messaging.send_each_for_multicast(msg)  # pragma: no cover
    bad = []
    for tok, r in zip(tokens, resp.responses):  # pragma: no cover
        if not r.success and r.exception and "registration-token-not-registered" in str(r.exception.code or ""):
            bad.append(tok)
    return bad  # pragma: no cover
