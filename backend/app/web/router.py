from __future__ import annotations

from fastapi import APIRouter

from backend.app.web.auth_router import router as auth_router
from backend.app.web.dashboard_router import router as dashboard_router

router = APIRouter(include_in_schema=False)
router.include_router(auth_router)
router.include_router(dashboard_router)
