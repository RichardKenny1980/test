"""Encrypted-at-rest text field used for storing Google OAuth tokens/secrets."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


class EncryptedTextField(models.TextField):
    """A TextField that transparently encrypts/decrypts its value with Fernet.

    Values are encrypted before hitting the database and decrypted on read,
    so OAuth access/refresh tokens are never stored in plaintext.
    """

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        token = get_fernet().encrypt(str(value).encode("utf-8"))
        return token.decode("utf-8")

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Value predates encryption or was written outside this field; return as-is.
            return value
