import sys
import os
from pathlib import Path
import asyncio

# Use an in-memory SQLite DB for tests to avoid connecting to external Postgres
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Ensure the backend root is on sys.path so `import app` works during tests
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Create tables before tests run
def _create_tables():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.base import Base
    # Import models so they are registered on Base.metadata
    import app.db.models  # noqa: F401
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import insert
    import uuid

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # create a tenant and a model_version used by tests
            from app.db import models as m
            tenant_id = uuid.uuid4()
            await conn.execute(insert(m.Tenant).values(id=tenant_id, name="test-tenant"))
            mv_id = uuid.uuid4()
            await conn.execute(insert(m.ModelVersion).values(id=mv_id, tenant_id=tenant_id, name="test-mv", is_active=True))
            # export for tests
            os.environ.setdefault("TEST_TENANT_ID", str(tenant_id))
            os.environ.setdefault("TEST_MODEL_VERSION_ID", str(mv_id))

    asyncio.run(_init())

    # bind the test engine into the app.db.session module so dependency yields use it
    import app.db.session as session_mod
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    session_mod.engine = engine
    session_mod.AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


_create_tables()
