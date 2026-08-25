from __future__ import annotations

import html
import logging
from datetime import UTC

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bots.ui import BUILDER_MENU, CANCEL, inline_keyboard
from app.config import Settings
from app.domain import format_toman, parse_positive_int
from app.models import BotStatus, TransactionStatus
from app.security import TokenCipher, token_fingerprint
from app.services.builder import BuilderService

logger = logging.getLogger(__name__)


class BuilderState(StatesGroup):
    mode = State()
    token = State()
    topup_amount = State()
    topup_receipt = State()
    support = State()


def create_builder_router(
    *,
    service: BuilderService,
    settings: Settings,
    cipher: TokenCipher,
    registry: object,
) -> Router:
    router = Router(name="builder")

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        payload = ""
        if message.text and " " in message.text:
            payload = message.text.split(maxsplit=1)[1]
        referral = payload.removeprefix("ref_") if payload.startswith("ref_") else None
        user = await service.ensure_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
            referral,
        )
        if user.is_blocked:
            await message.answer("⛔️ دسترسی شما به سامانه مسدود شده است.")
            return
        await message.answer(
            "سلام! با این ربات می‌توانید فروشگاه تلگرامی شخصی خودتان را بسازید و مدیریت کنید.",
            reply_markup=BUILDER_MENU,
        )

    @router.message(F.text == "❌ انصراف")
    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=BUILDER_MENU)

    @router.message(F.text == "🛠 ساخت ربات فروشگاه")
    async def create_intro(message: Message, state: FSMContext) -> None:
        await state.set_state(BuilderState.mode)
        await message.answer(
            "نوع ساخت را انتخاب کنید:\n\n"
            f"• برای خودم: {settings.trial_days} روز آزمایشی رایگان\n"
            f"• برای مشتری: {settings.subscription_days} روز فعال با هزینه "
            f"{format_toman(settings.customer_setup_price_toman)} تومان",
            reply_markup=inline_keyboard(
                [[("👤 برای خودم", "buildmode:self"), ("🤝 برای مشتری", "buildmode:customer")]]
            ),
        )

    @router.callback_query(BuilderState.mode, F.data.startswith("buildmode:"))
    async def create_mode(callback: CallbackQuery, state: FSMContext) -> None:
        customer_mode = callback.data.endswith("customer")
        await state.update_data(customer_mode=customer_mode)
        await state.set_state(BuilderState.token)
        await callback.message.answer(
            "برای ساخت ربات:\n\n"
            "1) وارد @BotFather شوید و /newbot را بزنید.\n"
            "2) نام فارسی و سپس نام کاربری انگلیسیِ ختم‌شونده به bot را وارد کنید.\n"
            "3) توکن دریافتی را همین‌جا بفرستید.\n\n"
            "⚠️ توکن را برای هیچ فرد دیگری ارسال نکنید. پیام حاوی توکن بعد از ثبت حذف می‌شود.",
            reply_markup=CANCEL,
        )
        await callback.answer()

    @router.message(BuilderState.token)
    async def accept_token(message: Message, state: FSMContext) -> None:
        token = (message.text or "").strip()
        if ":" not in token or len(token) < 30:
            await message.answer("توکن معتبر نیست؛ توکن کامل BotFather را ارسال کنید.")
            return
        try:
            await message.delete()
        except Exception as exc:
            logger.debug("Could not delete token message: %s", type(exc).__name__)
        candidate = Bot(token=token)
        try:
            state_data = await state.get_data()
            me = await candidate.get_me()
            if not me.is_bot or not me.username:
                raise ValueError("حساب ارسال‌شده ربات معتبر نیست.")
            await candidate.delete_webhook(drop_pending_updates=True)
            tenant = await service.create_tenant(
                owner_telegram_id=message.from_user.id,
                bot_id=me.id,
                username=me.username,
                display_name=me.full_name,
                encrypted_token=cipher.encrypt(token),
                token_hash=token_fingerprint(token),
                trial_days=settings.trial_days,
                referral_reward_toman=settings.referral_reward_toman,
                customer_mode=bool(state_data.get("customer_mode")),
                setup_price_toman=settings.customer_setup_price_toman,
                subscription_days=settings.subscription_days,
            )
        except Exception as exc:
            await candidate.session.close()
            logger.warning("Tenant token rejected: %s", type(exc).__name__)
            await message.answer(f"ثبت ربات انجام نشد: {html.escape(str(exc))}")
            return
        await candidate.session.close()
        await state.clear()
        try:
            await registry.start_tenant(tenant.id)
        except Exception:
            logger.exception("Could not start tenant %s immediately", tenant.id)
        mode_text = (
            f"اشتراک فعال: {settings.subscription_days} روز"
            if state_data.get("customer_mode")
            else f"اشتراک آزمایشی: {settings.trial_days} روز"
        )
        await message.answer(
            f"✅ ربات @{html.escape(me.username)} با موفقیت ساخته شد.\n"
            f"شناسه داخلی: <code>{tenant.id}</code>\n"
            f"{mode_text}\n\n"
            "اکنون ربات خودتان را باز کنید و /start را بزنید.",
            reply_markup=inline_keyboard([[("🤖 باز کردن ربات", f"open:{tenant.id}")]]),
        )
        await message.answer("منوی اصلی:", reply_markup=BUILDER_MENU)

    @router.callback_query(F.data.startswith("open:"))
    async def open_bot(callback: CallbackQuery) -> None:
        bots = await service.list_bots(callback.from_user.id)
        tenant_id = int(callback.data.split(":")[1])
        tenant = next((item for item in bots if item.id == tenant_id), None)
        if not tenant:
            await callback.answer("ربات پیدا نشد.", show_alert=True)
            return
        await callback.message.answer(f"https://t.me/{tenant.username}")
        await callback.answer()

    @router.message(F.text == "🤖 ربات‌های من")
    async def my_bots(message: Message) -> None:
        bots = await service.list_bots(message.from_user.id)
        if not bots:
            await message.answer("هنوز رباتی نساخته‌اید.")
            return
        lines = ["<b>ربات‌های شما</b>"]
        now = message.date.astimezone(UTC)
        for tenant in bots:
            end = (
                tenant.trial_ends_at
                if tenant.status == BotStatus.TRIAL
                else tenant.subscription_ends_at
            )
            days = max(0, (end.astimezone(UTC) - now).days + 1) if end else 0
            status = {
                BotStatus.TRIAL: f"آزمایشی؛ {days} روز",
                BotStatus.ACTIVE: f"فعال؛ {days} روز",
                BotStatus.EXPIRED: "منقضی",
                BotStatus.DISABLED: "غیرفعال",
            }[tenant.status]
            lines.append(
                f"\n• @{html.escape(tenant.username)} — {status} — ID: <code>{tenant.id}</code>"
            )
        await message.answer("".join(lines))

    @router.message(F.text == "♻️ تمدید اشتراک")
    async def renew_list(message: Message) -> None:
        bots = await service.list_bots(message.from_user.id)
        if not bots:
            await message.answer("رباتی برای تمدید وجود ندارد.")
            return
        rows = [[(f"@{bot.username}", f"renew:{bot.id}")] for bot in bots]
        await message.answer(
            f"هزینه تمدید {settings.subscription_days} روزه: "
            f"{format_toman(settings.monthly_subscription_price_toman)} تومان\n"
            "ربات موردنظر را انتخاب کنید:",
            reply_markup=inline_keyboard(rows),
        )

    @router.callback_query(F.data.startswith("renew:"))
    async def renew(callback: CallbackQuery) -> None:
        tenant_id = int(callback.data.split(":")[1])
        try:
            tenant = await service.renew_bot(
                telegram_id=callback.from_user.id,
                tenant_id=tenant_id,
                price_toman=settings.monthly_subscription_price_toman,
                subscription_days=settings.subscription_days,
            )
            await registry.start_tenant(tenant.id)
        except Exception as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.message.edit_text(
            f"✅ اشتراک @{tenant.username} برای {settings.subscription_days} روز تمدید شد."
        )
        await callback.answer()

    @router.message(F.text == "👤 حساب کاربری")
    async def account(message: Message) -> None:
        snapshot = await service.account(message.from_user.id)
        tx_lines = []
        for tx in snapshot.recent_transactions:
            tx_lines.append(
                f"• #{tx.id} | {format_toman(tx.amount_toman)} تومان | {tx.status.value}"
            )
        me = await message.bot.get_me()
        referral = f"https://t.me/{me.username}?start=ref_{snapshot.user.referral_code}"
        await message.answer(
            f"<b>حساب کاربری</b>\n"
            f"شناسه: <code>{message.from_user.id}</code>\n"
            f"تعداد ربات‌ها: {snapshot.bots_count}\n"
            f"موجودی: {format_toman(snapshot.user.balance_toman)} تومان\n"
            f"لینک دعوت: {referral}\n\n"
            f"<b>۵ تراکنش آخر:</b>\n{chr(10).join(tx_lines) or 'موردی نیست.'}",
            reply_markup=inline_keyboard([[("➕ افزایش موجودی", "builder_topup")]]),
        )

    @router.callback_query(F.data == "builder_topup")
    async def topup_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(BuilderState.topup_amount)
        await callback.message.answer("مبلغ شارژ را به تومان وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(BuilderState.topup_amount)
    async def topup_amount(message: Message, state: FSMContext) -> None:
        try:
            amount = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.update_data(amount=amount)
        await state.set_state(BuilderState.topup_receipt)
        await message.answer(
            f"مبلغ {format_toman(amount)} تومان را به کارت زیر واریز کنید:\n"
            f"<code>{html.escape(settings.builder_card_number)}</code>\n"
            f"به نام {html.escape(settings.builder_card_holder)}\n\nسپس تصویر رسید را ارسال کنید."
        )

    @router.message(BuilderState.topup_receipt, F.photo)
    async def topup_receipt(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        tx = await service.create_topup(
            message.from_user.id, int(data["amount"]), message.photo[-1].file_id
        )
        await state.clear()
        markup = inline_keyboard([[("✅ تأیید", f"btx:ok:{tx.id}"), ("❌ رد", f"btx:no:{tx.id}")]])
        for admin_id in settings.super_admin_ids:
            try:
                await message.bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=(
                        f"رسید شارژ ربات‌ساز #{tx.id}\nکاربر: <code>{message.from_user.id}</code>\n"
                        f"مبلغ: {format_toman(tx.amount_toman)} تومان"
                    ),
                    reply_markup=markup,
                )
            except Exception:
                logger.exception("Could not notify super admin %s", admin_id)
        await message.answer(
            "✅ رسید ثبت شد و پس از بررسی نتیجه اعلام می‌شود.", reply_markup=BUILDER_MENU
        )

    @router.callback_query(F.data.startswith("btx:"))
    async def review_builder_topup(callback: CallbackQuery) -> None:
        if callback.from_user.id not in settings.super_admin_ids:
            await callback.answer("دسترسی ندارید.", show_alert=True)
            return
        _, action, raw_id = callback.data.split(":")
        tx = await service.review_topup(
            int(raw_id),
            action == "ok",
            callback.from_user.id,
            settings.referral_reward_toman,
        )
        result = "تأیید" if tx.status == TransactionStatus.APPROVED else "رد"
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\nنتیجه: {result}"
        )
        await callback.bot.send_message(tx.user.telegram_id, f"رسید شارژ #{tx.id} {result} شد.")
        await callback.answer()

    @router.message(F.text == "💬 پشتیبانی")
    async def support_start(message: Message, state: FSMContext) -> None:
        await state.set_state(BuilderState.support)
        support = html.escape(settings.builder_support_account)
        await message.answer(
            f"پیام خود را ارسال کنید. راه ارتباط مستقیم: {support}",
            reply_markup=CANCEL,
        )

    @router.message(BuilderState.support)
    async def support_message(message: Message, state: FSMContext) -> None:
        for admin_id in settings.super_admin_ids:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"پیام پشتیبانی ربات‌ساز از <code>{message.from_user.id}</code>",
                )
                await message.copy_to(admin_id)
            except Exception:
                logger.exception("Support delivery failed")
        await state.clear()
        await message.answer("پیام شما ارسال شد.", reply_markup=BUILDER_MENU)

    return router
