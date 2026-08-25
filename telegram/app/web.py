from __future__ import annotations

import html
import logging

from aiohttp import web

from app.services.registry import TenantRegistry
from app.services.store import StoreService
from app.services.zarinpal import ZarinpalClient

logger = logging.getLogger(__name__)


def create_web_app(
    *, registry: TenantRegistry, sessions: object, zarinpal: ZarinpalClient
) -> web.Application:
    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "tenant_bots": len(registry.handles)})

    async def zarinpal_callback(request: web.Request) -> web.Response:
        tenant_id = int(request.match_info["tenant_id"])
        transaction_id = int(request.match_info["transaction_id"])
        authority = request.query.get("Authority", "")
        status = request.query.get("Status", "").upper()
        service = StoreService(tenant_id, sessions)
        transaction = await service.get_transaction_by_authority(authority)
        if not transaction or transaction.id != transaction_id:
            return _payment_page("تراکنش معتبر نیست", ok=False)
        if status != "OK":
            return _payment_page("پرداخت لغو شد یا ناموفق بود", ok=False)
        settings = await service.get_settings()
        try:
            result = await zarinpal.verify_payment(
                merchant_id=settings.zarinpal_merchant_id or "",
                amount_toman=transaction.amount_toman,
                authority=authority,
            )
            if not result.paid:
                return _payment_page(f"تأیید پرداخت ناموفق بود (کد {result.code})", ok=False)
            _, user_id = await service.review_topup(
                transaction.id,
                approve=True,
                reviewer_telegram_id=0,
                ref=result.ref_id,
            )
            bot = registry.get_bot(tenant_id)
            if bot:
                await bot.send_message(
                    user_id,
                    f"✅ پرداخت #{transaction.id} تأیید و کیف پول شما شارژ شد.\n"
                    f"کد پیگیری درگاه: <code>{html.escape(result.ref_id or '—')}</code>",
                )
            return _payment_page(
                f"پرداخت با موفقیت انجام شد. کد پیگیری: {result.ref_id or '—'}", ok=True
            )
        except Exception:
            logger.exception("Zarinpal callback failed for tenant %s", tenant_id)
            return _payment_page("تأیید پرداخت با خطا روبه‌رو شد؛ با پشتیبانی تماس بگیرید", ok=False)

    app.router.add_get("/healthz", health)
    app.router.add_get(
        "/payments/zarinpal/{tenant_id:\\d+}/{transaction_id:\\d+}", zarinpal_callback
    )
    return app


def _payment_page(message: str, *, ok: bool) -> web.Response:
    color = "#16a34a" if ok else "#dc2626"
    body = (
        "<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<body style='font-family:sans-serif;background:#f5f7fb;padding:40px'>"
        "<main style='max-width:540px;margin:auto;background:white;"
        "padding:28px;border-radius:18px'>"
        f"<h2 style='color:{color}'>{'پرداخت موفق' if ok else 'پرداخت ناموفق'}</h2>"
        f"<p>{html.escape(message)}</p><p>می‌توانید این صفحه را ببندید و به تلگرام برگردید.</p>"
        "</main></body></html>"
    )
    return web.Response(text=body, content_type="text/html")
