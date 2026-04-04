"""
ArxPrism Configuration Module

使用 pydantic-settings 实现配置管理。
所有敏感配置必须通过 .env 文件管理，严禁硬编码。

Reference: ARCHITECTURE.md Section 6, CODE_REVIEW.md Section 2
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
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
    # development 时开启 /docs、/redoc；生产请设为 production
    environment: str = Field(default="development")
    # 逗号分隔的浏览器 Origin，禁止与 credentials 搭配使用 "*"
    cors_origins: str = Field(default="http://localhost:3000")

    # 一键清空数据：POST /api/v1/admin/clear-all-data 需在请求头携带
    # X-ArxPrism-Admin-Token: <与下方一致>；未设置则接口返回 403（防止误暴露）
    admin_reset_token: str = ""

    # Celery 配置 (延迟初始化)
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    # LLM 连接参数
    llm_api_key: str = ""
    llm_base_url: Optional[str] = None  # e.g. https://api.openai.com/v1 or any OpenAI-compatible endpoint
    # 部分聚合网关（如带 Web CSRF 的中间层）对 /embeddings 与 /chat/completions 策略不一致；
    # 若 chat 正常但 embeddings 报 invalid csrf，可单独指向直连 OpenAI 或其它兼容 embeddings 的 base（须含 /v1）
    llm_embedding_base_url: Optional[str] = None
    llm_embedding_api_key: str = ""  # 为空则复用 llm_api_key
    llm_embedding_model: str = "text-embedding-3-small"
    # Chat 多模型路由（OpenAI-compatible；Embeddings 仍仅用 llm_embedding_*，勿混用）
    llm_triage_model: str = "sapiens-ai/agnes-1.5-lite"
    llm_extractor_model: str = "anthropic/claude-sonnet-4.6"
    llm_resolution_model: str = "openai/gpt-5.4-mini"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.1
    llm_max_retries: int = 3
    llm_base_delay: float = 2.0

    # arXiv 配置
    arxiv_rate_limit_delay: float = 3.0  # arXiv 君子协定: 3秒间隔
    arxiv_min_content_length: int = 500  # 最小内容长度阈值
    # 单次任务从 arXiv API 最多遍历多少条候选（分页累加）；前若干篇已在库时会继续向后翻直到凑满 max_results 或触顶
    arxiv_max_scan_per_task: int = 500

    # PDF 仅作抓取解析时的临时目录（解析后即删）；须对运行用户可写
    pdf_storage_path: str = "/tmp/arxprism-papers"

    # Supabase（用户、JWT、profiles、system_settings）
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # JWT 签名密钥：Supabase Dashboard → Settings → API → JWT Secret
    supabase_jwt_secret: str = ""
    # 本地/内网调试可 true；生产务必 false
    auth_disabled: bool = False

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
