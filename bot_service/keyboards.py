import ipaddress
from typing import Any
from urllib.parse import urlsplit


def supports_url_button(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host
    except ValueError:
        return False


def add_web_link(markup: dict[str, Any], label: str, url: str) -> str:
    if supports_url_button(url):
        markup["inline_keyboard"].insert(0, [{"text": label, "url": url}])
        return ""
    return "\n" + label + ": " + url


def menu_keyboard(web_url: str, administrator: bool = False) -> dict[str, Any]:
    rows = [
        [
            {"text": "Моё расписание", "callback_data": "nav:schedule"},
            {"text": "Моя карточка", "callback_data": "nav:profile"},
        ],
        [{"text": "Вступить в команду", "callback_data": "teams"}],
        [
            {
                "text": "Открыть сайт",
                **(
                    {"url": web_url.rstrip("/")}
                    if supports_url_button(web_url)
                    else {"callback_data": "website"}
                ),
            }
        ],
    ]
    if administrator:
        rows.insert(1, [{"text": "Помощник расписания", "callback_data": "nav:plan"}])
    return {"inline_keyboard": rows}


def invitation_keyboard(invitation_id: int) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Подтвердить участие", "callback_data": f"invite:accept:{invitation_id}"},
                {"text": "Не смогу", "callback_data": f"invite:decline:{invitation_id}"},
            ]
        ]
    }


def assignment_keyboard(slot_id: int, revision: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Подтвердить", "callback_data": f"assignment:accept:{slot_id}:{revision}"},
                {
                    "text": "Запросить замену",
                    "callback_data": f"assignment:decline:{slot_id}:{revision}",
                },
            ]
        ]
    }
