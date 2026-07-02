from app.api import audit, auth, cleanup, dashboard, scripts, servers, settings as settings_router_mod, ssh_keys, tasks
from app.api.health import router as health_router
from app.core.auto_cleanup import start_auto_cleanup_scheduler
from app.core.config import settings
from app.db.database import init_db
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router, prefix="/api")
    app.include_router(servers.router, prefix="/api")
    app.include_router(scripts.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(ssh_keys.router, prefix="/api")
    app.include_router(cleanup.router, prefix="/api")
    app.include_router(settings_router_mod.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()
        app.state.auto_cleanup_task = start_auto_cleanup_scheduler()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        task = getattr(app.state, "auto_cleanup_task", None)
        if task is not None:
            task.cancel()

    return app


app = create_app()
