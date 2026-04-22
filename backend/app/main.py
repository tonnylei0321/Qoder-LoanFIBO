"""
LoanFIBO - DDL to FIBO Ontology Mapping Pipeline

FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.app.config import settings
from backend.app.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    await init_db()
    logger.info("Database initialized")

    # Start APScheduler
    from backend.app.services.rules.aps_scheduler import start_scheduler
    start_scheduler()

    # Initialize agent services
    import redis.asyncio as aioredis
    from backend.app.services.agent.router import init_router
    from backend.app.services.agent.heartbeat import init_heartbeat_service, HEARTBEAT_TIMEOUT_SEC
    from backend.app.services.agent.tracer import init_tracer
    from backend.app.services.agent.task_queue import init_task_queue
    from backend.app.services.agent.ws_handler import init_ws_handler

    redis_client = None
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
        await redis_client.ping()
        logger.info("Redis connected for agent services")
    except Exception as e:
        logger.warning(f"Redis not available, agent services run without Redis: {e}")

    agent_router = init_router(redis_client=redis_client)
    tracer = init_tracer(redis_client=redis_client)
    task_queue = init_task_queue(router=agent_router, tracer=tracer)
    init_heartbeat_service(router=agent_router, redis_client=redis_client)
    init_ws_handler(router=agent_router, task_queue=task_queue, tracer=tracer)
    logger.info("Agent services initialized")

    # Start heartbeat background task
    async def heartbeat_loop():
        """心跳检测循环 — 每秒扫描连接状态。"""
        from backend.app.services.agent.heartbeat import get_heartbeat_service
        import asyncio
        while True:
            try:
                svc = get_heartbeat_service()
                svc.check_connections()
            except Exception as e:
                logger.error(f"Heartbeat check error: {e}")
            await asyncio.sleep(1)

    async def offline_alert_loop():
        """OFFLINE 告警检测 — 每 30 秒扫描。"""
        from backend.app.services.agent.heartbeat import get_heartbeat_service
        import asyncio
        while True:
            try:
                svc = get_heartbeat_service()
                alerts = await svc.check_offline_alerts()
                for alert in alerts:
                    logger.warning(f"OFFLINE 告警: {alert}")
                    # TODO: 发送邮件/短信通知
            except Exception as e:
                logger.error(f"Offline alert check error: {e}")
            await asyncio.sleep(30)

    import asyncio
    hb_task = asyncio.create_task(heartbeat_loop())
    alert_task = asyncio.create_task(offline_alert_loop())

    yield

    # Shutdown
    hb_task.cancel()
    alert_task.cancel()
    logger.info("Shutting down application")
    from backend.app.services.rules.aps_scheduler import stop_scheduler
    stop_scheduler()
    if redis_client:
        await redis_client.close()
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="DDL to FIBO Ontology Mapping Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health & root endpoints — MUST be registered BEFORE the static file mount
# at "/", otherwise the mount shadows them with 404.
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "api_prefix": settings.API_V1_STR,
    }


# Include API routers
from backend.app.api.v1 import pipeline, files, jobs, auth, loan_analysis, query, rules, tenant, sync, explore, org, agent
app.include_router(pipeline.router, prefix=settings.API_V1_STR, tags=["pipeline"])
app.include_router(files.router, prefix=settings.API_V1_STR, tags=["files"])
app.include_router(jobs.router, prefix=settings.API_V1_STR, tags=["jobs"])
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["auth"])
app.include_router(loan_analysis.router, prefix=settings.API_V1_STR, tags=["loan-analysis"])
app.include_router(query.router, prefix=settings.API_V1_STR, tags=["query"])
app.include_router(rules.router, prefix=settings.API_V1_STR, tags=["rules"])
app.include_router(tenant.router, prefix=settings.API_V1_STR, tags=["tenant"])
app.include_router(sync.router, prefix=settings.API_V1_STR, tags=["sync"])
app.include_router(explore.router, prefix=settings.API_V1_STR + "/explore", tags=["explore"])
app.include_router(org.router, prefix=settings.API_V1_STR + "/org", tags=["org"])
app.include_router(agent.router, prefix=settings.API_V1_STR, tags=["agent"])

# Mount static files (frontend) — MUST come last so API routes take priority
app.mount("/", StaticFiles(directory="backend/app/static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
