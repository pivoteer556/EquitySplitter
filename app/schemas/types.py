"""Shared request-schema types. An email enters the system through one of these, so it is normalized one way."""

import re
from typing import Annotated

from pydantic import AfterValidator, EmailStr

EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+$")


def normalize_email(value: str) -> str:
    """Strip and lowercase, then require one `@` with text on both sides. Lookups and the UNIQUE columns compare
    emails exactly, so every email must be lowercased before it is looked up or stored."""
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email format")
    return email


# Sign-in and self-registration: any `a@b` shape (a wrong address is a 401 or a new account, never a 422 oracle).
NormalizedEmail = Annotated[str, AfterValidator(normalize_email)]
# Addresses an officer types for someone else (officer create, bootstrap, owner invite): also a real email address.
NormalizedEmailStr = Annotated[EmailStr, AfterValidator(normalize_email)]
