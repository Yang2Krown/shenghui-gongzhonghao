import secrets
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 项目信息
    PROJECT_NAME: str = "AI公众号内容运营平台"
    PROJECT_DESCRIPTION: str = "基于AI的公众号内容运营辅助平台"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 调试配置
    DEBUG: bool = False
    
    # 安全配置
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    ALGORITHM: str = "HS256"
    
    # 数据库配置
    SQLITE_DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "ai_content_hub"
    POSTGRES_PORT: str = "5432"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # ====== LLM 配置 ======
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"
    TONGYI_API_KEY: Optional[str] = None
    TONGYI_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"

    # 默认 LLM provider 切换（deepseek / anthropic / openai）
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # ====== TopHub 榜眼数据 API ======
    TOPHUB_API_KEY: Optional[str] = None
    TOPHUB_API_BASE: str = "https://api.tophubdata.com"

    # ====== Embedding 配置 ======
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024

    # 默认AI模型（旧字段，保留兼容）
    DEFAULT_AI_MODEL: str = "deepseek-chat"
    DEFAULT_AI_PROVIDER: str = "deepseek"
    
    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
    ]
    
    # 可信主机
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 数据抓取配置
    SCRAPE_INTERVAL_HOURS: int = 24  # 每24小时抓取一次
    SCRAPE_TIMEOUT: int = 30  # 抓取超时时间（秒）
    SCRAPE_RETRY_COUNT: int = 3  # 抓取重试次数
    
    # 支持的平台
    SUPPORTED_PLATFORMS: List[str] = [
        "36kr",
        "qbitai",
        "jiqizhixin",
        "ithome",
        "huxiu",
        "tophub"
    ]
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """组装CORS源"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("ALLOWED_HOSTS", pre=True)
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """组装可信主机"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """获取数据库URI"""
        if self.POSTGRES_PASSWORD:
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        return self.SQLITE_DATABASE_URL
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


# 创建全局配置实例
settings = Settings()


# 根据环境选择数据库
def get_database_url() -> str:
    """获取数据库URL"""
    if settings.POSTGRES_PASSWORD:
        return settings.SQLALCHEMY_DATABASE_URI
    return settings.SQLITE_DATABASE_URL