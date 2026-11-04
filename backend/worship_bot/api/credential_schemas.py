import re
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class PasswordLogin(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", normalized):
            raise ValueError("Логин: 3–64 латинских символа, цифры, точка, дефис или подчёркивание")
        return normalized


class PasswordRegistration(PasswordLogin):
    password: SecretStr = Field(min_length=10, max_length=128)


class CredentialsUpdate(PasswordRegistration):
    current_password: SecretStr | None = Field(default=None, max_length=128)


class CredentialsRead(BaseModel):
    login: str | None
    has_password: bool


class SiteRegistration(PasswordRegistration):
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    consent_approved: Literal[True]

    @field_validator("name", "surname")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Укажите имя и фамилию")
        return value.strip()
