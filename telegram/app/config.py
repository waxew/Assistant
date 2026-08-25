from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Small dependency-free .env loader; real environment variables win."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _ids(name: str) -> frozenset[int]:
    result: set[int] = set()
    for part in os.getenv(name, "").split(","):
        part = part.strip()
        if part:
            result.add(int(part))
    return frozenset(result)


@dataclass(frozen=True, slots=True)
class Settings:
    builder_bot_token: str
    super_admin_ids: frozenset[int]
    token_encryption_key: str
    database_url: str
    public_base_url: str
    web_host: str
    web_port: int
    trial_days: int
    subscription_days: int
    monthly_subscription_price_toman: int
    customer_setup_price_toman: int
    referral_reward_toman: int
    builder_card_number: str
    builder_card_holder: str
    builder_support_account: str
    app_env: str
    log_level: str

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        settings = cls(
            builder_bot_token=os.getenv("BUILDER_BOT_TOKEN", "").strip(),
            super_admin_ids=_ids("SUPER_ADMIN_IDS"),
            token_encryption_key=os.getenv("TOKEN_ENCRYPTION_KEY", "").strip(),
            database_url=os.getenv(
                "DATABASE_URL", "sqlite+aiosqlite:///./data/store_builder.db"
            ).strip(),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
            web_host=os.getenv("WEB_HOST", "0.0.0.0"),  # noqa: S104 - container listener
            web_port=_int("WEB_PORT", 8080),
            trial_days=_int("TRIAL_DAYS", 7),
            subscription_days=_int("SUBSCRIPTION_DAYS", 30),
            monthly_subscription_price_toman=_int("MONTHLY_SUBSCRIPTION_PRICE_TOMAN", 100_000),
            customer_setup_price_toman=_int("CUSTOMER_SETUP_PRICE_TOMAN", 100_000),
            referral_reward_toman=_int("REFERRAL_REWARD_TOMAN", 20_000),
            builder_card_number=os.getenv("BUILDER_CARD_NUMBER", "").strip(),
            builder_card_holder=os.getenv("BUILDER_CARD_HOLDER", "").strip(),
            builder_support_account=os.getenv("BUILDER_SUPPORT_ACCOUNT", "@support").strip(),
            app_env=os.getenv("APP_ENV", "development").strip(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper().strip(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.builder_bot_token or ":" not in self.builder_bot_token:
            raise ValueError("BUILDER_BOT_TOKEN is missing or invalid")
        if not self.super_admin_ids:
            raise ValueError("SUPER_ADMIN_IDS must contain at least one Telegram user ID")
        if not self.token_encryption_key:
            raise ValueError("TOKEN_ENCRYPTION_KEY is required; run scripts/generate_key.py")
        if self.is_production and not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
        if self.trial_days < 0 or self.subscription_days <= 0:
            raise ValueError("Subscription day settings are invalid")
