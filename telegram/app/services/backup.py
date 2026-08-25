from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import select

from app.models import (
    AuditLog,
    Category,
    DeliveryContent,
    DiscountCode,
    Order,
    Product,
    ProductImage,
    ProductPlan,
    RequiredChannel,
    StoreSettings,
    StoreTransaction,
    StoreUser,
)
from app.services.store import StoreService


def _literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, date | datetime):
        value = value.isoformat()
    return "'" + str(value).replace("'", "''") + "'"


def _insert(instance: object) -> str:
    table = instance.__table__
    columns = [column.name for column in table.columns]
    values = [_literal(getattr(instance, column)) for column in columns]
    quoted = ", ".join(f'"{name}"' for name in columns)
    # Table and column names come only from SQLAlchemy metadata; values are escaped above.
    return f'INSERT INTO "{table.name}" ({quoted}) VALUES ({", ".join(values)});'  # noqa: S608


async def generate_sql_backup(service: StoreService) -> bytes:
    """Generate a tenant-scoped, human-readable SQL data backup without bot tokens."""
    async with service.sessions() as session:
        settings = await session.get(StoreSettings, service.tenant_id)
        categories = list(
            (
                await session.scalars(
                    select(Category).where(Category.tenant_id == service.tenant_id)
                )
            ).all()
        )
        products = list(
            (
                await session.scalars(select(Product).where(Product.tenant_id == service.tenant_id))
            ).all()
        )
        product_ids = [item.id for item in products]
        images = (
            []
            if not product_ids
            else list(
                (
                    await session.scalars(
                        select(ProductImage).where(ProductImage.product_id.in_(product_ids))
                    )
                ).all()
            )
        )
        plans = (
            []
            if not product_ids
            else list(
                (
                    await session.scalars(
                        select(ProductPlan).where(ProductPlan.product_id.in_(product_ids))
                    )
                ).all()
            )
        )
        contents = (
            []
            if not product_ids
            else list(
                (
                    await session.scalars(
                        select(DeliveryContent).where(DeliveryContent.product_id.in_(product_ids))
                    )
                ).all()
            )
        )
        users = list(
            (
                await session.scalars(
                    select(StoreUser).where(StoreUser.tenant_id == service.tenant_id)
                )
            ).all()
        )
        discounts = list(
            (
                await session.scalars(
                    select(DiscountCode).where(DiscountCode.tenant_id == service.tenant_id)
                )
            ).all()
        )
        orders = list(
            (await session.scalars(select(Order).where(Order.tenant_id == service.tenant_id))).all()
        )
        transactions = list(
            (
                await session.scalars(
                    select(StoreTransaction).where(StoreTransaction.tenant_id == service.tenant_id)
                )
            ).all()
        )
        channels = list(
            (
                await session.scalars(
                    select(RequiredChannel).where(RequiredChannel.tenant_id == service.tenant_id)
                )
            ).all()
        )
        audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(AuditLog.tenant_id == service.tenant_id)
                )
            ).all()
        )

    groups = [
        ("store_settings", [settings] if settings else []),
        ("categories", categories),
        ("products", products),
        ("product_images", images),
        ("product_plans", plans),
        ("delivery_contents", contents),
        ("store_users", users),
        ("discount_codes", discounts),
        ("orders", orders),
        ("store_transactions", transactions),
        ("required_channels", channels),
        ("audit_logs", audits),
    ]
    lines = [
        "-- Telegram Store Builder tenant backup",
        f"-- tenant_id: {service.tenant_id}",
        "-- Restore into a compatible empty schema; tenant_bots row must already exist.",
        "BEGIN;",
    ]
    for name, rows in groups:
        lines.append(f"\n-- {name}")
        lines.extend(_insert(row) for row in rows)
    lines.append("\nCOMMIT;\n")
    return "\n".join(lines).encode("utf-8")
