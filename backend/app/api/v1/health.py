from fastapi import APIRouter
from app.core.response import format_response

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check for STRATEGOS API"""
    return format_response({"status": "ok"})
