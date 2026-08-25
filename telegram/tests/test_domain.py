import unittest

from app.domain import (
    DiscountKind,
    PriceChangeMode,
    PriceDirection,
    changed_price,
    discount_amount,
    normalize_digits,
    parse_positive_int,
    slugify_ascii,
)


class DomainTests(unittest.TestCase):
    def test_normalizes_persian_and_arabic_digits(self) -> None:
        self.assertEqual(normalize_digits("۱۲۳٤٥٦"), "123456")

    def test_parse_positive_int_accepts_separators(self) -> None:
        self.assertEqual(parse_positive_int("۱٬۲۳۴٬۵۶۷"), 1_234_567)

    def test_parse_positive_int_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            parse_positive_int("-1")

    def test_fixed_discount_is_capped_at_price(self) -> None:
        self.assertEqual(discount_amount(50_000, DiscountKind.FIXED, 80_000), 50_000)

    def test_percent_discount_rounds_consistently(self) -> None:
        self.assertEqual(discount_amount(99, DiscountKind.PERCENT, 10), 10)

    def test_percentage_increase(self) -> None:
        self.assertEqual(
            changed_price(
                100_000,
                direction=PriceDirection.INCREASE,
                mode=PriceChangeMode.PERCENT,
                value=25,
            ),
            125_000,
        )

    def test_decrease_never_goes_below_zero(self) -> None:
        self.assertEqual(
            changed_price(
                1_000,
                direction=PriceDirection.DECREASE,
                mode=PriceChangeMode.FIXED,
                value=10_000,
            ),
            0,
        )

    def test_slug_is_safe_ascii(self) -> None:
        self.assertEqual(slugify_ascii(" Pro Plan ۲۰۲۶ "), "pro_plan_2026")


if __name__ == "__main__":
    unittest.main()
