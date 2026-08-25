from __future__ import annotations

import asyncio
import html
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, TelegramObject

from app.bots.store.helpers import message_to_payload, product_text
from app.bots.store.states import (
    BulkPriceState,
    CategoryState,
    DiscountState,
    MessageManageState,
    PlanEditState,
    ProductCreateState,
    ProductEditState,
    SettingsState,
    UserManageState,
)
from app.bots.ui import ADMIN_MENU, CANCEL, STORE_MENU, inline_keyboard, reply_keyboard
from app.domain import PriceChangeMode, PriceDirection, format_toman, parse_positive_int
from app.models import DeliveryType, DiscountKindDB, TransactionStatus
from app.services.backup import generate_sql_backup
from app.services.store import StoreService

logger = logging.getLogger(__name__)


class AdminCallbackMiddleware(BaseMiddleware):
    def __init__(self, service: StoreService) -> None:
        self.service = service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery) and not await self.service.is_admin(event.from_user.id):
            await event.answer("دسترسی ندارید.", show_alert=True)
            return None
        return await handler(event, data)


class AdminUserFilter(Filter):
    def __init__(self, service: StoreService) -> None:
        self.service = service

    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user and await self.service.is_admin(message.from_user.id))


def create_admin_router(service: StoreService) -> Router:
    router = Router(name=f"store-{service.tenant_id}-admin")
    router.callback_query.outer_middleware(AdminCallbackMiddleware(service))

    async def allowed(user_id: int) -> bool:
        return await service.is_admin(user_id)

    async def deny(message: Message) -> None:
        await message.answer("این بخش فقط برای مدیر فروشگاه است.")

    @router.message(F.text == "⚙️ پنل مدیریت")
    async def admin_panel(message: Message, state: FSMContext) -> None:
        if not await allowed(message.from_user.id):
            await deny(message)
            return
        await state.clear()
        await message.answer("⚙️ پنل مدیریت فروشگاه", reply_markup=ADMIN_MENU)

    @router.message(F.text == "🏠 منوی فروشگاه")
    async def store_menu(message: Message, state: FSMContext) -> None:
        if not await allowed(message.from_user.id):
            return
        await state.clear()
        await message.answer("منوی فروشگاه:", reply_markup=STORE_MENU)

    @router.message(AdminUserFilter(service), F.text == "❌ انصراف")
    async def admin_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=ADMIN_MENU)

    @router.message(F.text == "💳 بخش مالی")
    async def finance(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        settings = await service.get_settings()
        merchant_id = html.escape(settings.zarinpal_merchant_id or "تنظیم نشده")
        await message.answer(
            "<b>تنظیمات مالی</b>\n"
            f"کارت‌به‌کارت: {'✅' if settings.card_enabled else '❌'}\n"
            f"شماره کارت: <code>{html.escape(settings.card_number or 'تنظیم نشده')}</code>\n"
            f"صاحب کارت: {html.escape(settings.card_holder or 'تنظیم نشده')}\n"
            f"زرین‌پال: {'✅' if settings.zarinpal_enabled else '❌'}\n"
            f"Merchant ID: <code>{merchant_id}</code>",
            reply_markup=inline_keyboard(
                [
                    [("فعال/غیرفعال کارت", "setting:toggle:card_enabled")],
                    [
                        ("شماره کارت", "setting:value:card_number"),
                        ("نام صاحب کارت", "setting:value:card_holder"),
                    ],
                    [("فعال/غیرفعال زرین‌پال", "setting:toggle:zarinpal_enabled")],
                    [("Merchant ID زرین‌پال", "setting:value:zarinpal_merchant_id")],
                ]
            ),
        )

    @router.callback_query(F.data.startswith("setting:toggle:"))
    async def toggle_setting(callback: CallbackQuery) -> None:
        if not await allowed(callback.from_user.id):
            await callback.answer("دسترسی ندارید.", show_alert=True)
            return
        key = callback.data.split(":")[2]
        if key not in {"card_enabled", "zarinpal_enabled"}:
            await callback.answer("تنظیم نامعتبر است.")
            return
        settings = await service.get_settings()
        await service.update_settings(callback.from_user.id, **{key: not getattr(settings, key)})
        await callback.answer("ذخیره شد.", show_alert=True)

    @router.callback_query(F.data.startswith("setting:value:"))
    async def setting_value_start(callback: CallbackQuery, state: FSMContext) -> None:
        if not await allowed(callback.from_user.id):
            return
        key = callback.data.split(":", 2)[2]
        allowed_keys = {
            "card_number",
            "card_holder",
            "zarinpal_merchant_id",
            "start_text",
            "support_account",
            "secondary_admin_id",
            "satisfaction_channel_id",
            "log_channel_id",
            "referral_reward_toman",
            "start_photo_file_id",
        }
        if key not in allowed_keys:
            await callback.answer("تنظیم نامعتبر است.")
            return
        await state.update_data(setting_key=key)
        await state.set_state(SettingsState.value)
        prompt = (
            "تصویر شروع را ارسال کنید."
            if key == "start_photo_file_id"
            else "مقدار جدید را ارسال کنید؛ برای حذف، خط تیره (-) بفرستید."
        )
        await callback.message.answer(prompt, reply_markup=CANCEL)
        await callback.answer()

    @router.message(SettingsState.value)
    async def setting_value(message: Message, state: FSMContext) -> None:
        if not await allowed(message.from_user.id):
            return
        data = await state.get_data()
        key = data["setting_key"]
        if key == "start_photo_file_id":
            if not message.photo:
                await message.answer("لطفاً یک تصویر ارسال کنید.")
                return
            value: object = message.photo[-1].file_id
        else:
            raw = (message.text or "").strip()
            if raw == "-" and key == "start_text":
                value = ""
            elif raw == "-" and key == "referral_reward_toman":
                value = 0
            else:
                value = None if raw == "-" else raw
            if key in {"secondary_admin_id", "referral_reward_toman"} and value is not None:
                try:
                    value = int(str(value).replace(",", ""))
                except ValueError:
                    await message.answer("این مقدار باید عدد باشد.")
                    return
        await service.update_settings(message.from_user.id, **{key: value})
        await state.clear()
        await message.answer("✅ تنظیمات ذخیره شد.", reply_markup=ADMIN_MENU)

    @router.message(F.text == "🗂 مدیریت دسته‌ها")
    async def category_menu(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        categories = await service.list_categories(active_only=False)
        rows = [[(item.name, f"acat:view:{item.id}")] for item in categories]
        rows.append([("➕ افزودن دسته", "acat:add")])
        await message.answer("مدیریت دسته‌بندی‌ها:", reply_markup=inline_keyboard(rows))

    @router.callback_query(F.data == "acat:add")
    async def category_add_start(callback: CallbackQuery, state: FSMContext) -> None:
        if not await allowed(callback.from_user.id):
            return
        await state.set_state(CategoryState.add)
        await callback.message.answer("نام دسته جدید را بفرستید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(CategoryState.add)
    async def category_add(message: Message, state: FSMContext) -> None:
        try:
            category = await service.create_category(message.text or "")
        except Exception as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        await message.answer(
            f"✅ دسته «{html.escape(category.name)}» ساخته شد.", reply_markup=ADMIN_MENU
        )

    @router.callback_query(F.data.startswith("acat:view:"))
    async def category_view(callback: CallbackQuery) -> None:
        category_id = int(callback.data.split(":")[2])
        category = next(
            (c for c in await service.list_categories(active_only=False) if c.id == category_id),
            None,
        )
        if not category:
            await callback.answer("دسته پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            f"دسته: {html.escape(category.name)}",
            reply_markup=inline_keyboard(
                [
                    [
                        ("✏️ تغییر نام", f"acat:rename:{category.id}"),
                        ("🗑 حذف", f"acat:delete:{category.id}"),
                    ]
                ]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("acat:rename:"))
    async def category_rename_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(category_id=int(callback.data.split(":")[2]))
        await state.set_state(CategoryState.rename)
        await callback.message.answer("نام جدید را ارسال کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(CategoryState.rename)
    async def category_rename(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        await service.rename_category(
            int(data["category_id"]), message.text or "", message.from_user.id
        )
        await state.clear()
        await message.answer("✅ نام دسته تغییر کرد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data.startswith("acat:delete:"))
    async def category_delete(callback: CallbackQuery) -> None:
        try:
            await service.delete_category(int(callback.data.split(":")[2]), callback.from_user.id)
        except Exception as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.message.edit_text("✅ دسته حذف شد.")
        await callback.answer()

    @router.message(F.text == "📦 مدیریت محصولات")
    async def product_menu(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        await message.answer(
            "مدیریت محصولات:",
            reply_markup=inline_keyboard(
                [
                    [("➕ افزودن محصول", "aprod:add"), ("📋 فهرست محصولات", "aprod:list")],
                    [("📈 تغییر گروهی قیمت", "bulk:menu")],
                ]
            ),
        )

    @router.callback_query(F.data == "aprod:add")
    async def product_add_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(ProductCreateState.name)
        await callback.message.answer("نام فارسی محصول را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(ProductCreateState.name)
    async def product_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name_fa=(message.text or "").strip())
        await state.set_state(ProductCreateState.slug)
        await message.answer("نام انگلیسی/اسلاگ را بفرستید؛ برای ساخت خودکار، - بفرستید:")

    @router.message(ProductCreateState.slug)
    async def product_slug(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        await state.update_data(slug_en="" if raw == "-" else raw)
        await state.set_state(ProductCreateState.description)
        await message.answer("توضیحات محصول را وارد کنید:")

    @router.message(ProductCreateState.description)
    async def product_description(message: Message, state: FSMContext) -> None:
        await state.update_data(description=message.text or "")
        await state.set_state(ProductCreateState.delivery_type)
        await message.answer(
            "نوع تحویل محصول را انتخاب کنید:",
            reply_markup=inline_keyboard(
                [[("⚡️ خودکار", "pcreate:delivery:auto"), ("👤 دستی", "pcreate:delivery:manual")]]
            ),
        )

    @router.callback_query(ProductCreateState.delivery_type, F.data.startswith("pcreate:delivery:"))
    async def product_delivery_type(callback: CallbackQuery, state: FSMContext) -> None:
        kind = callback.data.split(":")[2]
        if kind == "auto":
            await state.update_data(
                delivery_type=DeliveryType.AUTOMATIC.value, delivery_contents=[]
            )
            await state.set_state(ProductCreateState.delivery_content)
            await callback.message.answer(
                "متن، تصویر، ویدئو یا فایل تحویل خودکار را یکی‌یکی بفرستید؛ "
                "سپس «پایان محتوا» را بزنید.",
                reply_markup=reply_keyboard([["✅ پایان محتوا"], ["❌ انصراف"]]),
            )
        else:
            await state.update_data(delivery_type=DeliveryType.MANUAL.value)
            await state.set_state(ProductCreateState.manual_prompt)
            await callback.message.answer(
                "متنی که برای دریافت اطلاعات مشتری نمایش داده شود وارد کنید؛ "
                "اگر اطلاعاتی لازم نیست، - بفرستید."
            )
        await callback.answer()

    @router.message(ProductCreateState.delivery_content, F.text != "✅ پایان محتوا")
    async def product_delivery_content(message: Message, state: FSMContext) -> None:
        payload = message_to_payload(message)
        if not payload:
            await message.answer("این نوع پیام پشتیبانی نمی‌شود.")
            return
        data = await state.get_data()
        contents = list(data.get("delivery_contents", []))
        if len(contents) >= 50:
            await message.answer("حداکثر ۵۰ محتوای تحویل مجاز است.")
            return
        contents.append(payload)
        await state.update_data(delivery_contents=contents)
        await message.answer(f"✅ محتوا ثبت شد ({len(contents)}/۵۰).")

    @router.message(ProductCreateState.delivery_content, F.text == "✅ پایان محتوا")
    async def product_delivery_done(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if not data.get("delivery_contents"):
            await message.answer("حداقل یک محتوای تحویل ارسال کنید.")
            return
        await choose_product_category(message, state)

    @router.message(ProductCreateState.manual_prompt)
    async def product_manual_prompt(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        await state.update_data(manual_prompt=None if raw == "-" else raw, delivery_contents=[])
        await choose_product_category(message, state)

    async def choose_product_category(message: Message, state: FSMContext) -> None:
        await state.set_state(ProductCreateState.category)
        categories = await service.list_categories()
        rows = [[(c.name, f"pcreate:cat:{c.id}")] for c in categories]
        rows.append([("بدون دسته‌بندی", "pcreate:cat:none")])
        await message.answer("دسته‌بندی محصول را انتخاب کنید:", reply_markup=inline_keyboard(rows))

    @router.callback_query(ProductCreateState.category, F.data.startswith("pcreate:cat:"))
    async def product_category(callback: CallbackQuery, state: FSMContext) -> None:
        raw = callback.data.split(":")[2]
        await state.update_data(category_id=None if raw == "none" else int(raw), photo_file_ids=[])
        await state.set_state(ProductCreateState.photos)
        await callback.message.answer(
            "حداکثر ۱۰ تصویر محصول بفرستید؛ سپس «پایان تصاویر» را بزنید.",
            reply_markup=reply_keyboard([["✅ پایان تصاویر"], ["❌ انصراف"]]),
        )
        await callback.answer()

    @router.message(ProductCreateState.photos, F.photo)
    async def product_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        photos = list(data.get("photo_file_ids", []))
        if len(photos) >= 10:
            await message.answer("حداکثر ۱۰ تصویر مجاز است.")
            return
        photos.append(message.photo[-1].file_id)
        await state.update_data(photo_file_ids=photos)
        await message.answer(f"✅ تصویر ثبت شد ({len(photos)}/۱۰).")

    @router.message(ProductCreateState.photos, F.text == "✅ پایان تصاویر")
    async def product_photos_done(message: Message, state: FSMContext) -> None:
        await state.set_state(ProductCreateState.plan_name)
        await message.answer("نام اولین پلن/اشتراک را وارد کنید:", reply_markup=CANCEL)

    @router.message(ProductCreateState.plan_name)
    async def product_plan_name(message: Message, state: FSMContext) -> None:
        await state.update_data(first_plan_name=message.text or "")
        await state.set_state(ProductCreateState.plan_price)
        await message.answer("قیمت پلن را به تومان وارد کنید:")

    @router.message(ProductCreateState.plan_price)
    async def product_plan_price(message: Message, state: FSMContext) -> None:
        try:
            price = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        data = await state.get_data()
        product = await service.create_product(
            actor=message.from_user.id,
            name_fa=data["name_fa"],
            slug_en=data["slug_en"],
            description=data["description"],
            delivery_type=data["delivery_type"],
            manual_prompt=data.get("manual_prompt"),
            category_id=data.get("category_id"),
            photo_file_ids=data.get("photo_file_ids", []),
            delivery_contents=data.get("delivery_contents", []),
            first_plan_name=data["first_plan_name"],
            first_plan_price_toman=price,
        )
        await state.clear()
        await message.answer(
            f"✅ محصول «{html.escape(product.name_fa)}» ساخته شد.", reply_markup=ADMIN_MENU
        )

    @router.callback_query(F.data == "aprod:list")
    async def product_list(callback: CallbackQuery) -> None:
        products = await service.list_products(active_only=False)
        if not products:
            await callback.answer("محصولی ثبت نشده است.", show_alert=True)
            return
        await callback.message.edit_text(
            "فهرست محصولات:",
            reply_markup=inline_keyboard(
                [
                    [(("✅ " if p.is_active else "❌ ") + p.name_fa, f"aprod:view:{p.id}")]
                    for p in products
                ]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("aprod:view:"))
    async def product_admin_view(callback: CallbackQuery) -> None:
        product_id = int(callback.data.split(":")[2])
        product = await service.get_product(product_id)
        if not product:
            await callback.answer("محصول پیدا نشد.")
            return
        status_action = "off" if product.is_active else "on"
        await callback.message.answer(
            product_text(product),
            reply_markup=inline_keyboard(
                [
                    [
                        ("فعال/غیرفعال", f"aprod:status:{status_action}:{product.id}"),
                        ("🗑 حذف", f"aprod:delete:{product.id}"),
                    ],
                    [
                        ("نام فارسی", f"pedit:name_fa:{product.id}"),
                        ("نام انگلیسی", f"pedit:slug_en:{product.id}"),
                    ],
                    [
                        ("توضیحات", f"pedit:description:{product.id}"),
                        ("تصویر اصلی", f"pedit:primary_photo_file_id:{product.id}"),
                    ],
                    [
                        ("دسته‌بندی", f"peditcat:menu:{product.id}"),
                        ("اطلاعات سفارش دستی", f"pedit:manual_prompt:{product.id}"),
                    ],
                    [
                        ("محتوای تحویل خودکار", f"peditdelivery:{product.id}"),
                        ("مدیریت پلن‌ها", f"plans:list:{product.id}"),
                    ],
                    [("➕ افزودن پلن", f"pedit:addplan:{product.id}")],
                ]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("aprod:status:"))
    async def product_status(callback: CallbackQuery) -> None:
        _, _, action, raw_id = callback.data.split(":")
        await service.set_product_active(int(raw_id), action == "on", callback.from_user.id)
        await callback.answer("وضعیت تغییر کرد.", show_alert=True)

    @router.callback_query(F.data.startswith("aprod:delete:"))
    async def product_delete(callback: CallbackQuery) -> None:
        await service.delete_product(int(callback.data.split(":")[2]), callback.from_user.id)
        await callback.message.edit_text("✅ محصول حذف یا بایگانی شد.")
        await callback.answer()

    @router.callback_query(F.data.startswith("pedit:addplan:"))
    async def add_plan_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(product_id=int(callback.data.split(":")[2]))
        await state.set_state(ProductEditState.add_plan_name)
        await callback.message.answer("نام پلن جدید را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(ProductEditState.add_plan_name)
    async def add_plan_name(message: Message, state: FSMContext) -> None:
        await state.update_data(plan_name=message.text or "")
        await state.set_state(ProductEditState.add_plan_price)
        await message.answer("قیمت پلن را به تومان وارد کنید:")

    @router.message(ProductEditState.add_plan_price)
    async def add_plan_price(message: Message, state: FSMContext) -> None:
        try:
            price = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        data = await state.get_data()
        await service.add_plan(
            int(data["product_id"]), data["plan_name"], price, message.from_user.id
        )
        await state.clear()
        await message.answer("✅ پلن اضافه شد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data.startswith("peditcat:menu:"))
    async def product_category_edit_menu(callback: CallbackQuery) -> None:
        product_id = int(callback.data.split(":")[2])
        categories = await service.list_categories()
        rows = [[(c.name, f"peditcat:set:{product_id}:{c.id}")] for c in categories]
        rows.append([("بدون دسته‌بندی", f"peditcat:set:{product_id}:none")])
        await callback.message.answer(
            "دسته‌بندی جدید را انتخاب کنید:", reply_markup=inline_keyboard(rows)
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("peditcat:set:"))
    async def product_category_edit(callback: CallbackQuery) -> None:
        _, _, raw_product, raw_category = callback.data.split(":")
        value = None if raw_category == "none" else int(raw_category)
        await service.update_product_field(
            int(raw_product), "category_id", value, callback.from_user.id
        )
        await callback.message.edit_text("✅ دسته‌بندی محصول تغییر کرد.")
        await callback.answer()

    @router.callback_query(F.data.startswith("peditdelivery:"))
    async def product_delivery_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(product_id=int(callback.data.split(":")[1]), delivery_contents=[])
        await state.set_state(ProductEditState.delivery_content)
        await callback.message.answer(
            "محتوای جدید تحویل خودکار را ارسال کنید و سپس «پایان محتوا» را بزنید.",
            reply_markup=reply_keyboard([["✅ پایان محتوا"], ["❌ انصراف"]]),
        )
        await callback.answer()

    @router.message(ProductEditState.delivery_content, F.text != "✅ پایان محتوا")
    async def product_delivery_edit_item(message: Message, state: FSMContext) -> None:
        payload = message_to_payload(message)
        if not payload:
            await message.answer("این نوع پیام پشتیبانی نمی‌شود.")
            return
        data = await state.get_data()
        items = list(data.get("delivery_contents", []))
        if len(items) >= 50:
            await message.answer("حداکثر ۵۰ محتوا مجاز است.")
            return
        items.append(payload)
        await state.update_data(delivery_contents=items)
        await message.answer(f"✅ ثبت شد ({len(items)}/۵۰).")

    @router.message(ProductEditState.delivery_content, F.text == "✅ پایان محتوا")
    async def product_delivery_edit_done(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if not data.get("delivery_contents"):
            await message.answer("حداقل یک محتوا بفرستید.")
            return
        await service.replace_delivery_contents(
            int(data["product_id"]), data["delivery_contents"], message.from_user.id
        )
        await state.clear()
        await message.answer("✅ محتوای تحویل خودکار جایگزین شد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data.startswith("plans:list:"))
    async def plans_list(callback: CallbackQuery) -> None:
        product = await service.get_product(int(callback.data.split(":")[2]))
        if not product:
            await callback.answer("محصول پیدا نشد.")
            return
        rows = [
            [(f"{p.name} — {p.price_toman:,}", f"planadmin:view:{p.id}")] for p in product.plans
        ]
        await callback.message.answer("پلن‌ها:", reply_markup=inline_keyboard(rows))
        await callback.answer()

    @router.callback_query(F.data.startswith("planadmin:view:"))
    async def plan_admin_view(callback: CallbackQuery) -> None:
        plan_id = int(callback.data.split(":")[2])
        await callback.message.edit_text(
            f"مدیریت پلن #{plan_id}",
            reply_markup=inline_keyboard(
                [
                    [
                        ("ویرایش نام", f"planadmin:edit:name:{plan_id}"),
                        ("ویرایش قیمت", f"planadmin:edit:price:{plan_id}"),
                    ],
                    [("🗑 حذف", f"planadmin:delete:{plan_id}")],
                ]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("planadmin:edit:"))
    async def plan_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, field, raw_id = callback.data.split(":")
        await state.update_data(plan_id=int(raw_id), plan_field=field)
        await state.set_state(PlanEditState.value)
        await callback.message.answer("مقدار جدید را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(PlanEditState.value)
    async def plan_edit_value(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if data["plan_field"] == "price":
            try:
                value = parse_positive_int(message.text or "")
            except ValueError as exc:
                await message.answer(str(exc))
                return
            await service.update_plan(int(data["plan_id"]), price=value)
        else:
            await service.update_plan(int(data["plan_id"]), name=message.text or "")
        await state.clear()
        await message.answer("✅ پلن ویرایش شد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data.startswith("planadmin:delete:"))
    async def plan_delete(callback: CallbackQuery) -> None:
        await service.delete_plan(int(callback.data.split(":")[2]))
        await callback.message.edit_text("✅ پلن حذف یا غیرفعال شد.")
        await callback.answer()

    @router.callback_query(F.data.startswith("pedit:") & ~F.data.startswith("pedit:addplan:"))
    async def edit_field_start(callback: CallbackQuery, state: FSMContext) -> None:
        _, field, raw_id = callback.data.split(":")
        await state.update_data(product_id=int(raw_id), product_field=field)
        await state.set_state(ProductEditState.value)
        prompt = (
            "تصویر جدید را ارسال کنید."
            if field == "primary_photo_file_id"
            else "مقدار جدید را ارسال کنید:"
        )
        await callback.message.answer(prompt, reply_markup=CANCEL)
        await callback.answer()

    @router.message(ProductEditState.value)
    async def edit_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        field = data["product_field"]
        if field == "primary_photo_file_id":
            if not message.photo:
                await message.answer("یک تصویر ارسال کنید.")
                return
            value = message.photo[-1].file_id
        else:
            value = (
                None
                if field == "manual_prompt" and (message.text or "").strip() == "-"
                else (message.text or "")
            )
        await service.update_product_field(
            int(data["product_id"]), field, value, message.from_user.id
        )
        await state.clear()
        await message.answer("✅ محصول ویرایش شد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data == "bulk:menu")
    async def bulk_menu(callback: CallbackQuery) -> None:
        await callback.message.edit_text(
            "دامنه تغییر قیمت:",
            reply_markup=inline_keyboard(
                [
                    [
                        ("همه محصولات", "bulk:scope:all"),
                        ("یک دسته", "bulk:scope:cat"),
                        ("یک محصول", "bulk:scope:prod"),
                    ]
                ]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("bulk:scope:"))
    async def bulk_scope(callback: CallbackQuery, state: FSMContext) -> None:
        scope = callback.data.split(":")[2]
        if scope == "all":
            await state.update_data(category_id=None, product_id=None)
            await bulk_config_prompt(callback.message)
        elif scope == "cat":
            categories = await service.list_categories()
            await callback.message.edit_text(
                "دسته را انتخاب کنید:",
                reply_markup=inline_keyboard(
                    [[(c.name, f"bulk:target:cat:{c.id}")] for c in categories]
                ),
            )
        else:
            products = await service.list_products(active_only=False)
            await callback.message.edit_text(
                "محصول را انتخاب کنید:",
                reply_markup=inline_keyboard(
                    [[(p.name_fa, f"bulk:target:prod:{p.id}")] for p in products]
                ),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("bulk:target:"))
    async def bulk_target(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, kind, raw_id = callback.data.split(":")
        await state.update_data(
            category_id=int(raw_id) if kind == "cat" else None,
            product_id=int(raw_id) if kind == "prod" else None,
        )
        await bulk_config_prompt(callback.message)
        await callback.answer()

    async def bulk_config_prompt(message: Message) -> None:
        await message.answer(
            "نوع تغییر را انتخاب کنید:",
            reply_markup=inline_keyboard(
                [
                    [
                        ("افزایش درصدی", "bulk:config:increase:percent"),
                        ("کاهش درصدی", "bulk:config:decrease:percent"),
                    ],
                    [
                        ("افزایش مبلغی", "bulk:config:increase:fixed"),
                        ("کاهش مبلغی", "bulk:config:decrease:fixed"),
                    ],
                ]
            ),
        )

    @router.callback_query(F.data.startswith("bulk:config:"))
    async def bulk_config(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, direction, mode = callback.data.split(":")
        await state.update_data(direction=direction, mode=mode)
        await state.set_state(BulkPriceState.value)
        await callback.message.answer("مقدار تغییر را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(BulkPriceState.value)
    async def bulk_value(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        data = await state.get_data()
        count = await service.bulk_change_prices(
            actor=message.from_user.id,
            direction=PriceDirection(data["direction"]),
            mode=PriceChangeMode(data["mode"]),
            value=value,
            category_id=data.get("category_id"),
            product_id=data.get("product_id"),
        )
        await state.clear()
        await message.answer(f"✅ قیمت {count} پلن تغییر کرد.", reply_markup=ADMIN_MENU)

    @router.message(F.text == "📊 آمار ربات")
    async def stats(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        value = await service.stats()
        await message.answer(
            f"<b>آمار فروشگاه</b>\n"
            f"کل کاربران: {value.total_users:,}\nعضویت این ماه: {value.month_users:,}\n"
            f"خریداران: {value.buyers:,}\nفروش کل: {format_toman(value.total_sales_toman)} تومان\n"
            f"فروش این ماه: {format_toman(value.month_sales_toman)} تومان\n"
            f"مجموع شارژ کیف پول: {format_toman(value.total_deposits_toman)} تومان"
        )

    @router.message(F.text == "👥 مدیریت کاربران")
    async def users_start(message: Message, state: FSMContext) -> None:
        if not await allowed(message.from_user.id):
            return
        await state.set_state(UserManageState.user_id)
        await message.answer("شناسه عددی تلگرام کاربر را وارد کنید:", reply_markup=CANCEL)

    @router.message(UserManageState.user_id)
    async def user_lookup(message: Message, state: FSMContext) -> None:
        try:
            telegram_id = int((message.text or "").strip())
        except ValueError:
            await message.answer("شناسه باید عدد باشد.")
            return
        user = await service.admin_find_user(telegram_id)
        if not user:
            await message.answer("کاربر پیدا نشد.")
            return
        await state.clear()
        balance = format_toman(user.balance_toman)
        await message.answer(
            f"کاربر <code>{user.telegram_id}</code>\nموجودی: {balance} تومان\n"
            f"وضعیت: {'مسدود' if user.is_blocked else 'فعال'}",
            reply_markup=inline_keyboard(
                [
                    [
                        ("➕ افزایش موجودی", f"user:balance:add:{user.telegram_id}"),
                        ("➖ کاهش موجودی", f"user:balance:sub:{user.telegram_id}"),
                    ],
                    [
                        ("مسدودکردن", f"user:block:1:{user.telegram_id}"),
                        ("رفع مسدودی", f"user:block:0:{user.telegram_id}"),
                    ],
                ]
            ),
        )

    @router.callback_query(F.data.startswith("user:balance:"))
    async def user_balance_start(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, action, raw_id = callback.data.split(":")
        await state.update_data(user_id=int(raw_id), sign=1 if action == "add" else -1)
        await state.set_state(UserManageState.balance)
        await callback.message.answer("مبلغ را به تومان وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(UserManageState.balance)
    async def user_balance(message: Message, state: FSMContext) -> None:
        try:
            amount = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        data = await state.get_data()
        user = await service.admin_adjust_balance(
            int(data["user_id"]), amount * int(data["sign"]), message.from_user.id
        )
        await state.clear()
        await message.answer(
            f"✅ موجودی جدید: {format_toman(user.balance_toman)} تومان", reply_markup=ADMIN_MENU
        )

    @router.callback_query(F.data.startswith("user:block:"))
    async def user_block(callback: CallbackQuery) -> None:
        _, _, raw_blocked, raw_id = callback.data.split(":")
        await service.admin_set_blocked(int(raw_id), raw_blocked == "1", callback.from_user.id)
        await callback.answer("وضعیت کاربر ذخیره شد.", show_alert=True)

    @router.message(F.text == "📨 مدیریت پیام‌ها")
    async def messages_menu(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        await message.answer(
            "مدیریت پیام‌ها:",
            reply_markup=inline_keyboard(
                [
                    [("ارسال مستقیم", "msg:direct")],
                    [("همگانی (کپی)", "msg:broadcast"), ("همگانی (فوروارد)", "msg:forward")],
                ]
            ),
        )

    @router.callback_query(F.data == "msg:direct")
    async def direct_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(MessageManageState.direct_user_id)
        await callback.message.answer("شناسه عددی گیرنده را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(MessageManageState.direct_user_id)
    async def direct_id(message: Message, state: FSMContext) -> None:
        try:
            target = int(message.text or "")
        except ValueError:
            await message.answer("شناسه باید عدد باشد.")
            return
        if not await service.admin_find_user(target):
            await message.answer("کاربر در فروشگاه پیدا نشد.")
            return
        await state.update_data(target=target)
        await state.set_state(MessageManageState.direct_message)
        await message.answer("پیام را ارسال کنید:")

    @router.message(MessageManageState.direct_message)
    async def direct_message(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        await message.copy_to(int(data["target"]))
        await state.clear()
        await message.answer("✅ پیام ارسال شد.", reply_markup=ADMIN_MENU)

    @router.callback_query(F.data.in_({"msg:broadcast", "msg:forward"}))
    async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
        mode = "forward" if callback.data.endswith("forward") else "copy"
        await state.update_data(broadcast_mode=mode)
        await state.set_state(
            MessageManageState.forward if mode == "forward" else MessageManageState.broadcast
        )
        await callback.message.answer("پیام همگانی را ارسال کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(MessageManageState.broadcast)
    @router.message(MessageManageState.forward)
    async def broadcast(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        recipients = await service.list_user_telegram_ids()
        sent = failed = 0
        for target in recipients:
            try:
                if data["broadcast_mode"] == "forward":
                    await message.bot.forward_message(target, message.chat.id, message.message_id)
                else:
                    await message.copy_to(target)
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1
        await state.clear()
        await message.answer(
            f"ارسال پایان یافت؛ موفق: {sent}، ناموفق: {failed}", reply_markup=ADMIN_MENU
        )

    @router.message(F.text == "🎟 کدهای تخفیف")
    async def discounts_menu(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        discounts = await service.list_discounts()
        lines = [
            f"• {html.escape(d.code)} | {d.value:,} "
            f"{('%' if d.kind == DiscountKindDB.PERCENT else 'تومان')} | "
            f"{d.usage_count}/{d.usage_limit}"
            for d in discounts
            if d.is_active
        ]
        rows = [[("➕ کد مبلغی", "discount:add:fixed"), ("➕ کد درصدی", "discount:add:percent")]]
        rows.extend(
            [[(("🗑 " + d.code), f"discount:delete:{d.id}")] for d in discounts if d.is_active]
        )
        await message.answer(
            f"<b>کدهای تخفیف</b>\n{chr(10).join(lines) or 'کدی ثبت نشده است.'}",
            reply_markup=inline_keyboard(rows),
        )

    @router.callback_query(F.data.startswith("discount:add:"))
    async def discount_add(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(discount_kind=callback.data.split(":")[2])
        await state.set_state(DiscountState.code)
        await callback.message.answer("کد تخفیف را وارد کنید:", reply_markup=CANCEL)
        await callback.answer()

    @router.message(DiscountState.code)
    async def discount_code(message: Message, state: FSMContext) -> None:
        await state.update_data(discount_code=message.text or "")
        await state.set_state(DiscountState.value)
        await message.answer("مبلغ یا درصد تخفیف را وارد کنید:")

    @router.message(DiscountState.value)
    async def discount_value(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.update_data(discount_value=value)
        await state.set_state(DiscountState.usage_limit)
        await message.answer("حداکثر تعداد استفاده را وارد کنید:")

    @router.message(DiscountState.usage_limit)
    async def discount_limit(message: Message, state: FSMContext) -> None:
        try:
            limit = parse_positive_int(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        data = await state.get_data()
        if data["discount_kind"] == "percent" and int(data["discount_value"]) > 100:
            await message.answer("درصد تخفیف نمی‌تواند بیشتر از ۱۰۰ باشد.")
            return
        discount = await service.create_discount(
            code=data["discount_code"],
            value=int(data["discount_value"]),
            usage_limit=limit,
            actor=message.from_user.id,
            kind=DiscountKindDB(data["discount_kind"]),
        )
        await state.clear()
        await message.answer(
            f"✅ کد {html.escape(discount.code)} ساخته شد.", reply_markup=ADMIN_MENU
        )

    @router.callback_query(F.data.startswith("discount:delete:"))
    async def discount_delete(callback: CallbackQuery) -> None:
        await service.delete_discount(int(callback.data.split(":")[2]), callback.from_user.id)
        await callback.message.edit_text("✅ کد تخفیف غیرفعال شد.")
        await callback.answer()

    @router.message(F.text == "🛠 مدیریت عمومی")
    async def general(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        settings = await service.get_settings()
        channels = await service.list_required_channels()
        await message.answer(
            f"<b>مدیریت عمومی</b>\n"
            f"پشتیبانی: {html.escape(settings.support_account or 'تنظیم نشده')}\n"
            f"ادمین دوم: <code>{settings.secondary_admin_id or 'تنظیم نشده'}</code>\n"
            f"کانال‌های عضویت اجباری: {len(channels)}",
            reply_markup=inline_keyboard(
                [
                    [
                        ("متن شروع", "setting:value:start_text"),
                        ("تصویر شروع", "setting:value:start_photo_file_id"),
                    ],
                    [
                        ("حساب پشتیبانی", "setting:value:support_account"),
                        ("ادمین دوم", "setting:value:secondary_admin_id"),
                    ],
                    [
                        ("کانال رضایت", "setting:value:satisfaction_channel_id"),
                        ("کانال لاگ", "setting:value:log_channel_id"),
                    ],
                    [("پاداش معرفی", "setting:value:referral_reward_toman")],
                    [("➕ کانال عضویت", "channel:add"), ("📋 کانال‌ها", "channel:list")],
                ]
            ),
        )

    @router.callback_query(F.data == "channel:add")
    async def channel_add_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(SettingsState.channel)
        await callback.message.answer(
            "کانال را با این قالب بفرستید:\n<code>@channel | عنوان کانال | https://t.me/channel</code>\n"
            "ربات باید در کانال ادمین باشد.",
            reply_markup=CANCEL,
        )
        await callback.answer()

    @router.message(SettingsState.channel)
    async def channel_add(message: Message, state: FSMContext) -> None:
        parts = [part.strip() for part in (message.text or "").split("|")]
        if len(parts) < 2:
            await message.answer("قالب ورودی صحیح نیست.")
            return
        channel = await service.add_required_channel(
            chat_id=parts[0],
            title=parts[1],
            invite_url=parts[2] if len(parts) > 2 else None,
            actor=message.from_user.id,
        )
        await state.clear()
        await message.answer(
            f"✅ کانال {html.escape(channel.title)} اضافه شد.", reply_markup=ADMIN_MENU
        )

    @router.callback_query(F.data == "channel:list")
    async def channel_list(callback: CallbackQuery) -> None:
        channels = await service.list_required_channels()
        if not channels:
            await callback.answer("کانالی ثبت نشده است.", show_alert=True)
            return
        await callback.message.edit_text(
            "کانال‌های عضویت اجباری:",
            reply_markup=inline_keyboard(
                [[(("🗑 " + c.title), f"channel:delete:{c.id}")] for c in channels]
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("channel:delete:"))
    async def channel_delete(callback: CallbackQuery) -> None:
        await service.delete_required_channel(
            int(callback.data.split(":")[2]), callback.from_user.id
        )
        await callback.message.edit_text("✅ کانال حذف شد.")
        await callback.answer()

    @router.callback_query(F.data.startswith("topup:"))
    async def review_topup(callback: CallbackQuery) -> None:
        if not await allowed(callback.from_user.id):
            await callback.answer("دسترسی ندارید.", show_alert=True)
            return
        _, action, raw_id = callback.data.split(":")
        try:
            tx, user_id = await service.review_topup(
                int(raw_id), approve=action == "ok", reviewer_telegram_id=callback.from_user.id
            )
        except Exception as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        result = "تأیید" if tx.status == TransactionStatus.APPROVED else "رد"
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\nنتیجه: {result}"
        )
        await callback.bot.send_message(user_id, f"رسید شارژ #{tx.id} {result} شد.")
        await callback.answer()

    @router.callback_query(F.data.startswith("order:delivered:"))
    async def order_delivered(callback: CallbackQuery) -> None:
        if not await allowed(callback.from_user.id):
            await callback.answer("دسترسی ندارید.", show_alert=True)
            return
        order_id = int(callback.data.split(":")[2])
        await service.mark_order_delivered(order_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"✅ سفارش #{order_id} تحویل‌شده ثبت شد.")
        await callback.answer()

    @router.message(F.text == "💾 دریافت بکاپ")
    async def backup(message: Message) -> None:
        if not await allowed(message.from_user.id):
            return
        await message.answer("در حال ساخت بکاپ امن فروشگاه…")
        content = await generate_sql_backup(service)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        await message.answer_document(
            BufferedInputFile(content, filename=f"store-{service.tenant_id}-{stamp}.sql"),
            caption="✅ بکاپ SQL فروشگاه آماده است. توکن ربات در این فایل قرار نمی‌گیرد.",
        )

    return router
