from app.api import scripts, servers, tasks
from app.api.health import router as health_router
from app.core.config import settings
from app.db.database import init_db
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router, prefix="/api")
    app.include_router(servers.router, prefix="/api")
    app.include_router(scripts.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
