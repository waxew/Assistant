from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class DiscountKind(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"


class PriceChangeMode(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"


class PriceDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


def normalize_digits(value: str) -> str:
    return value.translate(PERSIAN_DIGITS)


def parse_positive_int(value: str, *, minimum: int = 1, maximum: int | None = None) -> int:
    cleaned = normalize_digits(value).replace(",", "").replace("٬", "").strip()
    if not re.fullmatch(r"\d+", cleaned):
        raise ValueError("فقط عدد وارد کنید.")
    number = int(cleaned)
    if number < minimum:
        raise ValueError(f"عدد باید حداقل {minimum:,} باشد.")
    if maximum is not None and number > maximum:
        raise ValueError(f"عدد باید حداکثر {maximum:,} باشد.")
    return number


def format_toman(amount: int) -> str:
    return f"{amount:,}"


def discount_amount(price: int, kind: DiscountKind | str, value: int) -> int:
    kind = DiscountKind(kind)
    if price < 0 or value < 0:
        raise ValueError("Price and discount must be non-negative")
    if kind is DiscountKind.FIXED:
        return min(price, value)
    percent = min(value, 100)
    raw = (Decimal(price) * Decimal(percent) / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return min(price, int(raw))


def changed_price(
    price: int,
    *,
    direction: PriceDirection | str,
    mode: PriceChangeMode | str,
    value: int,
) -> int:
    if price < 0 or value < 0:
        raise ValueError("Price and change value must be non-negative")
    direction = PriceDirection(direction)
    mode = PriceChangeMode(mode)
    delta = value
    if mode is PriceChangeMode.PERCENT:
        delta = int(
            (Decimal(price) * Decimal(value) / Decimal(100)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    if direction is PriceDirection.INCREASE:
        return price + delta
    return max(0, price - delta)


def make_tracking_code() -> str:
    # 10 decimal digits, human-friendly and safe to paste into Telegram.
    return "".join(str(secrets.randbelow(10)) for _ in range(10))


def make_referral_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]


def slugify_ascii(value: str, fallback: str = "product") -> str:
    value = normalize_digits(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or fallback


@dataclass(frozen=True, slots=True)
class DiscountPreview:
    base_amount: int
    discount: int

    @property
    def final_amount(self) -> int:
        return max(0, self.base_amount - self.discount)
