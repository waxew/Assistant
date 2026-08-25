import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

from app.config import Settings


class ConfigTests(unittest.TestCase):
    def test_minimal_valid_configuration(self) -> None:
        values = {
            "BUILDER_BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE",
            "SUPER_ADMIN_IDS": "123,456",
            "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "APP_ENV": "test",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.super_admin_ids, frozenset({123, 456}))
        self.assertEqual(settings.trial_days, 7)

    def test_production_requires_https(self) -> None:
        values = {
            "BUILDER_BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE",
            "SUPER_ADMIN_IDS": "123",
            "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "APP_ENV": "production",
            "PUBLIC_BASE_URL": "http://example.com",
        }
        with patch.dict(os.environ, values, clear=True), self.assertRaises(ValueError):
            Settings.from_env()


if __name__ == "__main__":
    unittest.main()
