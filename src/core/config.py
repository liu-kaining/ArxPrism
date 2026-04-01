"""
ArxPrism Configuration Module

使用 pydantic-settings 实现配置管理。
所有敏感配置必须通过 .env 文件管理，严禁硬编码。

Reference: ARCHITECTURE.md Section 6, CODE_REVIEW.md Section 2
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类，从环境变量加载."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # LLM 配置（统一走 OpenAI-compatible API）
    llm_provider: str = "openai_compatible"

    # Neo4j 数据库配置 (Docker 网络中使用 neo4j 服务名)
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Redis 配置 (用于 Celery, Docker 网络中使用 redis 服务名)
    redis_url: str = "redis://redis:6379/0"

    # 应用设置
    app_env: str = "development"
    log_level: str = "INFO"

    # Celery 配置 (延迟初始化)
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    # LLM 连接参数
    llm_api_key: str = ""
    llm_base_url: Optional[str] = None  # e.g. https://api.openai.com/v1 or any OpenAI-compatible endpoint
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1
    llm_max_retries: int = 3
    llm_base_delay: float = 2.0

    # arXiv 配置
    arxiv_rate_limit_delay: float = 3.0  # arXiv 君子协定: 3秒间隔
    arxiv_min_content_length: int = 500  # 最小内容长度阈值

    # PDF 存储配置
    pdf_storage_path: str = "/data/papers"  # PDF 文件本地存储路径

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Celery 使用 redis_url 作为 broker 和 backend
        if self.celery_broker_url is None:
            object.__setattr__(self, 'celery_broker_url', self.redis_url)
        if self.celery_result_backend is None:
            object.__setattr__(self, 'celery_result_backend', self.redis_url)

        # 不再兼容 OPENAI_*：仅使用 LLM_* 配置


@lru_cache
def get_settings() -> Settings:
    """获取缓存的配置实例."""
    return Settings()


# 全局配置实例
settings = get_settings()
