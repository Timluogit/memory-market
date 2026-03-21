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
    SELLER_SHARE_RATE: float = 1.0  # MVP阶段：卖家全拿
    PLATFORM_FEE_RATE: float = 0.0  # MVP阶段：0佣金
    
    # 记忆
    MAX_MEMORY_SIZE: int = 50000  # 单条记忆最大字符数
    FREE_MEMORY_CATEGORIES: list = ["教程", "入门"]  # 免费分类
    
    # 外部服务（可选）
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")

settings = Settings()
