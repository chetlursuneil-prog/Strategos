import asyncio

from app.db.session import AsyncSessionLocal
from app.services.engine import run_deterministic_engine


async def main():
    async with AsyncSessionLocal() as db:
        snapshot = await run_deterministic_engine(
            db,
            input_data={
                "revenue": 120,
                "cost": 260,
                "margin": 0.08,
                "technical_debt": 85,
            },
        )
        print("STATE=", snapshot.get("state"))
        print("TOTAL_SCORE=", (snapshot.get("score_breakdown") or {}).get("total_score"))
        print("RESTRUCTURING_COUNT=", len(snapshot.get("restructuring_actions") or []))


if __name__ == "__main__":
    asyncio.run(main())
