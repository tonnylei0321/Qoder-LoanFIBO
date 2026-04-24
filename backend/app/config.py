from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    APP_NAME: str = "LoanFIBO"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "loanfibo"
    POSTGRES_USER: str = "loanfibo"
    POSTGRES_PASSWORD: str = "loanfibo_secret"
    DATABASE_URL: str = "postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5433/loanfibo"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6380/0"
    
    # GraphDB
    GRAPHDB_ENDPOINT: str = "http://localhost:7200"
    GRAPHDB_REPO: str = "loanfibo"
    GRAPHDB_TIMEOUT: float = 30.0
    
    # LLM - DashScope
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # LLM Models
    MAPPING_MODEL: str = "qwen-long"
    MAPPING_FALLBACK_MODEL: str = "qwen-max"   # Fallback for mapping when primary fails
    CRITIC_MODEL: str = "qwen-max"
    REVISION_MODEL: str = "qwen-max"
    
    # LLM Settings
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 120  # Increased for qwen-long with large prompts
    LLM_MAX_RETRIES: int = 2
    
    # Pipeline Settings
    BATCH_SIZE: int = 5
    MAX_CONCURRENCY: int = 2  # Reduced to avoid DashScope rate limits
    MAX_REVISION_ROUNDS: int = 3
    CANDIDATE_LIMIT: int = 20
    
    # CORS — 必须同时包含 localhost 和 127.0.0.1，因浏览器和脚本客户端可能使用不同 host
    # 生产环境请通过 .env 的 BACKEND_CORS_ORIGINS 覆盖
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:8000",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
