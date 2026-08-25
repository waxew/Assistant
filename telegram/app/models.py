from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class BotStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class DeliveryType(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TransactionKind(StrEnum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
    REFUND = "refund"
    REFERRAL = "referral"
    SUBSCRIPTION = "subscription"


class DiscountKindDB(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class BuilderUser(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "builder_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    balance_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("builder_users.id"))
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    bots: Mapped[list[TenantBot]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[BuilderTransaction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class BuilderTransaction(Base, CreatedAtMixin):
    __tablename__ = "builder_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("builder_users.id", ondelete="CASCADE"))
    kind: Mapped[TransactionKind] = mapped_column(
        Enum(TransactionKind, native_enum=False), default=TransactionKind.DEPOSIT
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False), default=TransactionStatus.PENDING
    )
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(500), default="")
    receipt_file_id: Mapped[str | None] = mapped_column(String(255))
    reviewed_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)

    user: Mapped[BuilderUser] = relationship(back_populates="transactions")


class TenantBot(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "tenant_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("builder_users.id", ondelete="CASCADE"))
    telegram_bot_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    encrypted_token: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[BotStatus] = mapped_column(
        Enum(BotStatus, native_enum=False), default=BotStatus.TRIAL, index=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    owner: Mapped[BuilderUser] = relationship(back_populates="bots")
    settings: Mapped[StoreSettings] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", uselist=False
    )


class StoreSettings(Base, UpdatedAtMixin):
    __tablename__ = "store_settings"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_bots.id", ondelete="CASCADE"), primary_key=True
    )
    start_text: Mapped[str] = mapped_column(Text, default="👋 خوش آمدید.")
    start_photo_file_id: Mapped[str | None] = mapped_column(String(255))
    support_account: Mapped[str | None] = mapped_column(String(128))
    secondary_admin_id: Mapped[int | None] = mapped_column(BigInteger)
    satisfaction_channel_id: Mapped[str | None] = mapped_column(String(128))
    log_channel_id: Mapped[str | None] = mapped_column(String(128))
    card_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    card_number: Mapped[str | None] = mapped_column(String(32))
    card_holder: Mapped[str | None] = mapped_column(String(128))
    zarinpal_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    zarinpal_merchant_id: Mapped[str | None] = mapped_column(String(64))
    referral_reward_toman: Mapped[int] = mapped_column(BigInteger, default=20_000)
    currency_label: Mapped[str] = mapped_column(String(32), default="تومان")

    tenant: Mapped[TenantBot] = relationship(back_populates="settings")


class StoreUser(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "store_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "telegram_id", name="uq_store_user_tenant_telegram"),
        UniqueConstraint("tenant_id", "referral_code", name="uq_store_user_tenant_referral"),
        Index("ix_store_user_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    balance_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    referral_code: Mapped[str] = mapped_column(String(20), index=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("store_users.id"))
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    orders: Mapped[list[Order]] = relationship(back_populates="user")
    transactions: Mapped[list[StoreTransaction]] = relationship(back_populates="user")


class Category(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_category_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deep_link_key", name="uq_product_tenant_deep_link"),
        Index("ix_product_tenant_category", "tenant_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    name_fa: Mapped[str] = mapped_column(String(255))
    slug_en: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    delivery_type: Mapped[DeliveryType] = mapped_column(
        Enum(DeliveryType, native_enum=False), default=DeliveryType.MANUAL
    )
    manual_prompt: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_photo_file_id: Mapped[str | None] = mapped_column(String(255))
    deep_link_key: Mapped[str] = mapped_column(String(32))

    category: Mapped[Category | None] = relationship(back_populates="products")
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.sort_order"
    )
    plans: Mapped[list[ProductPlan]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductPlan.id"
    )
    delivery_contents: Mapped[list[DeliveryContent]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="DeliveryContent.sort_order",
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    file_id: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductPlan(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "product_plans"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_plan_product_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    price_toman: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped[Product] = relationship(back_populates="plans")
    orders: Mapped[list[Order]] = relationship(back_populates="plan")


class DeliveryContent(Base):
    __tablename__ = "delivery_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    content_type: Mapped[str] = mapped_column(String(32))
    file_id: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="delivery_contents")


class DiscountCode(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "discount_codes"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_discount_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64))
    kind: Mapped[DiscountKindDB] = mapped_column(
        Enum(DiscountKindDB, native_enum=False), default=DiscountKindDB.FIXED
    )
    value: Mapped[int] = mapped_column(BigInteger)
    usage_limit: Mapped[int] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Order(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tracking_code", name="uq_order_tenant_tracking"),
        Index("ix_order_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("store_users.id", ondelete="RESTRICT"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("product_plans.id", ondelete="RESTRICT"))
    discount_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="SET NULL")
    )
    base_amount_toman: Mapped[int] = mapped_column(BigInteger)
    discount_amount_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    final_amount_toman: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), default=OrderStatus.PROCESSING, index=True
    )
    tracking_code: Mapped[str] = mapped_column(String(20), index=True)
    manual_info: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[StoreUser] = relationship(back_populates="orders")
    plan: Mapped[ProductPlan] = relationship(back_populates="orders")


class StoreTransaction(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "store_transactions"
    __table_args__ = (
        Index("ix_store_transaction_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "authority", name="uq_store_transaction_authority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("store_users.id", ondelete="RESTRICT"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    kind: Mapped[TransactionKind] = mapped_column(
        Enum(TransactionKind, native_enum=False), default=TransactionKind.DEPOSIT
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False), default=TransactionStatus.PENDING
    )
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(500), default="")
    payment_method: Mapped[str | None] = mapped_column(String(32))
    receipt_file_id: Mapped[str | None] = mapped_column(String(255))
    authority: Mapped[str | None] = mapped_column(String(128))
    external_ref: Mapped[str | None] = mapped_column(String(128))
    reviewed_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)

    user: Mapped[StoreUser] = relationship(back_populates="transactions")


class RequiredChannel(Base, CreatedAtMixin):
    __tablename__ = "required_channels"
    __table_args__ = (UniqueConstraint("tenant_id", "chat_id", name="uq_channel_tenant_chat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    chat_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255), default="کانال")
    invite_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SupportRelay(Base, CreatedAtMixin):
    __tablename__ = "support_relays"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "admin_chat_id", "admin_message_id", name="uq_support_relay_message"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    user_chat_id: Mapped[int] = mapped_column(BigInteger)
    admin_chat_id: Mapped[int] = mapped_column(BigInteger)
    admin_message_id: Mapped[int] = mapped_column(BigInteger)


class BroadcastJob(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "broadcast_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    created_by_telegram_id: Mapped[int] = mapped_column(BigInteger)
    mode: Mapped[str] = mapped_column(String(16), default="copy")
    source_chat_id: Mapped[int] = mapped_column(BigInteger)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)


class AuditLog(Base, CreatedAtMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_bots.id", ondelete="CASCADE"))
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[str] = mapped_column(Text, default="")
