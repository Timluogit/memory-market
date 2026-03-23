"""应用配置"""
import os
from typing import Optional

class Settings:
    # 应用
    APP_NAME: str = "Agent Memory Market"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # 数据库
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/memory_market.db")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    
    # 积分系统
    MVP_FREE_MODE: bool = True  # MVP阶段：完全免费
    INITIAL_CREDITS: int = 999999  # MVP阶段：无限积分
    SELLER_SHARE_RATE: float = 1.0  # 卖家获得100%（平台不收费）
    PLATFORM_FEE_RATE: float = 0.0  # 平台佣金0%
    
    # 记忆
    MAX_MEMORY_SIZE: int = 50000  # 单条记忆最大字符数
    FREE_MEMORY_CATEGORIES: list = ["教程", "入门"]  # 免费分类
    
    # 外部服务（可选）
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")

    # Qdrant 向量搜索
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # Cross-Encoder 重排
    RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-large")
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "20"))
    RERANK_THRESHOLD: float = float(os.getenv("RERANK_THRESHOLD", "0.5"))
    RERANK_CACHE_TTL: int = int(os.getenv("RERANK_CACHE_TTL", "3600"))  # 1小时
    RERANK_FORCE_CPU: bool = os.getenv("RERANK_FORCE_CPU", "false").lower() == "true"
    EMBEDDING_MODEL_DIR: str = os.getenv("EMBEDDING_MODEL_DIR", "./models")

    # 审计日志
    AUDIT_LOG_ENABLED: bool = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
    AUDIT_LOG_RETENTION_DAYS: int = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "90"))
    AUDIT_LOG_ARCHIVE_ENABLED: bool = os.getenv("AUDIT_LOG_ARCHIVE_ENABLED", "false").lower() == "true"
    AUDIT_LOG_ASYNC_WRITE: bool = os.getenv("AUDIT_LOG_ASYNC_WRITE", "true").lower() == "true"

    # 数字签名
    DIGITAL_SIGNATURE_ENABLED: bool = os.getenv("DIGITAL_SIGNATURE_ENABLED", "true").lower() == "true"
    DIGITAL_SIGNATURE_ALGORITHM: str = os.getenv("DIGITAL_SIGNATURE_ALGORITHM", "RSA-SHA256")
    DIGITAL_SIGNATURE_KEY_SIZE: int = int(os.getenv("DIGITAL_SIGNATURE_KEY_SIZE", "2048"))
    KEY_ENCRYPTION_SALT: str = os.getenv("KEY_ENCRYPTION_SALT", "")

    # 搜索缓存
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1小时
    CACHE_ON_MISS: bool = os.getenv("CACHE_ON_MISS", "true").lower() == "true"
    CACHE_DELAY_INVALIDATION: bool = os.getenv("CACHE_DELAY_INVALIDATION", "true").lower() == "true"
    CACHE_DELAY_SECONDS: int = int(os.getenv("CACHE_DELAY_SECONDS", "5"))
    CACHE_MAX_MEMORY: str = os.getenv("CACHE_MAX_MEMORY", "2gb")

    # 用户画像系统
    PROFILE_ENABLED: bool = os.getenv("PROFILE_ENABLED", "true").lower() == "true"
    PROFILE_AUTO_EXTRACTION: bool = os.getenv("PROFILE_AUTO_EXTRACTION", "true").lower() == "true"
    PROFILE_MIN_CONFIDENCE: float = float(os.getenv("PROFILE_MIN_CONFIDENCE", "0.6"))  # 自动提取最小置信度
    PROFILE_CACHE_TTL: int = int(os.getenv("PROFILE_CACHE_TTL", "300"))  # 5分钟缓存
    PROFILE_AUTO_FORGET_DAYS: int = int(os.getenv("PROFILE_AUTO_FORGET_DAYS", "30"))  # 自动遗忘天数
    PROFILE_EXTRACTION_MODEL: str = os.getenv("PROFILE_EXTRACTION_MODEL", "gpt-4o-mini")  # 画像提取模型
    PROFILE_MAX_FIELDS: int = int(os.getenv("PROFILE_MAX_FIELDS", "30"))  # 最大字段数

settings = Settings()
