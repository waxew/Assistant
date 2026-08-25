import unittest

from cryptography.fernet import Fernet

from app.security import SecretRedactionFilter, TokenCipher, token_fingerprint


class SecurityTests(unittest.TestCase):
    def test_token_round_trip(self) -> None:
        cipher = TokenCipher(Fernet.generate_key().decode())
        encrypted = cipher.encrypt("123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_123")
        self.assertNotIn("123456789", encrypted)
        self.assertEqual(cipher.decrypt(encrypted), "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_123")

    def test_fingerprint_is_stable(self) -> None:
        self.assertEqual(token_fingerprint("a"), token_fingerprint("a"))
        self.assertNotEqual(token_fingerprint("a"), token_fingerprint("b"))

    def test_redaction(self) -> None:
        value = SecretRedactionFilter._redact("token=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_123")
        self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUVWXYZ", value)


if __name__ == "__main__":
    unittest.main()
