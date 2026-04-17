from fastapi import FastAPI

from backend.app.api.routes.history import router as history_router
from backend.app.api.routes.match import router as match_router
from backend.app.api.routes.matches import router as matches_router
from backend.app.api.routes.picks import router as picks_router


def create_app() -> FastAPI:
    app = FastAPI(title="Gordon BetScanner Backend", version="0.1.0")
    app.include_router(picks_router, prefix="/picks", tags=["picks"])
    app.include_router(matches_router, prefix="/matches", tags=["matches"])
    app.include_router(match_router, prefix="/match", tags=["match"])
    app.include_router(history_router, prefix="/history", tags=["history"])
    return app


app = create_app()
