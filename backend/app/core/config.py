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
    ENVIRONMENT: str = "development"
    
    # 调试配置
    DEBUG: bool = False
    
    # 安全配置
    SECRET_KEY: str = "dev-insecure-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    ALGORITHM: str = "HS256"
    API_DOCS_ENABLED: Optional[bool] = None
    
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

    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_FAIL_OPEN: Optional[bool] = None
    RATE_LIMIT_AUTH_LOGIN_IP: str = "20/900"
    RATE_LIMIT_AUTH_LOGIN_ACCOUNT: str = "8/900"
    RATE_LIMIT_AUTH_REGISTER_IP: str = "10/3600"
    RATE_LIMIT_AUTH_REGISTER_ACCOUNT: str = "3/3600"
    RATE_LIMIT_SMS_IP: str = "10/3600"
    RATE_LIMIT_SMS_PHONE: str = "5/3600"
    RATE_LIMIT_FILE_UPLOAD_USER: str = "30/3600"
    RATE_LIMIT_LINK_EXTRACT_USER: str = "60/3600"
    RATE_LIMIT_AI_GENERATION_USER: str = "20/3600"
    RATE_LIMIT_PAYMENT_ORDER_USER: str = "10/600"
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # 管理员配置
    SUPER_ADMIN_PHONE: str = "18021751281"
    
    # ====== LLM 配置 ======
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"
    AIGOCODE_API_KEY: Optional[str] = None
    AIGOCODE_API_BASE: str = "https://api.highwayapi.ai/anthropic"
    AIGOCODE_MODEL: str = "claude-opus-4-8-r"
    TONGYI_API_KEY: Optional[str] = None
    TONGYI_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"

    # 默认 LLM provider 切换（deepseek / anthropic / openai / aigocode）
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    MODEL_TEMPERATURE: float = 0.7
    MODEL_MAX_TOKENS: int = 2048

    # ====== TopHub 榜眼数据 API ======
    TOPHUB_API_KEY: Optional[str] = None
    TOPHUB_API_BASE: str = "https://api.tophubdata.com"

    # ====== 飞书商单 brief 接入 ======
    # 平台共用一个自建应用；每个用户各自走设备码 OAuth 授权，token 存库按 user_id 隔离。
    # 原生 HTTP 调飞书开放平台，不依赖 lark-cli / 系统钥匙串。密钥放 .env / .env.production。
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    # 读文档时申请的 scope；offline_access 用来换取 refresh_token（否则 access_token 2h 后失效需重授权）
    FEISHU_SCOPES: str = "offline_access docx:document:readonly wiki:wiki:readonly drive:drive:readonly"

    # ====== Embedding 配置 ======
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024

    # 默认AI模型（旧字段，保留兼容）
    DEFAULT_AI_MODEL: str = "deepseek-v4-flash"
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
    
    # ====== 标题生成 Pipeline 配置 ======
    MIN_CANDIDATES: int = 10
    MAX_CANDIDATES: int = 15
    MIN_COVERAGE_METHODS: int = 6
    MAX_SAME_METHOD: int = 3
    PRIORITY_METHOD_RATIO: float = 0.5
    MIN_TITLE_LENGTH: int = 8
    MAX_TITLE_LENGTH: int = 30
    OPTIMAL_MIN_LENGTH: int = 14
    OPTIMAL_MAX_LENGTH: int = 25
    MAX_MODIFIERS_PER_TITLE: int = 5
    B_SCORE_WEIGHT: float = 0.6
    C_SCORE_WEIGHT: float = 0.4
    PASS_THRESHOLD: float = 6.5
    MAX_REGENERATIONS: int = 1

    # ====== 阿里云短信配置 ======
    ALIYUN_SMS_ACCESS_KEY_ID: Optional[str] = None
    ALIYUN_SMS_ACCESS_KEY_SECRET: Optional[str] = None
    ALIYUN_SMS_SIGN_NAME: Optional[str] = None
    ALIYUN_SMS_TEMPLATE_CODE: Optional[str] = None

    # Exa API（微信公众号搜索，替代 mcporter CLI）
    EXA_API_KEY: Optional[str] = None

    # 博查 Bocha（国内可充值的 web 搜索 API，替代 Exa/搜狗，先用于实操类爆文搜索）
    BOCHA_API_KEY: Optional[str] = None

    # Jina Reader（抓网页/教程全文，r.jina.ai；留空走免费档，有 key 限额更高）
    JINA_API_KEY: Optional[str] = None

    # Moonshot / Kimi（联网搜索专用，Agent A2 可写性审计）
    MOONSHOT_API_KEY: Optional[str] = None
    MOONSHOT_API_BASE: str = "https://api.moonshot.cn/v1"
    MOONSHOT_MODEL: str = "moonshot-v1-32k"

    # Pixus AI 图像生成（公众号封面等）
    PIXUS_API_KEY: Optional[str] = None
    PIXUS_API_BASE: str = "https://pixus.dev"

    # ====== 微信支付 v3 Native 扫码支付 ======
    WXPAY_MCH_ID: Optional[str] = None
    WXPAY_APP_ID: Optional[str] = None
    WXPAY_API_V3_KEY: Optional[str] = None
    WXPAY_PRIVATE_KEY_PATH: Optional[str] = None
    WXPAY_MCH_SERIAL_NO: Optional[str] = None
    WXPAY_PUBLIC_KEY_PATH: Optional[str] = None
    WXPAY_PUBLIC_KEY_ID: Optional[str] = None
    WXPAY_NOTIFY_URL: Optional[str] = None
    WXPAY_TEST_MODE: bool = False

    # HTTP 代理（用于访问境外网站：HN / Reddit / V2EX / GitHub 等）
    HTTP_PROXY: Optional[str] = None

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

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v: str, values: dict) -> str:
        """生产环境必须显式提供强随机密钥。"""
        environment = str(values.get("ENVIRONMENT") or "development").lower()
        if environment in {"prod", "production"}:
            if not v or v == "dev-insecure-change-me" or len(v) < 32:
                raise ValueError("生产环境必须配置长度不少于 32 位的 SECRET_KEY")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    @property
    def api_docs_enabled(self) -> bool:
        if self.API_DOCS_ENABLED is not None:
            return self.API_DOCS_ENABLED
        return not self.is_production

    @property
    def rate_limit_fail_open(self) -> bool:
        if self.RATE_LIMIT_FAIL_OPEN is not None:
            return self.RATE_LIMIT_FAIL_OPEN
        return not self.is_production
    
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
        extra = "ignore"


# 创建全局配置实例
settings = Settings()


# 根据环境选择数据库
def get_database_url() -> str:
    """获取数据库URL"""
    if settings.POSTGRES_PASSWORD:
        return settings.SQLALCHEMY_DATABASE_URI
    return settings.SQLITE_DATABASE_URL
