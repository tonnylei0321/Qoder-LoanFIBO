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
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
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

# Include API routers
from backend.app.api.v1 import pipeline, files, jobs, auth, loan_analysis, query, rules, tenant
app.include_router(pipeline.router, prefix=settings.API_V1_STR, tags=["pipeline"])
app.include_router(files.router, prefix=settings.API_V1_STR, tags=["files"])
app.include_router(jobs.router, prefix=settings.API_V1_STR, tags=["jobs"])
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["auth"])
app.include_router(loan_analysis.router, prefix=settings.API_V1_STR, tags=["loan-analysis"])
app.include_router(query.router, prefix=settings.API_V1_STR, tags=["query"])
app.include_router(rules.router, prefix=settings.API_V1_STR, tags=["rules"])
app.include_router(tenant.router, prefix=settings.API_V1_STR, tags=["tenant"])

# Mount static files (frontend)
app.mount("/", StaticFiles(directory="backend/app/static", html=True), name="static")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
