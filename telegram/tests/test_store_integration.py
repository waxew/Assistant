from cryptography.fernet import Fernet

from app.database import Database
from app.models import DeliveryType
from app.security import TokenCipher, token_fingerprint
from app.services.builder import BuilderService
from app.services.store import StoreService


async def create_tenant(builder: BuilderService, cipher: TokenCipher, suffix: int):
    token = f"{100000 + suffix}:ABCDEFGHIJKLMNOPQRSTUVWXYZ_{suffix:03d}"
    return await builder.create_tenant(
        owner_telegram_id=100,
        bot_id=900_000 + suffix,
        username=f"test_{suffix}_bot",
        display_name=f"Test {suffix}",
        encrypted_token=cipher.encrypt(token),
        token_hash=token_fingerprint(token),
        trial_days=7,
        referral_reward_toman=20_000,
    )


async def test_purchase_and_topup_are_transactional(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'store.db'}")
    await database.init_schema()
    cipher = TokenCipher(Fernet.generate_key().decode())
    builder = BuilderService(database.session_factory)
    await builder.ensure_user(100, "owner", "Owner")
    tenant = await create_tenant(builder, cipher, 1)
    store = StoreService(tenant.id, database.session_factory)
    await store.ensure_user(telegram_id=200, username="buyer", full_name="Buyer")
    category = await store.create_category("محصولات")
    product = await store.create_product(
        actor=100,
        name_fa="محصول تست",
        slug_en="test-product",
        description="توضیحات",
        delivery_type=DeliveryType.AUTOMATIC,
        manual_prompt=None,
        category_id=category.id,
        photo_file_ids=[],
        delivery_contents=[{"content_type": "text", "text": "delivery"}],
        first_plan_name="پایه",
        first_plan_price_toman=10_000,
    )
    topup = await store.create_topup(200, 20_000, "card")
    await store.review_topup(topup.id, approve=True, reviewer_telegram_id=100)
    await store.review_topup(topup.id, approve=True, reviewer_telegram_id=100)
    outcome = await store.purchase(
        user_telegram_id=200,
        plan_id=product.plans[0].id,
        discount_code=None,
        manual_info=None,
    )
    user = await store.get_user_by_telegram_id(200)
    assert outcome.ok
    assert outcome.delivery[0].text == "delivery"
    assert user.balance_toman == 10_000
    await database.close()


async def test_tenant_catalogs_are_isolated(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'isolation.db'}")
    await database.init_schema()
    cipher = TokenCipher(Fernet.generate_key().decode())
    builder = BuilderService(database.session_factory)
    await builder.ensure_user(100, "owner", "Owner")
    first = StoreService((await create_tenant(builder, cipher, 1)).id, database.session_factory)
    second = StoreService((await create_tenant(builder, cipher, 2)).id, database.session_factory)
    await first.create_category("فقط فروشگاه اول")
    assert [item.name for item in await first.list_categories()] == ["فقط فروشگاه اول"]
    assert await second.list_categories() == []
    await database.close()
