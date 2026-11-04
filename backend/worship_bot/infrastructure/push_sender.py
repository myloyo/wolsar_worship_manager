import json
import logging
from urllib.parse import urlsplit

from pywebpush import WebPushException, webpush

from worship_bot.config import Settings

logger = logging.getLogger(__name__)


def valid_push_endpoint(endpoint: str) -> bool:
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ""
        port = url.port
    except ValueError:
        return False
    return (
        url.scheme == "https"
        and not url.username
        and not url.password
        and port in (None, 443)
        and not url.fragment
        and (
            host
            in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
            or host.endswith(".notify.windows.com")
        )
    )


def send_push(
    endpoint: str, p256dh: str, auth: str, message: dict[str, str], settings: Settings
) -> str:
    if not valid_push_endpoint(endpoint):
        return "expired"
    if not settings.vapid_private_key:
        return "retry"
    try:
        webpush(
            subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
            data=json.dumps(message, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key.get_secret_value(),
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
            ttl=86400,
        )
    except WebPushException as error:
        logger.warning(
            "push.provider_failed",
            extra={
                "provider": "web_push",
                "error_type": type(error).__name__,
                "status_code": error.response.status_code if error.response is not None else None,
            },
        )
        if error.response is not None and error.response.status_code in (404, 410):
            return "expired"
        return "retry"
    except Exception as error:
        logger.warning(
            "push.provider_failed",
            extra={"provider": "web_push", "error_type": type(error).__name__},
        )
        return "retry"
    return "sent"
