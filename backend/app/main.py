from fastapi import FastAPI

from backend.app.api.routes.picks import router as picks_router


def create_app() -> FastAPI:
    app = FastAPI(title="Gordon BetScanner Backend", version="0.1.0")
    app.include_router(picks_router, prefix="/picks", tags=["picks"])
    return app


app = create_app()
