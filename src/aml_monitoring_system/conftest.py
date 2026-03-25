"""
Shared pytest fixtures for the AML Monitoring System test suite.

Fixture hierarchy:
  event_loop         â€” single async loop for the test session
  settings_override  â€” patches env vars so no real .env is needed
  db_session         â€” in-memory SQLite async session (unit tests)
  mock_redis         â€” fakeredis async instance
  app_client         â€” TestClient with DB + Redis overridden
  analyst_token      â€” JWT for role=analyst
  admin_token        â€” JWT for role=admin
  sample_user        â€” persisted User ORM object
  sample_transaction â€” persisted Transaction ORM object
  sample_alert       â€” persisted Alert ORM object
"""
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

# â”€â”€ In-process SQLite for unit tests (no Postgres needed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# â”€â”€ Override settings before any app import â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.fixture(scope="session", autouse=True)
def settings_override():
    """
    Patch all settings that require external services so tests
    can run in CI without a real Postgres / Redis instance.
    """
    overrides = {
        "DATABASE_URL"              : TEST_DB_URL,
        "REDIS_URL"                 : "redis://localhost:6379/15",  # overridden by fakeredis
        "SECRET_KEY"                : "test-secret-key-minimum-32-characters-long",
        "DEBUG"                     : "true",
        "APP_ENV"                   : "test",
        "ML_MODEL_PATH"             : "app/ml/models/",
    }
    with patch.dict("os.environ", overrides):
        yield


# â”€â”€ Async event loop (session-scoped) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# â”€â”€ In-memory DB engine + session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest_asyncio.fixture(scope="session")
async def db_engine():
    from app.db.base import Base

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yields a fresh async session, rolling back after each test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# â”€â”€ Fake Redis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest_asyncio.fixture
async def mock_redis():
    """
    Uses fakeredis if available, otherwise falls back to AsyncMock.
    Install: pip install fakeredis
    """
    try:
        import fakeredis.aioredis as fakeredis
        r = fakeredis.FakeRedis()
        yield r
        await r.flushall()
    except ImportError:
        yield AsyncMock()


# â”€â”€ Auth tokens â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.fixture
def analyst_token() -> str:
    from app.core.security import create_access_token
    return create_access_token({"sub": "analyst@aml.com", "role": "analyst"})


@pytest.fixture
def admin_token() -> str:
    from app.core.security import create_access_token
    return create_access_token({"sub": "admin@aml.com", "role": "admin"})


@pytest.fixture
def analyst_headers(analyst_token) -> dict:
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest.fixture
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# â”€â”€ Test data factories â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    from app.models.user import User
    user = User(
        user_id                       = "USR_TEST_001",
        account_type                  = "Individual",
        country                       = "IN",
        occupation                    = "Salaried",
        kyc_level                     = "Full",
        is_pep                        = False,
        dormant_days_before_activation= 0,
        avg_monthly_txn_volume_usd    = 1500.0,
        num_linked_accounts           = 1,
        sanctions_hit                 = False,
        adverse_media_flag            = False,
        industry                      = "IT Services",
        risk_tier                     = "LOW",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_pep_user(db_session: AsyncSession):
    from app.models.user import User
    user = User(
        user_id                       = "USR_PEP_001",
        account_type                  = "Individual",
        country                       = "IN",
        occupation                    = "Government Official",
        kyc_level                     = "Full",
        is_pep                        = True,
        dormant_days_before_activation= 0,
        risk_tier                     = "HIGH",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_transaction(db_session: AsyncSession, sample_user):
    from app.models.user import User
    # Need a receiver too
    receiver = User(
        user_id      = "USR_TEST_002",
        country      = "IN",
        kyc_level    = "Full",
        risk_tier    = "LOW",
        account_type = "Individual",
    )
    db_session.add(receiver)
    await db_session.flush()

    from app.models.transaction import Transaction
    txn = Transaction(
        txn_id               = "TXN_TEST_001",
        sender_id            = sample_user.user_id,
        receiver_id          = receiver.user_id,
        amount_usd           = 5000.0,
        amount_local         = 415000.0,
        currency             = "INR",
        fx_rate_to_usd       = 83.0,
        payment_method       = "UPI",
        txn_type             = "P2P",
        timestamp            = datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc),
        hour_of_day          = 14,
        day_of_week          = "Saturday",
        is_weekend           = True,
        is_cross_border      = False,
        sender_country       = "IN",
        receiver_country     = "IN",
        flag_large_transaction= False,
        flag_high_risk_country= False,
        flag_pep_involved    = False,
        flag_structuring     = False,
        flag_dormant_account = False,
        flag_crypto          = False,
        flag_night_transaction=False,
        flag_round_amount    = False,
        rule_score           = 0.0,
        ml_score             = 0.05,
        graph_score          = 0.02,
        composite_risk_score = 0.03,
        risk_label           = "LOW",
        status               = "Completed",
        channel              = "Mobile App",
    )
    db_session.add(txn)
    await db_session.flush()
    return txn


@pytest_asyncio.fixture
async def sample_high_risk_transaction(db_session: AsyncSession, sample_user):
    from app.models.user import User
    receiver = User(
        user_id="USR_TEST_003", country="IR",
        kyc_level="None", risk_tier="HIGH", account_type="Individual",
    )
    db_session.add(receiver)
    await db_session.flush()

    from app.models.transaction import Transaction
    txn = Transaction(
        txn_id               = "TXN_HIGHRISK_001",
        sender_id            = sample_user.user_id,
        receiver_id          = receiver.user_id,
        amount_usd           = 95000.0,
        amount_local         = 95000.0,
        currency             = "USD",
        fx_rate_to_usd       = 1.0,
        payment_method       = "SWIFT",
        txn_type             = "Remittance",
        timestamp            = datetime(2024, 6, 1, 2, 30, 0, tzinfo=timezone.utc),  # night
        hour_of_day          = 2,
        day_of_week          = "Saturday",
        is_weekend           = True,
        is_cross_border      = True,
        sender_country       = "IN",
        receiver_country     = "IR",
        flag_large_transaction= True,
        flag_high_risk_country= True,
        flag_pep_involved    = False,
        flag_structuring     = False,
        flag_dormant_account = False,
        flag_crypto          = False,
        flag_night_transaction= True,
        flag_round_amount    = True,
        rule_score           = 0.80,
        ml_score             = 0.75,
        graph_score          = 0.60,
        composite_risk_score = 0.74,
        risk_label           = "HIGH",
        status               = "Blocked",
        channel              = "API",
    )
    db_session.add(txn)
    await db_session.flush()
    return txn


@pytest_asyncio.fixture
async def sample_alert(db_session: AsyncSession, sample_high_risk_transaction):
    from app.models.alert import Alert
    alert = Alert(
        alert_id             = "ALT_TEST_001",
        txn_id               = sample_high_risk_transaction.txn_id,
        user_id              = sample_high_risk_transaction.sender_id,
        alert_rule           = "HIGH_RISK_COUNTRY",
        severity             = "HIGH",
        composite_risk_score = 0.74,
        rule_score           = 0.80,
        ml_score             = 0.75,
        graph_score          = 0.60,
        assigned_analyst     = "AML_ANALYST_001",
        alert_status         = "Open",
        sar_filed            = False,
        false_positive       = False,
        notes                = "Auto-generated during fixture setup",
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


# â”€â”€ FastAPI test client (with DB override) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest_asyncio.fixture
async def app_client(db_session: AsyncSession, mock_redis):
    """
    Full ASGI test client with:
      - In-memory SQLite DB (dependency override)
      - Fake Redis (patched into risk_engine and dashboard)
    """
    from app.main import app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()

