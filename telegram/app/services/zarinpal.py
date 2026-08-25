from __future__ import annotations

from dataclasses import dataclass

import aiohttp

REQUEST_URL = "https://payment.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
START_PAY_URL = "https://www.zarinpal.com/pg/StartPay/{authority}"


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    authority: str
    payment_url: str


@dataclass(frozen=True, slots=True)
class PaymentVerification:
    paid: bool
    code: int
    ref_id: str | None = None


class ZarinpalError(RuntimeError):
    pass


class ZarinpalClient:
    """Minimal async client for Zarinpal v4; store amounts are toman, API amounts are rial."""

    async def request_payment(
        self,
        *,
        merchant_id: str,
        amount_toman: int,
        callback_url: str,
        description: str,
    ) -> PaymentRequest:
        payload = {
            "merchant_id": merchant_id,
            "amount": amount_toman * 10,
            "callback_url": callback_url,
            "description": description[:255],
        }
        result = await self._post(REQUEST_URL, payload)
        data = result.get("data") or {}
        if int(data.get("code", 0)) != 100 or not data.get("authority"):
            raise ZarinpalError(self._error_text(result))
        authority = str(data["authority"])
        return PaymentRequest(authority, START_PAY_URL.format(authority=authority))

    async def verify_payment(
        self, *, merchant_id: str, amount_toman: int, authority: str
    ) -> PaymentVerification:
        result = await self._post(
            VERIFY_URL,
            {
                "merchant_id": merchant_id,
                "amount": amount_toman * 10,
                "authority": authority,
            },
        )
        data = result.get("data") or {}
        code = int(data.get("code", 0))
        return PaymentVerification(
            paid=code in {100, 101},
            code=code,
            ref_id=str(data.get("ref_id")) if data.get("ref_id") is not None else None,
        )

    async def _post(self, url: str, payload: dict[str, object]) -> dict[str, object]:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                try:
                    body = await response.json(content_type=None)
                except Exception as exc:
                    raise ZarinpalError("پاسخ نامعتبر از درگاه پرداخت") from exc
                if response.status >= 500:
                    raise ZarinpalError("درگاه پرداخت موقتاً در دسترس نیست")
                return body

    @staticmethod
    def _error_text(result: dict[str, object]) -> str:
        errors = result.get("errors")
        if isinstance(errors, dict):
            return str(errors.get("message") or errors.get("code") or "خطای درگاه پرداخت")
        return "ایجاد پرداخت ناموفق بود"
