import sys
from pathlib import Path

# Ensure `src/` is importable for `import app.*`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def settings_override():
    overrides = {
        "DATABASE_URL": TEST_DB_URL,
        "REDIS_URL": "redis://localhost:6379/15",
        "DEBUG": "true",
        "APP_ENV": "test",
        "ML_MODEL_PATH": "app/ml/models/",
    }
    with patch.dict("os.environ", overrides):
        yield


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    from app.db.base import Base
    from app.db.session import init_db

    await init_db()
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def mock_redis():
    try:
        import fakeredis.aioredis  # type: ignore

        return await fakeredis.aioredis.FakeRedis()
    except Exception:
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.setex = AsyncMock(return_value=None)
        r.incr = AsyncMock(return_value=1)
        r.expire = AsyncMock(return_value=None)
        return r


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    from app.models.user import User

    user = User(
        user_id="USR_TEST_001",
        account_type="Individual",
        country="IN",
        occupation="Salaried",
        kyc_level="Full",
        is_pep=False,
        dormant_days_before_activation=0,
        avg_monthly_txn_volume_usd=1500.0,
        num_linked_accounts=1,
        sanctions_hit=False,
        adverse_media_flag=False,
        industry="IT Services",
        risk_tier="LOW",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_transaction(db_session: AsyncSession, sample_user):
    from app.models.user import User
    from app.models.transaction import Transaction

    receiver = User(
        user_id="USR_TEST_002",
        country="IN",
        kyc_level="Full",
        risk_tier="LOW",
        account_type="Individual",
    )
    db_session.add(receiver)
    await db_session.flush()

    txn = Transaction(
        txn_id="TXN_TEST_001",
        sender_id=sample_user.user_id,
        receiver_id=receiver.user_id,
        amount_usd=5000.0,
        amount_local=415000.0,
        currency="INR",
        fx_rate_to_usd=83.0,
        payment_method="UPI",
        txn_type="P2P",
        timestamp=datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc),
        hour_of_day=14,
        day_of_week="Saturday",
        is_weekend=True,
        is_cross_border=False,
        sender_country="IN",
        receiver_country="IN",
        composite_risk_score=0.03,
        risk_label="LOW",
        status="Completed",
        channel="Mobile App",
    )
    db_session.add(txn)
    await db_session.flush()
    return txn


@pytest_asyncio.fixture
async def sample_high_risk_transaction(db_session: AsyncSession, sample_user):
    from app.models.user import User
    from app.models.transaction import Transaction

    receiver = User(
        user_id="USR_TEST_003",
        country="IR",
        kyc_level="None",
        risk_tier="HIGH",
        account_type="Individual",
    )
    db_session.add(receiver)
    await db_session.flush()

    txn = Transaction(
        txn_id="TXN_HIGHRISK_001",
        sender_id=sample_user.user_id,
        receiver_id=receiver.user_id,
        amount_usd=95000.0,
        amount_local=95000.0,
        currency="USD",
        fx_rate_to_usd=1.0,
        payment_method="SWIFT",
        txn_type="Remittance",
        timestamp=datetime(2024, 6, 1, 2, 30, 0, tzinfo=timezone.utc),
        hour_of_day=2,
        day_of_week="Saturday",
        is_weekend=True,
        is_cross_border=True,
        sender_country="IN",
        receiver_country="IR",
        flag_large_transaction=True,
        flag_high_risk_country=True,
        flag_night_transaction=True,
        flag_round_amount=True,
        rule_score=0.80,
        ml_score=0.75,
        graph_score=0.60,
        composite_risk_score=0.74,
        risk_label="HIGH",
        status="Blocked",
        channel="API",
    )
    db_session.add(txn)
    await db_session.flush()
    return txn


@pytest_asyncio.fixture
async def sample_alert(db_session: AsyncSession, sample_high_risk_transaction):
    from app.models.alert import Alert

    alert = Alert(
        alert_id="ALT_TEST_001",
        txn_id=sample_high_risk_transaction.txn_id,
        user_id=sample_high_risk_transaction.sender_id,
        alert_rule="HIGH_RISK_COUNTRY",
        severity="HIGH",
        composite_risk_score=0.74,
        rule_score=0.80,
        ml_score=0.75,
        graph_score=0.60,
        assigned_analyst="AML_ANALYST_001",
        alert_status="Open",
        sar_filed=False,
        false_positive=False,
        notes="Auto-generated during fixture setup",
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


@pytest_asyncio.fixture
async def app_client(db_session: AsyncSession, mock_redis):
    from app.main import app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()




