import base64
import hashlib
import hmac
import secrets


def password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = password_digest(password, salt)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if stored is None:
        password_digest(password, bytes(16))
        return False
    try:
        algorithm, salt, digest = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = password_digest(password, base64.b64decode(salt, validate=True))
        return hmac.compare_digest(actual, base64.b64decode(digest, validate=True))
    except (ValueError, TypeError):
        return False
