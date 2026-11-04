import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b"),
)
PROHIBITED_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".dump",
    ".sql",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
}
PROHIBITED_PARTS = {
    "node_modules",
    ".venv",
    "venv",
    ".local-tools",
    "backups",
    "bot-data",
    "uploads",
    ".ssh",
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    command = ["git", "-C", str(root), "ls-files", "-z"]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        print("Git repository not initialized. Run git init and git add before this check.")
        return 2
    failed = False
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = Path(raw.decode("utf-8"))
        is_env = path.name == ".env" or (
            path.name.startswith(".env.") and path.name not in {".env.example", ".env.test.example"}
        )
        if (
            is_env
            or path.suffix.lower() in PROHIBITED_SUFFIXES
            or set(path.parts) & PROHIBITED_PARTS
        ):
            print(f"PROHIBITED tracked path: {path.as_posix()}")
            failed = True
            continue
        # Scan Git's index: the bytes that a commit will actually publish.
        staged = subprocess.run(
            ["git", "-C", str(root), "show", f":{path.as_posix()}"],
            capture_output=True,
            check=False,
        )
        if staged.returncode:
            print(f"Cannot read staged file: {path.as_posix()}")
            failed = True
        elif any(pattern.search(staged.stdout) for pattern in SECRET_PATTERNS):
            print(f"POSSIBLE SECRET: {path.as_posix()} (value hidden)")
            failed = True
    print(
        "Publish check failed."
        if failed
        else "Publish check passed. Review staged changes before committing."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
