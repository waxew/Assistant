from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import (
    DiscountKind,
    PriceChangeMode,
    PriceDirection,
    changed_price,
    discount_amount,
    make_referral_code,
    make_tracking_code,
    slugify_ascii,
)
from app.models import (
    AuditLog,
    BotStatus,
    Category,
    DeliveryContent,
    DeliveryType,
    DiscountCode,
    DiscountKindDB,
    Order,
    OrderStatus,
    Product,
    ProductImage,
    ProductPlan,
    RequiredChannel,
    StoreSettings,
    StoreTransaction,
    StoreUser,
    SupportRelay,
    TenantBot,
    TransactionKind,
    TransactionStatus,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class DeliveryPayload:
    content_type: str
    file_id: str | None
    text: str | None
    caption: str | None


@dataclass(frozen=True, slots=True)
class PurchaseOutcome:
    ok: bool
    reason: str
    required_toman: int = 0
    order_id: int | None = None
    tracking_code: str | None = None
    product_name: str = ""
    plan_name: str = ""
    final_amount_toman: int = 0
    delivery_type: DeliveryType | None = None
    manual_prompt: str | None = None
    delivery: tuple[DeliveryPayload, ...] = ()
    referral_user_telegram_id: int | None = None
    referral_reward_toman: int = 0


@dataclass(frozen=True, slots=True)
class StoreStats:
    total_users: int
    month_users: int
    buyers: int
    total_sales_toman: int
    month_sales_toman: int
    total_deposits_toman: int


class StoreService:
    def __init__(self, tenant_id: int, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.tenant_id = tenant_id
        self.sessions = sessions

    async def get_tenant(self) -> TenantBot:
        async with self.sessions() as session:
            tenant = await session.scalar(
                select(TenantBot)
                .where(TenantBot.id == self.tenant_id)
                .options(selectinload(TenantBot.owner), selectinload(TenantBot.settings))
            )
            if tenant is None:
                raise LookupError("Tenant bot not found")
            return tenant

    async def get_settings(self) -> StoreSettings:
        async with self.sessions() as session:
            settings = await session.get(StoreSettings, self.tenant_id)
            if settings is None:
                raise LookupError("Store settings not found")
            return settings

    async def admin_ids(self) -> frozenset[int]:
        tenant = await self.get_tenant()
        ids = {tenant.owner.telegram_id}
        if tenant.settings and tenant.settings.secondary_admin_id:
            ids.add(tenant.settings.secondary_admin_id)
        return frozenset(ids)

    async def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in await self.admin_ids()

    async def ensure_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        full_name: str,
        referral_code: str | None = None,
    ) -> StoreUser:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == telegram_id,
                )
            )
            if user:
                user.username = username
                user.full_name = full_name
                user.last_seen_at = utc_now()
                await session.commit()
                return user

            referred_by: int | None = None
            if referral_code:
                referrer = await session.scalar(
                    select(StoreUser).where(
                        StoreUser.tenant_id == self.tenant_id,
                        StoreUser.referral_code == referral_code,
                    )
                )
                if referrer and referrer.telegram_id != telegram_id:
                    referred_by = referrer.id

            code = await self._unique_referral_code(session)
            user = StoreUser(
                tenant_id=self.tenant_id,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                referral_code=code,
                referred_by_user_id=referred_by,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def _unique_referral_code(self, session: AsyncSession) -> str:
        for _ in range(10):
            code = make_referral_code()
            exists = await session.scalar(
                select(StoreUser.id).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.referral_code == code,
                )
            )
            if not exists:
                return code
        return secrets.token_hex(10)

    async def get_user_by_telegram_id(self, telegram_id: int) -> StoreUser | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(StoreUser).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == telegram_id,
                )
            )

    async def list_categories(self, *, active_only: bool = True) -> list[Category]:
        async with self.sessions() as session:
            query = select(Category).where(Category.tenant_id == self.tenant_id)
            if active_only:
                query = query.where(Category.is_active.is_(True))
            query = query.order_by(Category.sort_order, Category.id)
            return list((await session.scalars(query)).all())

    async def create_category(self, name: str) -> Category:
        cleaned = name.strip()[:128]
        if not cleaned:
            raise ValueError("نام دسته‌بندی خالی است.")
        async with self.sessions() as session:
            exists = await session.scalar(
                select(Category.id).where(
                    Category.tenant_id == self.tenant_id, Category.name == cleaned
                )
            )
            if exists:
                raise ValueError("این دسته‌بندی قبلاً ساخته شده است.")
            category = Category(tenant_id=self.tenant_id, name=cleaned)
            session.add(category)
            await session.flush()
            await self._audit(session, None, "category.create", "category", category.id, cleaned)
            await session.commit()
            return category

    async def rename_category(self, category_id: int, name: str, actor: int) -> None:
        async with self.sessions() as session:
            category = await session.scalar(
                select(Category).where(
                    Category.id == category_id, Category.tenant_id == self.tenant_id
                )
            )
            if not category:
                raise LookupError("دسته‌بندی پیدا نشد.")
            category.name = name.strip()[:128]
            await self._audit(
                session, actor, "category.rename", "category", category.id, category.name
            )
            await session.commit()

    async def delete_category(self, category_id: int, actor: int) -> None:
        async with self.sessions() as session:
            category = await session.scalar(
                select(Category).where(
                    Category.id == category_id, Category.tenant_id == self.tenant_id
                )
            )
            if not category:
                raise LookupError("دسته‌بندی پیدا نشد.")
            products_count = await session.scalar(
                select(func.count(Product.id)).where(Product.category_id == category.id)
            )
            if products_count:
                raise ValueError("ابتدا محصولات این دسته را منتقل یا حذف کنید.")
            await self._audit(
                session, actor, "category.delete", "category", category.id, category.name
            )
            await session.delete(category)
            await session.commit()

    async def list_products(
        self, category_id: int | None = None, *, active_only: bool = True
    ) -> list[Product]:
        async with self.sessions() as session:
            query = (
                select(Product)
                .where(Product.tenant_id == self.tenant_id)
                .options(selectinload(Product.plans), selectinload(Product.category))
            )
            if category_id is not None:
                query = query.where(Product.category_id == category_id)
            if active_only:
                query = query.where(Product.is_active.is_(True))
            return list((await session.scalars(query.order_by(Product.id))).all())

    async def search_products(self, term: str, *, limit: int = 20) -> list[Product]:
        cleaned = term.strip()
        async with self.sessions() as session:
            query = (
                select(Product)
                .where(
                    Product.tenant_id == self.tenant_id,
                    Product.is_active.is_(True),
                    or_(
                        Product.name_fa.ilike(f"%{cleaned}%"),
                        Product.slug_en.ilike(f"%{cleaned}%"),
                    ),
                )
                .options(selectinload(Product.plans))
                .limit(limit)
            )
            return list((await session.scalars(query)).all())

    async def get_product(self, product_id: int, *, active_only: bool = False) -> Product | None:
        async with self.sessions() as session:
            query = (
                select(Product)
                .where(Product.id == product_id, Product.tenant_id == self.tenant_id)
                .options(
                    selectinload(Product.category),
                    selectinload(Product.images),
                    selectinload(Product.plans),
                    selectinload(Product.delivery_contents),
                )
            )
            if active_only:
                query = query.where(Product.is_active.is_(True))
            return await session.scalar(query)

    async def get_product_by_deep_link(self, key: str) -> Product | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(Product)
                .where(
                    Product.tenant_id == self.tenant_id,
                    Product.deep_link_key == key,
                    Product.is_active.is_(True),
                )
                .options(
                    selectinload(Product.category),
                    selectinload(Product.images),
                    selectinload(Product.plans),
                )
            )

    async def create_product(
        self,
        *,
        actor: int,
        name_fa: str,
        slug_en: str,
        description: str,
        delivery_type: DeliveryType | str,
        manual_prompt: str | None,
        category_id: int | None,
        photo_file_ids: Iterable[str],
        delivery_contents: Iterable[dict[str, Any]],
        first_plan_name: str,
        first_plan_price_toman: int,
    ) -> Product:
        photos = list(photo_file_ids)[:10]
        contents = list(delivery_contents)[:50]
        async with self.sessions() as session:
            if category_id is not None:
                valid_category = await session.scalar(
                    select(Category.id).where(
                        Category.id == category_id, Category.tenant_id == self.tenant_id
                    )
                )
                if not valid_category:
                    raise ValueError("دسته‌بندی معتبر نیست.")

            deep_link_key = secrets.token_urlsafe(8).replace("-", "").replace("_", "")
            product = Product(
                tenant_id=self.tenant_id,
                category_id=category_id,
                name_fa=name_fa.strip()[:255],
                slug_en=slugify_ascii(slug_en, fallback=f"product_{deep_link_key[:6]}")[:128],
                description=description.strip(),
                delivery_type=DeliveryType(delivery_type),
                manual_prompt=manual_prompt.strip() if manual_prompt else None,
                primary_photo_file_id=photos[0] if photos else None,
                deep_link_key=deep_link_key,
            )
            session.add(product)
            await session.flush()
            for index, file_id in enumerate(photos):
                session.add(ProductImage(product_id=product.id, file_id=file_id, sort_order=index))
            for index, payload in enumerate(contents):
                session.add(
                    DeliveryContent(
                        product_id=product.id,
                        content_type=str(payload.get("content_type", "text"))[:32],
                        file_id=payload.get("file_id"),
                        text=payload.get("text"),
                        caption=payload.get("caption"),
                        sort_order=index,
                    )
                )
            session.add(
                ProductPlan(
                    product_id=product.id,
                    name=first_plan_name.strip()[:255],
                    price_toman=first_plan_price_toman,
                )
            )
            await self._audit(
                session, actor, "product.create", "product", product.id, product.name_fa
            )
            await session.commit()
            return await self._load_product(session, product.id)

    async def _load_product(self, session: AsyncSession, product_id: int) -> Product:
        product = await session.scalar(
            select(Product)
            .where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            .options(
                selectinload(Product.images),
                selectinload(Product.plans),
                selectinload(Product.delivery_contents),
            )
        )
        if not product:
            raise LookupError("محصول پیدا نشد.")
        return product

    async def add_plan(
        self, product_id: int, name: str, price_toman: int, actor: int
    ) -> ProductPlan:
        async with self.sessions() as session:
            product = await session.scalar(
                select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            )
            if not product:
                raise LookupError("محصول پیدا نشد.")
            plan = ProductPlan(
                product_id=product.id, name=name.strip()[:255], price_toman=price_toman
            )
            session.add(plan)
            await session.flush()
            await self._audit(session, actor, "plan.create", "plan", plan.id, plan.name)
            await session.commit()
            return plan

    async def set_product_active(self, product_id: int, active: bool, actor: int) -> None:
        async with self.sessions() as session:
            product = await session.scalar(
                select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            )
            if not product:
                raise LookupError("محصول پیدا نشد.")
            product.is_active = active
            await self._audit(session, actor, "product.status", "product", product.id, str(active))
            await session.commit()

    async def update_product_field(
        self, product_id: int, field: str, value: Any, actor: int
    ) -> None:
        allowed = {
            "name_fa",
            "slug_en",
            "description",
            "category_id",
            "primary_photo_file_id",
            "manual_prompt",
        }
        if field not in allowed:
            raise ValueError("فیلد قابل ویرایش نیست.")
        if field == "slug_en":
            value = slugify_ascii(str(value))
        async with self.sessions() as session:
            product = await session.scalar(
                select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            )
            if not product:
                raise LookupError("محصول پیدا نشد.")
            setattr(product, field, value)
            if field == "primary_photo_file_id" and value:
                session.add(ProductImage(product_id=product.id, file_id=value, sort_order=0))
            await self._audit(
                session, actor, f"product.update.{field}", "product", product.id, str(value)[:500]
            )
            await session.commit()

    async def replace_delivery_contents(
        self, product_id: int, payloads: Iterable[dict[str, Any]], actor: int
    ) -> None:
        async with self.sessions() as session:
            product = await session.scalar(
                select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            )
            if not product:
                raise LookupError("محصول پیدا نشد.")
            await session.execute(
                delete(DeliveryContent).where(DeliveryContent.product_id == product.id)
            )
            for index, payload in enumerate(list(payloads)[:50]):
                session.add(
                    DeliveryContent(
                        product_id=product.id,
                        content_type=str(payload.get("content_type", "text"))[:32],
                        file_id=payload.get("file_id"),
                        text=payload.get("text"),
                        caption=payload.get("caption"),
                        sort_order=index,
                    )
                )
            product.delivery_type = DeliveryType.AUTOMATIC
            await self._audit(session, actor, "product.delivery.replace", "product", product.id, "")
            await session.commit()

    async def delete_product(self, product_id: int, actor: int) -> None:
        async with self.sessions() as session:
            product = await session.scalar(
                select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
            )
            if not product:
                raise LookupError("محصول پیدا نشد.")
            orders = await session.scalar(
                select(func.count(Order.id))
                .join(ProductPlan, Order.plan_id == ProductPlan.id)
                .where(ProductPlan.product_id == product.id)
            )
            if orders:
                product.is_active = False
                for plan in (
                    await session.scalars(
                        select(ProductPlan).where(ProductPlan.product_id == product.id)
                    )
                ).all():
                    plan.is_active = False
                details = "soft-delete because orders exist"
            else:
                await session.delete(product)
                details = "hard-delete"
            await self._audit(session, actor, "product.delete", "product", product_id, details)
            await session.commit()

    async def update_plan(
        self, plan_id: int, *, name: str | None = None, price: int | None = None
    ) -> None:
        async with self.sessions() as session:
            plan = await session.scalar(
                select(ProductPlan)
                .join(Product)
                .where(ProductPlan.id == plan_id, Product.tenant_id == self.tenant_id)
            )
            if not plan:
                raise LookupError("پلن پیدا نشد.")
            if name is not None:
                plan.name = name.strip()[:255]
            if price is not None:
                plan.price_toman = price
            await session.commit()

    async def delete_plan(self, plan_id: int) -> None:
        async with self.sessions() as session:
            plan = await session.scalar(
                select(ProductPlan)
                .join(Product)
                .where(ProductPlan.id == plan_id, Product.tenant_id == self.tenant_id)
            )
            if not plan:
                raise LookupError("پلن پیدا نشد.")
            order_count = await session.scalar(
                select(func.count(Order.id)).where(Order.plan_id == plan.id)
            )
            if order_count:
                plan.is_active = False
            else:
                await session.delete(plan)
            await session.commit()

    async def bulk_change_prices(
        self,
        *,
        actor: int,
        direction: PriceDirection | str,
        mode: PriceChangeMode | str,
        value: int,
        category_id: int | None = None,
        product_id: int | None = None,
    ) -> int:
        async with self.sessions() as session:
            query = select(ProductPlan).join(Product).where(Product.tenant_id == self.tenant_id)
            if category_id is not None:
                query = query.where(Product.category_id == category_id)
            if product_id is not None:
                query = query.where(Product.id == product_id)
            plans = list((await session.scalars(query)).all())
            for plan in plans:
                plan.price_toman = changed_price(
                    plan.price_toman, direction=direction, mode=mode, value=value
                )
            await self._audit(
                session,
                actor,
                "price.bulk_change",
                "plan",
                None,
                f"count={len(plans)} direction={direction} mode={mode} value={value}",
            )
            await session.commit()
            return len(plans)

    async def create_discount(
        self,
        *,
        code: str,
        value: int,
        usage_limit: int,
        actor: int,
        kind: DiscountKindDB = DiscountKindDB.FIXED,
    ) -> DiscountCode:
        cleaned = code.strip().casefold()[:64]
        async with self.sessions() as session:
            exists = await session.scalar(
                select(DiscountCode.id).where(
                    DiscountCode.tenant_id == self.tenant_id, DiscountCode.code == cleaned
                )
            )
            if exists:
                raise ValueError("این کد قبلاً ساخته شده است.")
            discount = DiscountCode(
                tenant_id=self.tenant_id,
                code=cleaned,
                kind=kind,
                value=value,
                usage_limit=usage_limit,
            )
            session.add(discount)
            await session.flush()
            await self._audit(session, actor, "discount.create", "discount", discount.id, cleaned)
            await session.commit()
            return discount

    async def list_discounts(self) -> list[DiscountCode]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(DiscountCode)
                        .where(DiscountCode.tenant_id == self.tenant_id)
                        .order_by(DiscountCode.id.desc())
                    )
                ).all()
            )

    async def delete_discount(self, discount_id: int, actor: int) -> None:
        async with self.sessions() as session:
            discount = await session.scalar(
                select(DiscountCode).where(
                    DiscountCode.id == discount_id,
                    DiscountCode.tenant_id == self.tenant_id,
                )
            )
            if not discount:
                raise LookupError("کد تخفیف پیدا نشد.")
            discount.is_active = False
            await self._audit(
                session, actor, "discount.delete", "discount", discount.id, discount.code
            )
            await session.commit()

    async def preview_discount(self, plan_id: int, code: str) -> tuple[int, int, int] | None:
        async with self.sessions() as session:
            plan = await session.scalar(
                select(ProductPlan)
                .join(Product)
                .where(
                    ProductPlan.id == plan_id,
                    Product.tenant_id == self.tenant_id,
                    ProductPlan.is_active.is_(True),
                    Product.is_active.is_(True),
                )
            )
            if not plan:
                return None
            discount = await self._valid_discount(session, code)
            if not discount:
                return plan.price_toman, 0, plan.price_toman
            amount = discount_amount(
                plan.price_toman, DiscountKind(discount.kind.value), discount.value
            )
            return plan.price_toman, amount, plan.price_toman - amount

    async def _valid_discount(self, session: AsyncSession, code: str | None) -> DiscountCode | None:
        if not code:
            return None
        now = datetime.now(UTC)
        discount = await session.scalar(
            select(DiscountCode).where(
                DiscountCode.tenant_id == self.tenant_id,
                DiscountCode.code == code.strip().casefold(),
                DiscountCode.is_active.is_(True),
            )
        )
        if not discount:
            return None
        if discount.usage_count >= discount.usage_limit:
            return None
        if discount.expires_at and discount.expires_at < now:
            return None
        return discount

    async def purchase(
        self,
        *,
        user_telegram_id: int,
        plan_id: int,
        discount_code: str | None,
        manual_info: str | None,
    ) -> PurchaseOutcome:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser)
                .where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == user_telegram_id,
                )
                .with_for_update()
            )
            if not user or user.is_blocked:
                return PurchaseOutcome(False, "حساب کاربری در دسترس نیست.")

            plan = await session.scalar(
                select(ProductPlan)
                .join(Product)
                .where(
                    ProductPlan.id == plan_id,
                    Product.tenant_id == self.tenant_id,
                    ProductPlan.is_active.is_(True),
                    Product.is_active.is_(True),
                )
                .options(selectinload(ProductPlan.product).selectinload(Product.delivery_contents))
            )
            if not plan:
                return PurchaseOutcome(False, "محصول یا پلن دیگر فعال نیست.")

            discount = await self._valid_discount(session, discount_code)
            discount_value = 0
            if discount:
                discount_value = discount_amount(
                    plan.price_toman, DiscountKind(discount.kind.value), discount.value
                )
            final_amount = plan.price_toman - discount_value
            if user.balance_toman < final_amount:
                return PurchaseOutcome(
                    False,
                    "موجودی ناکافی است.",
                    required_toman=final_amount - user.balance_toman,
                    product_name=plan.product.name_fa,
                    plan_name=plan.name,
                    final_amount_toman=final_amount,
                )

            previous_orders = await session.scalar(
                select(func.count(Order.id)).where(
                    Order.tenant_id == self.tenant_id,
                    Order.user_id == user.id,
                    Order.status.in_([OrderStatus.PROCESSING, OrderStatus.DELIVERED]),
                )
            )
            user.balance_toman -= final_amount
            tracking = make_tracking_code()
            order = Order(
                tenant_id=self.tenant_id,
                user_id=user.id,
                plan_id=plan.id,
                discount_code_id=discount.id if discount else None,
                base_amount_toman=plan.price_toman,
                discount_amount_toman=discount_value,
                final_amount_toman=final_amount,
                status=OrderStatus.PROCESSING,
                tracking_code=tracking,
                manual_info=manual_info,
            )
            session.add(order)
            await session.flush()
            session.add(
                StoreTransaction(
                    tenant_id=self.tenant_id,
                    user_id=user.id,
                    order_id=order.id,
                    kind=TransactionKind.PURCHASE,
                    status=TransactionStatus.APPROVED,
                    amount_toman=-final_amount,
                    description=f"خرید {plan.product.name_fa} / {plan.name}",
                    payment_method="wallet",
                )
            )
            if discount:
                discount.usage_count += 1

            referrer_telegram_id: int | None = None
            reward_toman = 0
            if previous_orders == 0 and user.referred_by_user_id and not user.referral_rewarded:
                referrer = await session.scalar(
                    select(StoreUser)
                    .where(StoreUser.id == user.referred_by_user_id)
                    .with_for_update()
                )
                store_settings = await session.get(StoreSettings, self.tenant_id)
                if referrer and store_settings and store_settings.referral_reward_toman > 0:
                    reward_toman = store_settings.referral_reward_toman
                    referrer.balance_toman += reward_toman
                    referrer_telegram_id = referrer.telegram_id
                    user.referral_rewarded = True
                    session.add(
                        StoreTransaction(
                            tenant_id=self.tenant_id,
                            user_id=referrer.id,
                            kind=TransactionKind.REFERRAL,
                            status=TransactionStatus.APPROVED,
                            amount_toman=reward_toman,
                            description=f"پاداش اولین خرید زیرمجموعه {user.telegram_id}",
                            payment_method="referral",
                        )
                    )

            await self._audit(
                session,
                user_telegram_id,
                "order.create",
                "order",
                order.id,
                f"plan={plan.id} amount={final_amount}",
            )
            await session.commit()
            payloads = tuple(
                DeliveryPayload(item.content_type, item.file_id, item.text, item.caption)
                for item in plan.product.delivery_contents
            )
            return PurchaseOutcome(
                True,
                "خرید با موفقیت انجام شد.",
                order_id=order.id,
                tracking_code=tracking,
                product_name=plan.product.name_fa,
                plan_name=plan.name,
                final_amount_toman=final_amount,
                delivery_type=plan.product.delivery_type,
                manual_prompt=plan.product.manual_prompt,
                delivery=payloads,
                referral_user_telegram_id=referrer_telegram_id,
                referral_reward_toman=reward_toman,
            )

    async def mark_order_delivered(self, order_id: int) -> None:
        async with self.sessions() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_id, Order.tenant_id == self.tenant_id)
            )
            if order:
                order.status = OrderStatus.DELIVERED
                order.delivered_at = utc_now()
                await session.commit()

    async def get_order(self, tracking_code: str, user_telegram_id: int) -> Order | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(Order)
                .join(StoreUser)
                .where(
                    Order.tenant_id == self.tenant_id,
                    Order.tracking_code == tracking_code.strip(),
                    StoreUser.telegram_id == user_telegram_id,
                )
                .options(selectinload(Order.plan).selectinload(ProductPlan.product))
            )

    async def create_topup(
        self, user_telegram_id: int, amount_toman: int, method: str
    ) -> StoreTransaction:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == user_telegram_id,
                )
            )
            if not user:
                raise LookupError("کاربر پیدا نشد.")
            transaction = StoreTransaction(
                tenant_id=self.tenant_id,
                user_id=user.id,
                kind=TransactionKind.DEPOSIT,
                status=TransactionStatus.PENDING,
                amount_toman=amount_toman,
                description="افزایش موجودی",
                payment_method=method,
            )
            session.add(transaction)
            await session.commit()
            await session.refresh(transaction)
            return transaction

    async def set_topup_authority(self, transaction_id: int, authority: str) -> None:
        async with self.sessions() as session:
            transaction = await session.scalar(
                select(StoreTransaction).where(
                    StoreTransaction.id == transaction_id,
                    StoreTransaction.tenant_id == self.tenant_id,
                )
            )
            if not transaction:
                raise LookupError("تراکنش پیدا نشد.")
            transaction.authority = authority
            await session.commit()

    async def submit_receipt(self, transaction_id: int, file_id: str) -> StoreTransaction:
        async with self.sessions() as session:
            transaction = await session.scalar(
                select(StoreTransaction).where(
                    StoreTransaction.id == transaction_id,
                    StoreTransaction.tenant_id == self.tenant_id,
                    StoreTransaction.status == TransactionStatus.PENDING,
                )
            )
            if not transaction:
                raise LookupError("تراکنش معتبر نیست.")
            transaction.receipt_file_id = file_id
            await session.commit()
            return transaction

    async def review_topup(
        self,
        transaction_id: int,
        *,
        approve: bool,
        reviewer_telegram_id: int,
        ref: str | None = None,
    ) -> tuple[StoreTransaction, int]:
        async with self.sessions() as session:
            transaction = await session.scalar(
                select(StoreTransaction)
                .where(
                    StoreTransaction.id == transaction_id,
                    StoreTransaction.tenant_id == self.tenant_id,
                )
                .options(selectinload(StoreTransaction.user))
                .with_for_update()
            )
            if not transaction:
                raise LookupError("تراکنش پیدا نشد.")
            if transaction.status == TransactionStatus.APPROVED:
                return transaction, transaction.user.telegram_id
            if transaction.status == TransactionStatus.REJECTED:
                raise ValueError("این تراکنش قبلاً رد شده است.")
            transaction.reviewed_by_telegram_id = reviewer_telegram_id
            if approve:
                transaction.status = TransactionStatus.APPROVED
                transaction.external_ref = ref
                transaction.user.balance_toman += transaction.amount_toman
            else:
                transaction.status = TransactionStatus.REJECTED
            await self._audit(
                session,
                reviewer_telegram_id,
                "topup.approve" if approve else "topup.reject",
                "transaction",
                transaction.id,
                "",
            )
            await session.commit()
            return transaction, transaction.user.telegram_id

    async def get_transaction_by_authority(self, authority: str) -> StoreTransaction | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(StoreTransaction)
                .where(
                    StoreTransaction.tenant_id == self.tenant_id,
                    StoreTransaction.authority == authority,
                )
                .options(selectinload(StoreTransaction.user))
            )

    async def account_snapshot(
        self, telegram_id: int
    ) -> tuple[StoreUser, list[Order], list[StoreTransaction]]:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == telegram_id,
                )
            )
            if not user:
                raise LookupError("کاربر پیدا نشد.")
            orders = list(
                (
                    await session.scalars(
                        select(Order)
                        .where(Order.user_id == user.id)
                        .order_by(Order.id.desc())
                        .limit(5)
                    )
                ).all()
            )
            transactions = list(
                (
                    await session.scalars(
                        select(StoreTransaction)
                        .where(StoreTransaction.user_id == user.id)
                        .order_by(StoreTransaction.id.desc())
                        .limit(5)
                    )
                ).all()
            )
            return user, orders, transactions

    async def stats(self) -> StoreStats:
        async with self.sessions() as session:
            now = datetime.now(UTC)
            month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
            total_users = int(
                await session.scalar(
                    select(func.count(StoreUser.id)).where(StoreUser.tenant_id == self.tenant_id)
                )
                or 0
            )
            month_users = int(
                await session.scalar(
                    select(func.count(StoreUser.id)).where(
                        StoreUser.tenant_id == self.tenant_id,
                        StoreUser.created_at >= month_start,
                    )
                )
                or 0
            )
            buyers = int(
                await session.scalar(
                    select(func.count(func.distinct(Order.user_id))).where(
                        Order.tenant_id == self.tenant_id,
                        Order.status.in_([OrderStatus.PROCESSING, OrderStatus.DELIVERED]),
                    )
                )
                or 0
            )
            total_sales = int(
                await session.scalar(
                    select(func.coalesce(func.sum(Order.final_amount_toman), 0)).where(
                        Order.tenant_id == self.tenant_id,
                        Order.status.in_([OrderStatus.PROCESSING, OrderStatus.DELIVERED]),
                    )
                )
                or 0
            )
            month_sales = int(
                await session.scalar(
                    select(func.coalesce(func.sum(Order.final_amount_toman), 0)).where(
                        Order.tenant_id == self.tenant_id,
                        Order.created_at >= month_start,
                        Order.status.in_([OrderStatus.PROCESSING, OrderStatus.DELIVERED]),
                    )
                )
                or 0
            )
            total_deposits = int(
                await session.scalar(
                    select(func.coalesce(func.sum(StoreTransaction.amount_toman), 0)).where(
                        StoreTransaction.tenant_id == self.tenant_id,
                        StoreTransaction.kind == TransactionKind.DEPOSIT,
                        StoreTransaction.status == TransactionStatus.APPROVED,
                    )
                )
                or 0
            )
            return StoreStats(
                total_users,
                month_users,
                buyers,
                total_sales,
                month_sales,
                total_deposits,
            )

    async def list_user_telegram_ids(self) -> list[int]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(StoreUser.telegram_id).where(
                            StoreUser.tenant_id == self.tenant_id,
                            StoreUser.is_blocked.is_(False),
                        )
                    )
                ).all()
            )

    async def admin_find_user(self, telegram_id: int) -> StoreUser | None:
        return await self.get_user_by_telegram_id(telegram_id)

    async def admin_adjust_balance(self, telegram_id: int, delta: int, actor: int) -> StoreUser:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser)
                .where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == telegram_id,
                )
                .with_for_update()
            )
            if not user:
                raise LookupError("کاربر پیدا نشد.")
            user.balance_toman = max(0, user.balance_toman + delta)
            session.add(
                StoreTransaction(
                    tenant_id=self.tenant_id,
                    user_id=user.id,
                    kind=TransactionKind.DEPOSIT if delta >= 0 else TransactionKind.PURCHASE,
                    status=TransactionStatus.APPROVED,
                    amount_toman=delta,
                    description="ویرایش موجودی توسط مدیر",
                    payment_method="admin",
                    reviewed_by_telegram_id=actor,
                )
            )
            await self._audit(
                session, actor, "user.balance.adjust", "user", user.id, f"delta={delta}"
            )
            await session.commit()
            return user

    async def admin_set_blocked(self, telegram_id: int, blocked: bool, actor: int) -> StoreUser:
        async with self.sessions() as session:
            user = await session.scalar(
                select(StoreUser).where(
                    StoreUser.tenant_id == self.tenant_id,
                    StoreUser.telegram_id == telegram_id,
                )
            )
            if not user:
                raise LookupError("کاربر پیدا نشد.")
            user.is_blocked = blocked
            await self._audit(
                session, actor, "user.block" if blocked else "user.unblock", "user", user.id, ""
            )
            await session.commit()
            return user

    async def update_settings(self, actor: int, **values: Any) -> StoreSettings:
        allowed = {
            "start_text",
            "start_photo_file_id",
            "support_account",
            "secondary_admin_id",
            "satisfaction_channel_id",
            "log_channel_id",
            "card_enabled",
            "card_number",
            "card_holder",
            "zarinpal_enabled",
            "zarinpal_merchant_id",
            "referral_reward_toman",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported setting fields: {sorted(unknown)}")
        async with self.sessions() as session:
            settings = await session.get(StoreSettings, self.tenant_id)
            if not settings:
                raise LookupError("تنظیمات پیدا نشد.")
            for field, value in values.items():
                setattr(settings, field, value)
            await self._audit(
                session, actor, "settings.update", "settings", self.tenant_id, str(values)
            )
            await session.commit()
            return settings

    async def list_required_channels(self) -> list[RequiredChannel]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(RequiredChannel).where(
                            RequiredChannel.tenant_id == self.tenant_id,
                            RequiredChannel.is_active.is_(True),
                        )
                    )
                ).all()
            )

    async def add_required_channel(
        self, *, chat_id: str, title: str, invite_url: str | None, actor: int
    ) -> RequiredChannel:
        async with self.sessions() as session:
            channel = RequiredChannel(
                tenant_id=self.tenant_id,
                chat_id=chat_id.strip(),
                title=title.strip()[:255] or "کانال",
                invite_url=invite_url.strip() if invite_url else None,
            )
            session.add(channel)
            await session.flush()
            await self._audit(
                session, actor, "channel.add", "required_channel", channel.id, channel.chat_id
            )
            await session.commit()
            return channel

    async def delete_required_channel(self, channel_id: int, actor: int) -> None:
        async with self.sessions() as session:
            channel = await session.scalar(
                select(RequiredChannel).where(
                    RequiredChannel.id == channel_id,
                    RequiredChannel.tenant_id == self.tenant_id,
                )
            )
            if not channel:
                raise LookupError("کانال پیدا نشد.")
            channel.is_active = False
            await self._audit(
                session, actor, "channel.delete", "required_channel", channel.id, channel.chat_id
            )
            await session.commit()

    async def remember_support_message(
        self,
        *,
        user_chat_id: int,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> None:
        async with self.sessions() as session:
            session.add(
                SupportRelay(
                    tenant_id=self.tenant_id,
                    user_chat_id=user_chat_id,
                    admin_chat_id=admin_chat_id,
                    admin_message_id=admin_message_id,
                )
            )
            await session.commit()

    async def resolve_support_reply(self, admin_chat_id: int, admin_message_id: int) -> int | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(SupportRelay.user_chat_id).where(
                    SupportRelay.tenant_id == self.tenant_id,
                    SupportRelay.admin_chat_id == admin_chat_id,
                    SupportRelay.admin_message_id == admin_message_id,
                )
            )

    async def _audit(
        self,
        session: AsyncSession,
        actor: int | None,
        action: str,
        entity_type: str | None,
        entity_id: int | None,
        details: str,
    ) -> None:
        session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_telegram_id=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details[:4000],
            )
        )


def tenant_runtime_active(tenant: TenantBot, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    def aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    if tenant.status == BotStatus.DISABLED:
        return False
    if tenant.status == BotStatus.TRIAL:
        end = aware(tenant.trial_ends_at)
        return bool(end and end > now)
    if tenant.status == BotStatus.ACTIVE:
        end = aware(tenant.subscription_ends_at)
        return bool(end and end > now)
    return False
