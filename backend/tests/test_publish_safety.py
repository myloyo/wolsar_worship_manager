import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", [".env", "private.pem", "credentials.txt"])
def test_publish_check_rejects_secrets_without_printing_values(tmp_path: Path, name: str) -> None:
    # Arrange
    script = Path(__file__).resolve().parents[2] / "deploy" / "check_publish.py"
    target = tmp_path / "deploy" / "check_publish.py"
    target.parent.mkdir()
    target.write_bytes(script.read_bytes())
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    secret = "sk-" + "x" * 40
    (tmp_path / name).write_text(secret, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--all"], check=True)

    # Act
    result = subprocess.run(
        [sys.executable, str(target)], capture_output=True, text=True, check=False
    )

    # Assert
    assert result.returncode == 1
    assert name in result.stdout
    assert secret not in result.stdout + result.stderr


def test_publish_check_allows_placeholder_environment_templates(tmp_path: Path) -> None:
    # Arrange
    script = Path(__file__).resolve().parents[2] / "deploy" / "check_publish.py"
    target = tmp_path / "deploy" / "check_publish.py"
    target.parent.mkdir()
    target.write_bytes(script.read_bytes())
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    for name in (".env.example", ".env.test.example"):
        (tmp_path / name).write_text("JWT_SECRET=replace-with-random-secret\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--all"], check=True)

    # Act
    result = subprocess.run(
        [sys.executable, str(target)], capture_output=True, text=True, check=False
    )

    # Assert
    assert result.returncode == 0
    assert "Publish check passed" in result.stdout
