from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import (
    BotStatus,
    BuilderTransaction,
    BuilderUser,
    StoreSettings,
    TenantBot,
    TransactionKind,
    TransactionStatus,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class BuilderAccount:
    user: BuilderUser
    bots_count: int
    recent_transactions: tuple[BuilderTransaction, ...]


class BuilderService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str,
        referral_code: str | None = None,
    ) -> BuilderUser:
        async with self.sessions() as session:
            user = await session.scalar(
                select(BuilderUser).where(BuilderUser.telegram_id == telegram_id)
            )
            if user:
                user.username = username
                user.full_name = full_name
                await session.commit()
                return user

            referrer_id: int | None = None
            if referral_code:
                referrer_id = await session.scalar(
                    select(BuilderUser.id).where(BuilderUser.referral_code == referral_code)
                )
            user = BuilderUser(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                referral_code=await self._unique_referral_code(session),
                referred_by_id=referrer_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def _unique_referral_code(self, session: AsyncSession) -> str:
        for _ in range(10):
            code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")
            if not await session.scalar(
                select(BuilderUser.id).where(BuilderUser.referral_code == code)
            ):
                return code
        return secrets.token_hex(10)

    async def account(self, telegram_id: int) -> BuilderAccount:
        async with self.sessions() as session:
            user = await session.scalar(
                select(BuilderUser).where(BuilderUser.telegram_id == telegram_id)
            )
            if not user:
                raise LookupError("حساب کاربری پیدا نشد.")
            bots_count = int(
                await session.scalar(
                    select(func.count(TenantBot.id)).where(TenantBot.owner_id == user.id)
                )
                or 0
            )
            txs = tuple(
                (
                    await session.scalars(
                        select(BuilderTransaction)
                        .where(BuilderTransaction.user_id == user.id)
                        .order_by(BuilderTransaction.id.desc())
                        .limit(5)
                    )
                ).all()
            )
            return BuilderAccount(user=user, bots_count=bots_count, recent_transactions=txs)

    async def list_bots(self, telegram_id: int) -> list[TenantBot]:
        async with self.sessions() as session:
            bots = list(
                (
                    await session.scalars(
                        select(TenantBot)
                        .join(BuilderUser)
                        .where(BuilderUser.telegram_id == telegram_id)
                        .order_by(TenantBot.id.desc())
                    )
                ).all()
            )
            now = utc_now()
            dirty = False
            for tenant in bots:
                if tenant.status == BotStatus.TRIAL and tenant.trial_ends_at:
                    if self._aware(tenant.trial_ends_at) <= now:
                        tenant.status = BotStatus.EXPIRED
                        dirty = True
                elif tenant.status == BotStatus.ACTIVE and tenant.subscription_ends_at:
                    if self._aware(tenant.subscription_ends_at) <= now:
                        tenant.status = BotStatus.EXPIRED
                        dirty = True
            if dirty:
                await session.commit()
            return bots

    async def create_tenant(
        self,
        *,
        owner_telegram_id: int,
        bot_id: int,
        username: str,
        display_name: str,
        encrypted_token: str,
        token_hash: str,
        trial_days: int,
        referral_reward_toman: int,
        customer_mode: bool = False,
        setup_price_toman: int = 0,
        subscription_days: int = 30,
    ) -> TenantBot:
        async with self.sessions() as session:
            owner = await session.scalar(
                select(BuilderUser)
                .where(BuilderUser.telegram_id == owner_telegram_id)
                .with_for_update()
            )
            if not owner:
                raise LookupError("ابتدا /start را بزنید.")
            duplicate = await session.scalar(
                select(TenantBot.id).where(
                    (TenantBot.telegram_bot_id == bot_id) | (TenantBot.token_hash == token_hash)
                )
            )
            if duplicate:
                raise ValueError("این ربات قبلاً به سامانه اضافه شده است.")

            if customer_mode and owner.balance_toman < setup_price_toman:
                raise ValueError("موجودی حساب برای ساخت ربات مشتری کافی نیست.")
            tenant = TenantBot(
                owner_id=owner.id,
                telegram_bot_id=bot_id,
                username=username.lower().lstrip("@"),
                display_name=display_name,
                encrypted_token=encrypted_token,
                token_hash=token_hash,
                status=BotStatus.ACTIVE if customer_mode else BotStatus.TRIAL,
                trial_ends_at=None if customer_mode else utc_now() + timedelta(days=trial_days),
                subscription_ends_at=(
                    utc_now() + timedelta(days=subscription_days) if customer_mode else None
                ),
            )
            session.add(tenant)
            await session.flush()
            session.add(
                StoreSettings(
                    tenant_id=tenant.id,
                    referral_reward_toman=referral_reward_toman,
                )
            )
            if customer_mode:
                owner.balance_toman -= setup_price_toman
                session.add(
                    BuilderTransaction(
                        user_id=owner.id,
                        kind=TransactionKind.SUBSCRIPTION,
                        status=TransactionStatus.APPROVED,
                        amount_toman=-setup_price_toman,
                        description=f"ساخت ربات مشتری @{tenant.username}",
                    )
                )
            await session.commit()
            await session.refresh(tenant)
            return tenant

    async def create_topup(
        self, telegram_id: int, amount_toman: int, receipt_file_id: str
    ) -> BuilderTransaction:
        if amount_toman <= 0:
            raise ValueError("مبلغ باید بیشتر از صفر باشد.")
        async with self.sessions() as session:
            user = await session.scalar(
                select(BuilderUser).where(BuilderUser.telegram_id == telegram_id)
            )
            if not user:
                raise LookupError("حساب کاربری پیدا نشد.")
            tx = BuilderTransaction(
                user_id=user.id,
                kind=TransactionKind.DEPOSIT,
                status=TransactionStatus.PENDING,
                amount_toman=amount_toman,
                description="شارژ حساب ربات‌ساز با کارت‌به‌کارت",
                receipt_file_id=receipt_file_id,
            )
            session.add(tx)
            await session.commit()
            await session.refresh(tx)
            return tx

    async def get_builder_transaction(self, transaction_id: int) -> BuilderTransaction | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(BuilderTransaction)
                .where(BuilderTransaction.id == transaction_id)
                .options(selectinload(BuilderTransaction.user))
            )

    async def review_topup(
        self,
        transaction_id: int,
        approve: bool,
        reviewer_telegram_id: int,
        referral_reward_toman: int = 0,
    ) -> BuilderTransaction:
        async with self.sessions() as session:
            tx = await session.scalar(
                select(BuilderTransaction)
                .where(BuilderTransaction.id == transaction_id)
                .options(selectinload(BuilderTransaction.user))
                .with_for_update()
            )
            if not tx:
                raise LookupError("تراکنش پیدا نشد.")
            if tx.status != TransactionStatus.PENDING:
                return tx
            tx.status = TransactionStatus.APPROVED if approve else TransactionStatus.REJECTED
            tx.reviewed_by_telegram_id = reviewer_telegram_id
            if approve:
                tx.user.balance_toman += tx.amount_toman
                if (
                    tx.user.referred_by_id
                    and not tx.user.referral_rewarded
                    and referral_reward_toman > 0
                ):
                    referrer = await session.scalar(
                        select(BuilderUser)
                        .where(BuilderUser.id == tx.user.referred_by_id)
                        .with_for_update()
                    )
                    if referrer:
                        referrer.balance_toman += referral_reward_toman
                        tx.user.referral_rewarded = True
                        session.add(
                            BuilderTransaction(
                                user_id=referrer.id,
                                kind=TransactionKind.REFERRAL,
                                status=TransactionStatus.APPROVED,
                                amount_toman=referral_reward_toman,
                                description=f"پاداش اولین شارژ زیرمجموعه {tx.user.telegram_id}",
                            )
                        )
            await session.commit()
            return tx

    async def renew_bot(
        self,
        *,
        telegram_id: int,
        tenant_id: int,
        price_toman: int,
        subscription_days: int,
    ) -> TenantBot:
        async with self.sessions() as session:
            user = await session.scalar(
                select(BuilderUser).where(BuilderUser.telegram_id == telegram_id).with_for_update()
            )
            if not user:
                raise LookupError("ربات پیدا نشد.")
            tenant = await session.scalar(
                select(TenantBot).where(TenantBot.id == tenant_id, TenantBot.owner_id == user.id)
            )
            if not tenant:
                raise LookupError("ربات پیدا نشد.")
            if user.balance_toman < price_toman:
                raise ValueError("موجودی حساب برای تمدید کافی نیست.")
            user.balance_toman -= price_toman
            base = utc_now()
            if tenant.subscription_ends_at and self._aware(tenant.subscription_ends_at) > base:
                base = self._aware(tenant.subscription_ends_at)
            tenant.subscription_ends_at = base + timedelta(days=subscription_days)
            tenant.status = BotStatus.ACTIVE
            session.add(
                BuilderTransaction(
                    user_id=user.id,
                    kind=TransactionKind.SUBSCRIPTION,
                    status=TransactionStatus.APPROVED,
                    amount_toman=-price_toman,
                    description=f"تمدید @{tenant.username} برای {subscription_days} روز",
                )
            )
            await session.commit()
            return tenant

    async def active_tenants(self) -> list[TenantBot]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(TenantBot).where(
                            TenantBot.status.in_([BotStatus.TRIAL, BotStatus.ACTIVE])
                        )
                    )
                ).all()
            )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
