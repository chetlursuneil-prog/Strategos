import os
import uuid
import asyncio
import sys
from pathlib import Path
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import Base
from app.db import models as m

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./strategos_dev.db")

if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        tenant_q = await conn.execute(select(m.Tenant).limit(1))
        tenant = tenant_q.scalars().first()
        if tenant is None:
            tenant_id = uuid.uuid4()
            await conn.execute(insert(m.Tenant).values(id=tenant_id, name="local-dev-tenant"))
        else:
            tenant_id = tenant.id

        mv_q = await conn.execute(select(m.ModelVersion).where(m.ModelVersion.tenant_id == tenant_id).limit(1))
        mv = mv_q.scalars().first()
        if mv is None:
            model_version_id = uuid.uuid4()
            await conn.execute(
                insert(m.ModelVersion).values(
                    id=model_version_id,
                    tenant_id=tenant_id,
                    name="local-dev-model",
                    description="Local SQLite deterministic baseline",
                    is_active=True,
                )
            )
        else:
            model_version_id = mv.id

    await engine.dispose()
    print(f"TENANT_ID={tenant_id}")
    print(f"MODEL_VERSION_ID={model_version_id}")

if __name__ == "__main__":
    asyncio.run(main())
