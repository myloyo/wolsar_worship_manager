import base64
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / "deploy/env.production.example").read_text(encoding="utf-8")
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_bytes = private_key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    values = {
        "DATABASE_PASSWORD": secrets.token_hex(32),
        "BOT_SERVICE_TOKEN": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_hex(64),
        "VAPID_PRIVATE_KEY": base64.urlsafe_b64encode(private_bytes).rstrip(b"=").decode(),
        "VAPID_PUBLIC_KEY": base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode(),
    }
    lines = [
        f"{line.split('=', 1)[0]}={values[line.split('=', 1)[0]]}"
        if line.split("=", 1)[0] in values
        else line
        for line in template.splitlines()
    ]
    target = root / ".env"
    with target.open("x", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")
    target.chmod(0o600)
    print(
        "Created .env with new database, service, JWT and VAPID keys. Add bot/API tokens manually."
    )


if __name__ == "__main__":
    main()
