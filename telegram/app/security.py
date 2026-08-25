from __future__ import annotations

import hashlib
import logging
import re

from cryptography.fernet import Fernet, InvalidToken

TOKEN_PATTERN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b")


class TokenCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored bot token cannot be decrypted with the current key") from exc


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SecretRedactionFilter(logging.Filter):
    """Redacts Telegram-style bot tokens from log messages and arguments."""

    @staticmethod
    def _redact(value: object) -> object:
        if isinstance(value, str):
            return TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", value)
        if isinstance(value, tuple):
            return tuple(SecretRedactionFilter._redact(item) for item in value)
        if isinstance(value, dict):
            return {key: SecretRedactionFilter._redact(item) for key, item in value.items()}
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        record.args = self._redact(record.args)
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    redactor = SecretRedactionFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(redactor)
