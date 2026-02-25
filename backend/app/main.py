import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from app.api.v1.health import router as health_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.engine import router as engine_router
from app.api.v1.rules import router as rules_router
from app.api.v1.model_versions import router as model_versions_router
from app.api.v1.states import router as states_router
from app.api.v1.advisory import router as advisory_router
from app.api.v1.intake import router as intake_router
from app.api.v1.reports import router as reports_router
from app.api.v1.admin import router as admin_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="STRATEGOS",
    description="Deterministic transformation modeling platform",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(engine_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(model_versions_router, prefix="/api/v1")
app.include_router(states_router, prefix="/api/v1")
app.include_router(advisory_router, prefix="/api/v1")
app.include_router(intake_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

@app.get("/api/v1/")
async def root():
    return {"status": "success", "data": {"service": "STRATEGOS API"}, "meta": {}}
