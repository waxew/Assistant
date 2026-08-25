from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=item) for item in row] for row in rows],
        resize_keyboard=True,
    )


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=data) for title, data in row]
            for row in rows
        ]
    )


BUILDER_MENU = reply_keyboard(
    [
        ["🛠 ساخت ربات فروشگاه"],
        ["🤖 ربات‌های من", "♻️ تمدید اشتراک"],
        ["👤 حساب کاربری", "💬 پشتیبانی"],
    ]
)

STORE_MENU = reply_keyboard(
    [
        ["🛍 محصولات", "🔎 جستجوی محصول"],
        ["👤 حساب کاربری", "📦 پیگیری سفارش"],
        ["💬 پشتیبانی", "⚙️ پنل مدیریت"],
    ]
)

ADMIN_MENU = reply_keyboard(
    [
        ["💳 بخش مالی", "🗂 مدیریت دسته‌ها"],
        ["📦 مدیریت محصولات", "📊 آمار ربات"],
        ["👥 مدیریت کاربران", "📨 مدیریت پیام‌ها"],
        ["🎟 کدهای تخفیف", "🛠 مدیریت عمومی"],
        ["💾 دریافت بکاپ", "🏠 منوی فروشگاه"],
    ]
)

CANCEL = reply_keyboard([["❌ انصراف"]])
