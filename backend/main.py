from app.api import audit, auth, batch, cleanup, dashboard, ops_commands, scripts, servers, settings as settings_router_mod, ssh_keys, tasks
from app.api.health import router as health_router
from app.core.auto_cleanup import start_auto_cleanup_scheduler
from app.core.client_ip import reset_client_ip, resolve_client_ip, set_client_ip
from app.core.config import settings
from app.core.report_summary import schedule_missing_report_summary_backfill
from app.core.task_recovery import recover_stuck_tasks
from app.core.task_runner import resume_running_script_tasks_after_startup
from app.core.gpu_driver_runner import resume_gpu_driver_tasks_after_startup
from app.core.cuda_toolkit_runner import resume_cuda_toolkit_tasks_after_startup
from app.db.database import init_db
from fastapi import FastAPI, Request


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.middleware("http")
    async def capture_client_ip(request: Request, call_next):
        peer_host = request.client.host if request.client else None
        token = set_client_ip(resolve_client_ip(request.headers, peer_host))
        try:
            return await call_next(request)
        finally:
            reset_client_ip(token)

    app.include_router(health_router, prefix="/api")
    app.include_router(servers.router, prefix="/api")
    app.include_router(scripts.router, prefix="/api")
    app.include_router(ops_commands.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(batch.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(ssh_keys.router, prefix="/api")
    app.include_router(cleanup.router, prefix="/api")
    app.include_router(settings_router_mod.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()
        recover_stuck_tasks()
        tasks.resume_pending_tasks_after_startup()
        tasks.resume_running_stress_tasks_after_startup()
        resume_running_script_tasks_after_startup()
        resume_gpu_driver_tasks_after_startup()
        resume_cuda_toolkit_tasks_after_startup()
        schedule_missing_report_summary_backfill()
        app.state.auto_cleanup_task = start_auto_cleanup_scheduler()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        task = getattr(app.state, "auto_cleanup_task", None)
        if task is not None:
            task.cancel()

    return app


app = create_app()
