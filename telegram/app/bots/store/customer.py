from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)

from app.bots.store.helpers import (
    ORDER_LABELS,
    missing_required_channels,
    product_text,
    send_delivery,
)
from app.bots.store.states import CustomerState
from app.bots.ui import ADMIN_MENU, CANCEL, STORE_MENU, inline_keyboard
from app.config import Settings
from app.domain import format_toman, parse_positive_int
from app.models import DeliveryType
from app.services.store import PurchaseOutcome, StoreService
from app.services.zarinpal import ZarinpalClient

logger = logging.getLogger(__name__)


def create_customer_router(
    service: StoreService, app_settings: Settings, zarinpal: ZarinpalClient
) -> Router:
    router = Router(name=f"store-{service.tenant_id}-customer")

    async def ensure_customer(message: Message, referral: str | None = None):
        user = await service.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            referral_code=referral,
        )
        if user.is_blocked:
            await message.answer("⛔️ حساب شما مسدود شده است.")
            return None
        return user

    async def show_home(message: Message) -> None:
        store_settings = await service.get_settings()
        missing = await missing_required_channels(
            message.bot, message.from_user.id, await service.list_required_channels()
        )
        if missing:
            buttons: list[list[InlineKeyboardButton]] = []
            for channel in missing:
                url = channel.invite_url
                if not url and channel.chat_id.startswith("@"):
                    url = f"https://t.me/{channel.chat_id[1:]}"
                if url:
                    buttons.append([InlineKeyboardButton(text=channel.title, url=url)])
            buttons.append(
                [InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="join:check")]
            )
            await message.answer(
                "برای استفاده از فروشگاه ابتدا در کانال‌های زیر عضو شوید:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )
            return
        if store_settings.start_photo_file_id:
            await message.answer_photo(
                store_settings.start_photo_file_id,
                caption=store_settings.start_text,
                reply_markup=STORE_MENU,
            )
        else:
            await message.answer(store_settings.start_text, reply_markup=STORE_MENU)

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        payload = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""
        referral = payload.removeprefix("ref_") if payload.startswith("ref_") else None
        user = await ensure_customer(message, referral)
        if not user:
            return
        if payload.startswith("product_"):
            product = await service.get_product_by_deep_link(payload.removeprefix("product_"))
            if product:
                await show_product(message.bot, message.chat.id, product.id)
                return
        await show_home(message)

    @router.callback_query(F.data == "join:check")
    async def check_join(callback: CallbackQuery) -> None:
        missing = await missing_required_channels(
            callback.bot, callback.from_user.id, await service.list_required_channels()
        )
        if missing:
            await callback.answer("هنوز عضویت شما کامل نیست.", show_alert=True)
            return
        await callback.message.delete()
        await callback.message.answer("✅ عضویت تأیید شد.", reply_markup=STORE_MENU)
        await callback.answer()

    @router.message(F.text == "🏠 منوی فروشگاه")
    @router.message(F.text == "❌ انصراف")
    async def menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        markup = (
            ADMIN_MENU
            if message.text == "❌ انصراف" and await service.is_admin(message.from_user.id)
            else STORE_MENU
        )
        await message.answer(
            "عملیات لغو شد." if message.text == "❌ انصراف" else "منوی فروشگاه:",
            reply_markup=markup,
        )

    @router.message(F.text == "🛍 محصولات")
    async def categories(message: Message) -> None:
        if not await ensure_customer(message):
            return
        items = await service.list_categories()
        rows = [[(item.name, f"cat:{item.id}")] for item in items]
        rows.append([("همه محصولات", "cat:all")])
        await message.answer("دسته‌بندی موردنظر را انتخاب کنید:", reply_markup=inline_keyboard(rows))

    @router.callback_query(F.data.startswith("cat:"))
    async def products(callback: CallbackQuery) -> None:
        raw = callback.data.split(":")[1]
        items = await service.list_products(None if raw == "all" else int(raw))
        if not items:
            await callback.answer("محصولی در این دسته نیست.", show_alert=True)
            return
        rows = [[(item.name_fa, f"product:{item.id}")] for item in items]
        await callback.message.edit_text(
            "محصول را انتخاب کنید:", reply_markup=inline_keyboard(rows)
        )
        await callback.answer()

    async def show_product(bot: Bot, chat_id: int, product_id: int) -> None:
        product = await service.get_product(product_id, active_only=True)
        if not product:
            await bot.send_message(chat_id, "محصول پیدا نشد یا غیرفعال است.")
            return
        rows = [
            [(f"خرید {plan.name} — {format_toman(plan.price_toman)} تومان", f"plan:{plan.id}")]
            for plan in product.plans
            if plan.is_active
        ]
        markup = inline_keyboard(rows) if rows else None
        if product.primary_photo_file_id:
            await bot.send_photo(
                chat_id,
                product.primary_photo_file_id,
                caption=product_text(product),
                reply_markup=markup,
            )
        else:
            await bot.send_message(chat_id, product_text(product), reply_markup=markup)

    @router.callback_query(F.data.startswith("product:"))
    async def product(callback: CallbackQuery) -> None:
        await show_product(callback.bot, callback.message.chat.id, int(callback.data.split(":")[1]))
        await callback.answer()

    @router.message(F.text == "🔎 جستجوی محصول")
    async def search_start(message: Message, state: FSMContext) -> None:
        await state.set_state(CustomerState.search)
        await message.answer("نام فارسی یا انگلیسی محصول را وارد کنید:", reply_markup=CANCEL)

    @router.message(CustomerState.search)
    async def search_result(message: Message, state: FSMContext) -> None:
        items = await service.search_products(message.text or "")
        await state.clear()
        if not items:
            await message.answer("نتیجه‌ای پیدا نشد.", reply_markup=STORE_MENU)
            return
        await message.answer(
            "نتایج جستجو:",
            reply_markup=inline_keyboard([[(p.name_fa, f"product:{p.id}")] for p in items]),
        )

    @router.callback_query(F.data.startswith("plan:"))
    async def choose_plan(callback: CallbackQuery, state: FSMContext) -> None:
        plan_id = int(callback.data.split(":")[1])
        await state.clear()
        await state.update_data(plan_id=plan_id, user_id=callback.from_user.id)
        await callback.message.answer(
            "اگر کد تخفیف دارید وارد کنید:",
            reply_markup=inline_keyboard([[("بدون کد تخفیف", "buy:nocode")]]),
        )
        await state.set_state(CustomerState.discount)
        await callback.answer()

    @router.callback_query(CustomerState.discount, F.data == "buy:nocode")
    async def buy_without_code(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(discount_code=None)
        await prepare_confirmation(callback.message, state)
        await callback.answer()

    @router.message(CustomerState.discount)
    async def discount_code(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        preview = await service.preview_discount(int(data["plan_id"]), message.text or "")
        if not preview or preview[1] == 0:
            await message.answer("کد تخفیف معتبر نیست. دوباره وارد کنید یا «بدون کد» را بزنید.")
            return
        await state.update_data(discount_code=(message.text or "").strip())
        await message.answer(
            f"تخفیف: {format_toman(preview[1])} تومان\nمبلغ نهایی: {format_toman(preview[2])} تومان"
        )
        await prepare_confirmation(message, state)

    async def prepare_confirmation(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        plan_id = int(data["plan_id"])
        product = None
        for candidate in await service.list_products(active_only=True):
            if any(plan.id == plan_id for plan in candidate.plans):
                product = await service.get_product(candidate.id, active_only=True)
                break
        if (
            product
            and product.delivery_type == DeliveryType.MANUAL
            and product.manual_prompt
            and "manual_info" not in data
        ):
            await state.set_state(CustomerState.manual_info)
            await message.answer(product.manual_prompt, reply_markup=CANCEL)
            return
        if not product:
            await state.clear()
            await message.answer("محصول یا پلن دیگر فعال نیست.", reply_markup=STORE_MENU)
            return
        plan = next(plan for plan in product.plans if plan.id == plan_id)
        preview = await service.preview_discount(plan_id, data.get("discount_code") or "")
        if not preview:
            await state.clear()
            await message.answer("پلن دیگر فعال نیست.", reply_markup=STORE_MENU)
            return
        await state.set_state(CustomerState.confirm)
        await message.answer(
            f"<b>پیش‌فاکتور</b>\n"
            f"محصول: {html.escape(product.name_fa)}\n"
            f"پلن: {html.escape(plan.name)}\n"
            f"مبلغ پایه: {format_toman(preview[0])} تومان\n"
            f"تخفیف: {format_toman(preview[1])} تومان\n"
            f"<b>مبلغ نهایی: {format_toman(preview[2])} تومان</b>",
            reply_markup=inline_keyboard(
                [[("✅ پرداخت از کیف پول", "buy:confirm"), ("❌ لغو", "buy:cancel")]]
            ),
        )

    @router.message(CustomerState.manual_info)
    async def manual_info(message: Message, state: FSMContext) -> None:
        await state.update_data(manual_info=message.text or message.caption or "")
        await prepare_confirmation(message, state)

    @router.callback_query(CustomerState.confirm, F.data == "buy:cancel")
    async def cancel_purchase(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.edit_text("خرید لغو شد.")
        await callback.answer()

    @router.callback_query(CustomerState.confirm, F.data == "buy:confirm")
    async def confirm_purchase(callback: CallbackQuery, state: FSMContext) -> None:
        await execute_purchase(callback.message, state, callback.from_user.id)
        await callback.answer()

    async def execute_purchase(message: Message, state: FSMContext, user_id: int) -> None:
        data = await state.get_data()
        manual_info = data.get("manual_info")
        outcome = await service.purchase(
            user_telegram_id=user_id,
            plan_id=int(data["plan_id"]),
            discount_code=data.get("discount_code"),
            manual_info=manual_info,
        )
        await state.clear()
        await render_purchase(message, outcome, user_id, manual_info)

    async def render_purchase(
        message: Message,
        outcome: PurchaseOutcome,
        user_id: int,
        manual_info: str | None,
    ) -> None:
        if not outcome.ok:
            markup = (
                inline_keyboard([[("➕ افزایش موجودی", "wallet:topup")]])
                if outcome.required_toman
                else None
            )
            await message.answer(
                f"❌ {outcome.reason}"
                + (
                    f"\nکسری موجودی: {format_toman(outcome.required_toman)} تومان"
                    if outcome.required_toman
                    else ""
                ),
                reply_markup=markup,
            )
            return
        await message.answer(
            f"✅ خرید با موفقیت انجام شد.\n"
            f"محصول: {html.escape(outcome.product_name)}\nپلن: {html.escape(outcome.plan_name)}\n"
            f"مبلغ: {format_toman(outcome.final_amount_toman)} تومان\n"
            f"کد پیگیری: <code>{outcome.tracking_code}</code>"
        )
        if outcome.delivery_type == DeliveryType.AUTOMATIC:
            for payload in outcome.delivery:
                await send_delivery(message.bot, message.chat.id, payload)
            await service.mark_order_delivered(outcome.order_id)
        else:
            for admin_id in await service.admin_ids():
                try:
                    product_name = html.escape(outcome.product_name)
                    plan_name = html.escape(outcome.plan_name)
                    await message.bot.send_message(
                        admin_id,
                        f"📦 سفارش دستی جدید #{outcome.order_id}\n"
                        f"کاربر: <code>{user_id}</code>\n"
                        f"محصول: {product_name} / {plan_name}\n"
                        f"اطلاعات: {html.escape(manual_info or '—')}",
                        reply_markup=inline_keyboard(
                            [[("✅ ثبت تحویل", f"order:delivered:{outcome.order_id}")]]
                        ),
                    )
                except Exception:
                    logger.exception("Manual order notification failed")
        if outcome.referral_user_telegram_id:
            try:
                reward = format_toman(outcome.referral_reward_toman)
                await message.bot.send_message(
                    outcome.referral_user_telegram_id,
                    f"🎁 {reward} تومان پاداش دعوت دریافت کردید.",
                )
            except Exception as exc:
                logger.debug("Referral notification failed: %s", type(exc).__name__)

    @router.message(F.text == "📦 پیگیری سفارش")
    async def tracking_start(message: Message, state: FSMContext) -> None:
        await state.set_state(CustomerState.tracking)
        await message.answer("کد پیگیری سفارش را وارد کنید:", reply_markup=CANCEL)

    @router.message(CustomerState.tracking)
    async def tracking(message: Message, state: FSMContext) -> None:
        order = await service.get_order(message.text or "", message.from_user.id)
        await state.clear()
        if not order:
            await message.answer("سفارشی با این کد پیدا نشد.", reply_markup=STORE_MENU)
            return
        await message.answer(
            f"سفارش <code>{order.tracking_code}</code>\n"
            f"محصول: {html.escape(order.plan.product.name_fa)}\n"
            f"وضعیت: {ORDER_LABELS[order.status]}\n"
            f"مبلغ: {format_toman(order.final_amount_toman)} تومان",
            reply_markup=STORE_MENU,
        )

    @router.message(F.text == "👤 حساب کاربری")
    async def account(message: Message) -> None:
        user, orders, transactions = await service.account_snapshot(message.from_user.id)
        me = await message.bot.get_me()
        referral = f"https://t.me/{me.username}?start=ref_{user.referral_code}"
        order_lines = [f"• {o.tracking_code}: {ORDER_LABELS[o.status]}" for o in orders]
        tx_lines = [
            f"• #{tx.id}: {format_toman(tx.amount_toman)} تومان ({tx.status.value})"
            for tx in transactions
        ]
        settings = await service.get_settings()
        await message.answer(
            f"<b>حساب کاربری</b>\nشناسه: <code>{message.from_user.id}</code>\n"
            f"موجودی: {format_toman(user.balance_toman)} تومان\n"
            f"لینک دعوت: {referral}\n"
            f"پاداش اولین خرید دوست: {format_toman(settings.referral_reward_toman)} تومان\n\n"
            f"<b>۵ سفارش آخر:</b>\n{chr(10).join(order_lines) or 'موردی نیست.'}\n\n"
            f"<b>۵ تراکنش آخر:</b>\n{chr(10).join(tx_lines) or 'موردی نیست.'}",
            reply_markup=inline_keyboard([[("➕ افزایش موجودی", "wallet:topup")]]),
        )

    @router.callback_query(F.data == "wallet:topup")
    async def topup_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CustomerState.topup_amount)
        await callback.message.answer("مبلغ شارژ را به تومان وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(CustomerState.topup_amount)
    async def topup_amount(message: Message, state: FSMContext) -> None:
        try:
            amount = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.update_data(amount=amount)
        settings = await service.get_settings()
        rows = []
        if settings.zarinpal_enabled and settings.zarinpal_merchant_id:
            rows.append([("پرداخت آنلاین زرین‌پال", "pay:zarinpal")])
        if settings.card_enabled and settings.card_number:
            rows.append([("کارت‌به‌کارت", "pay:card")])
        if not rows:
            await state.clear()
            await message.answer(
                "درگاه پرداخت هنوز توسط مدیر تنظیم نشده است.", reply_markup=STORE_MENU
            )
            return
        await message.answer("روش پرداخت را انتخاب کنید:", reply_markup=inline_keyboard(rows))

    @router.callback_query(F.data == "pay:card")
    async def card_payment(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        amount = int(data["amount"])
        tx = await service.create_topup(callback.from_user.id, amount, "card")
        await state.update_data(transaction_id=tx.id)
        await state.set_state(CustomerState.topup_receipt)
        settings = await service.get_settings()
        await callback.message.answer(
            f"مبلغ {format_toman(amount)} تومان را واریز کنید:\n"
            f"<code>{html.escape(settings.card_number or '')}</code>\n"
            f"به نام {html.escape(settings.card_holder or '')}\n"
            f"شناسه تراکنش: <code>{tx.id}</code>\n\nسپس تصویر رسید را بفرستید."
        )
        await callback.answer()

    @router.callback_query(F.data == "pay:zarinpal")
    async def zarinpal_payment(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        amount = int(data["amount"])
        settings = await service.get_settings()
        tx = await service.create_topup(callback.from_user.id, amount, "zarinpal")
        callback_url = (
            f"{app_settings.public_base_url}/payments/zarinpal/{service.tenant_id}/{tx.id}"
        )
        try:
            payment = await zarinpal.request_payment(
                merchant_id=settings.zarinpal_merchant_id or "",
                amount_toman=amount,
                callback_url=callback_url,
                description=f"شارژ کیف پول فروشگاه - تراکنش {tx.id}",
            )
            await service.set_topup_authority(tx.id, payment.authority)
        except Exception as exc:
            await state.clear()
            await callback.message.answer(f"اتصال به درگاه ناموفق بود: {html.escape(str(exc))}")
            await callback.answer()
            return
        await state.clear()
        await callback.message.answer(
            "برای پرداخت امن وارد درگاه شوید:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 پرداخت", url=payment.payment_url)]]
            ),
        )
        await callback.answer()

    @router.message(CustomerState.topup_receipt, F.photo)
    async def receipt(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        tx = await service.submit_receipt(int(data["transaction_id"]), message.photo[-1].file_id)
        await state.clear()
        markup = inline_keyboard(
            [[("✅ تأیید", f"topup:ok:{tx.id}"), ("❌ رد", f"topup:no:{tx.id}")]]
        )
        for admin_id in await service.admin_ids():
            try:
                await message.bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=(
                        f"رسید شارژ #{tx.id}\nکاربر: <code>{message.from_user.id}</code>\n"
                        f"مبلغ: {format_toman(tx.amount_toman)} تومان"
                    ),
                    reply_markup=markup,
                )
            except Exception:
                logger.exception("Receipt notification failed")
        await message.answer(
            "✅ رسید ثبت شد؛ نتیجه پس از بررسی اعلام می‌شود.", reply_markup=STORE_MENU
        )

    @router.message(F.text == "💬 پشتیبانی")
    async def support_start(message: Message, state: FSMContext) -> None:
        await state.set_state(CustomerState.support)
        await message.answer("پیام، تصویر یا فایل خود را ارسال کنید:", reply_markup=CANCEL)

    @router.message(CustomerState.support)
    async def support(message: Message, state: FSMContext) -> None:
        for admin_id in await service.admin_ids():
            try:
                header = await message.bot.send_message(
                    admin_id,
                    f"💬 پیام پشتیبانی از <code>{message.from_user.id}</code>\n"
                    "برای پاسخ، روی پیام کپی‌شده Reply کنید.",
                )
                copied = await message.copy_to(
                    admin_id, reply_parameters=ReplyParameters(message_id=header.message_id)
                )
                await service.remember_support_message(
                    user_chat_id=message.chat.id,
                    admin_chat_id=admin_id,
                    admin_message_id=copied.message_id,
                )
            except Exception:
                logger.exception("Support relay failed")
        await state.clear()
        await message.answer("پیام شما به پشتیبانی ارسال شد.", reply_markup=STORE_MENU)

    @router.message(F.reply_to_message)
    async def support_reply(message: Message) -> None:
        if not await service.is_admin(message.from_user.id):
            return
        target = await service.resolve_support_reply(
            message.chat.id, message.reply_to_message.message_id
        )
        if not target:
            return
        await message.copy_to(target)
        await message.answer("✅ پاسخ ارسال شد.")

    return router
