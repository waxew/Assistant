from __future__ import annotations

import html
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from app.models import DeliveryType, OrderStatus, Product, RequiredChannel
from app.services.store import DeliveryPayload

ORDER_LABELS = {
    OrderStatus.PENDING_PAYMENT: "در انتظار پرداخت",
    OrderStatus.PROCESSING: "در حال پردازش",
    OrderStatus.DELIVERED: "تحویل‌شده",
    OrderStatus.CANCELLED: "لغوشده",
    OrderStatus.REFUNDED: "مرجوع‌شده",
}


def product_text(product: Product) -> str:
    category = product.category.name if product.category else "بدون دسته‌بندی"
    plans = "\n".join(
        f"• {html.escape(plan.name)}: {plan.price_toman:,} تومان"
        for plan in product.plans
        if plan.is_active
    )
    delivery = "آنی و خودکار" if product.delivery_type == DeliveryType.AUTOMATIC else "دستی"
    return (
        f"<b>{html.escape(product.name_fa)}</b>\n"
        f"دسته: {html.escape(category)}\n"
        f"نوع تحویل: {delivery}\n\n{html.escape(product.description)}\n\n"
        f"<b>پلن‌ها:</b>\n{plans or 'پلن فعالی ندارد'}"
    )


def message_to_payload(message: Message) -> dict[str, Any] | None:
    caption = message.caption
    if message.text:
        return {"content_type": "text", "text": message.text, "caption": None, "file_id": None}
    mapping = (
        ("photo", message.photo[-1].file_id if message.photo else None),
        ("video", message.video.file_id if message.video else None),
        ("document", message.document.file_id if message.document else None),
        ("audio", message.audio.file_id if message.audio else None),
        ("voice", message.voice.file_id if message.voice else None),
        ("animation", message.animation.file_id if message.animation else None),
    )
    for content_type, file_id in mapping:
        if file_id:
            return {
                "content_type": content_type,
                "file_id": file_id,
                "text": None,
                "caption": caption,
            }
    return None


async def send_delivery(bot: Bot, chat_id: int, payload: DeliveryPayload) -> None:
    kwargs = {"chat_id": chat_id, "caption": payload.caption}
    if payload.content_type == "text":
        await bot.send_message(chat_id, payload.text or "")
    elif payload.content_type == "photo":
        await bot.send_photo(photo=payload.file_id, **kwargs)
    elif payload.content_type == "video":
        await bot.send_video(video=payload.file_id, **kwargs)
    elif payload.content_type == "document":
        await bot.send_document(document=payload.file_id, **kwargs)
    elif payload.content_type == "audio":
        await bot.send_audio(audio=payload.file_id, **kwargs)
    elif payload.content_type == "voice":
        await bot.send_voice(voice=payload.file_id, **kwargs)
    elif payload.content_type == "animation":
        await bot.send_animation(animation=payload.file_id, **kwargs)


async def missing_required_channels(
    bot: Bot, user_id: int, channels: list[RequiredChannel]
) -> list[RequiredChannel]:
    missing: list[RequiredChannel] = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.chat_id, user_id)
            if member.status in {"left", "kicked"}:
                missing.append(channel)
        except TelegramForbiddenError:
            missing.append(channel)
        except TelegramBadRequest:
            # Invalid channel settings should not lock every customer out.
            continue
    return missing
