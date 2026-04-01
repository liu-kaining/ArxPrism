"""
ArxPrism Task Models

任务状态管理相关的 Pydantic 模型定义。
用于 Redis 存储、API 响应和任务队列。

Reference: ARCHITECTURE.md Section 5 (扩展)
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举."""

    PENDING = "pending"      # 等待处理
    RUNNING = "running"      # 正在执行
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class PaperProcessingStatus(str, Enum):
    """单篇论文处理状态."""

    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 处理中
    SUCCESS = "success"      # 成功
    SKIPPED = "skipped"      # 跳过 (领域不相关)
    FAILED = "failed"        # 失败


class PaperProcessingResult(BaseModel):
    """单篇论文处理结果."""

    arxiv_id: str = Field(description="arXiv 论文 ID")
    title: str = Field(default="", description="论文标题")
    status: PaperProcessingStatus = Field(description="处理状态")
    message: Optional[str] = Field(default=None, description="状态消息或错误信息")
    processed_at: Optional[datetime] = Field(default=None, description="处理时间")

    # 萃取结果摘要 (仅成功时填充)
    method_name: Optional[str] = Field(default=None, description="提取的方法名称")
    is_relevant: Optional[bool] = Field(default=None, description="是否领域相关")


class TaskProgress(BaseModel):
    """任务进度信息."""

    total: int = Field(default=0, description="总论文数")
    processed: int = Field(default=0, description="已处理数")
    succeeded: int = Field(default=0, description="成功数")
    skipped: int = Field(default=0, description="跳过数 (领域不相关)")
    failed: int = Field(default=0, description="失败数")
    current_paper_id: Optional[str] = Field(default=None, description="当前处理的论文 ID")
    current_paper_title: Optional[str] = Field(default=None, description="当前处理的论文标题")

    @property
    def percentage(self) -> float:
        """计算完成百分比."""
        if self.total == 0:
            return 0.0
        return round((self.processed / self.total) * 100, 1)


class Task(BaseModel):
    """任务完整信息."""

    task_id: str = Field(description="任务唯一标识 (UUID)")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")

    # 任务参数
    query: str = Field(description="arXiv 搜索查询")
    domain_preset: str = Field(default="sre", description="领域预设")
    max_results: int = Field(default=10, description="最大论文数")

    # 进度信息
    progress: TaskProgress = Field(default_factory=TaskProgress, description="进度信息")

    # 处理结果
    results: List[PaperProcessingResult] = Field(
        default_factory=list,
        description="各论文处理结果"
    )

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")

    # 错误信息
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # 可执行操作
    @property
    def can_pause(self) -> bool:
        """是否可暂停."""
        return self.status == TaskStatus.RUNNING

    @property
    def can_resume(self) -> bool:
        """是否可恢复."""
        return self.status == TaskStatus.PAUSED

    @property
    def can_cancel(self) -> bool:
        """是否可取消."""
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED)

    @property
    def can_retry(self) -> bool:
        """是否可重试."""
        return self.status == TaskStatus.FAILED


class TaskCreateRequest(BaseModel):
    """创建任务请求."""

    query: str = Field(
        description="arXiv 搜索查询关键词",
        examples=["site reliability engineering", "AIOps log anomaly"]
    )
    domain_preset: str = Field(
        default="sre",
        description="领域预设: sre, aiops, microservices, distributed, cloudnative, custom"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最大抓取论文数 (1-100)"
    )


class TaskCreateResponse(BaseModel):
    """创建任务响应."""

    task_id: str = Field(description="任务 ID")
    status: TaskStatus = Field(description="初始状态")
    message: str = Field(default="Task created successfully")


class TaskListResponse(BaseModel):
    """任务列表响应."""

    tasks: List[Task] = Field(description="任务列表")
    total: int = Field(description="总数")


class TaskSummary(BaseModel):
    """任务摘要 (用于列表显示)."""

    task_id: str
    status: TaskStatus
    query: str
    domain_preset: str
    progress: TaskProgress
    created_at: datetime
    updated_at: datetime


# =============================================================================
# 领域预设配置
# =============================================================================

class DomainPreset(BaseModel):
    """领域预设配置."""

    key: str = Field(description="预设键名")
    name: str = Field(description="预设显示名称")
    description: str = Field(description="预设描述")
    include_terms: List[str] = Field(
        default_factory=list,
        description="包含的搜索词"
    )
    exclude_terms: List[str] = Field(
        default_factory=list,
        description="排除的搜索词"
    )
    categories: List[str] = Field(
        default_factory=list,
        description="arXiv 类别限定"
    )


# 预定义的领域预设
DOMAIN_PRESETS: dict[str, DomainPreset] = {
    "sre": DomainPreset(
        key="sre",
        name="站点可靠性工程 (SRE)",
        description="Site Reliability Engineering, Incident Management, SLO/SLI",
        include_terms=[
            "site reliability engineering",
            "incident management",
            "SLO",
            "error budget",
            "on-call",
            "runbook",
            "service level objective"
        ],
        exclude_terms=[
            "CLIP",
            "image segmentation",
            "computer vision",
            "medical imaging"
        ],
        categories=["cs.SE", "cs.DC"]
    ),
    "aiops": DomainPreset(
        key="aiops",
        name="AIOps 智能运维",
        description="AIOps, Log Anomaly Detection, Root Cause Analysis",
        include_terms=[
            "AIOps",
            "log anomaly",
            "root cause analysis",
            "fault diagnosis",
            "log analysis",
            "anomaly detection",
            "observability"
        ],
        exclude_terms=[
            "image",
            "video",
            "speech"
        ],
        categories=["cs.SE", "cs.AI", "cs.LG"]
    ),
    "microservices": DomainPreset(
        key="microservices",
        name="微服务架构",
        description="Microservices, Service Mesh, Distributed Tracing",
        include_terms=[
            "microservices",
            "service mesh",
            "distributed tracing",
            "service discovery",
            "API gateway",
            "container orchestration"
        ],
        exclude_terms=[],
        categories=["cs.DC", "cs.SE"]
    ),
    "distributed": DomainPreset(
        key="distributed",
        name="分布式系统",
        description="Distributed Systems, Consensus, Fault Tolerance",
        include_terms=[
            "distributed system",
            "consensus",
            "fault tolerance",
            "distributed storage",
            "replication",
            "CAP theorem"
        ],
        exclude_terms=[],
        categories=["cs.DC"]
    ),
    "cloudnative": DomainPreset(
        key="cloudnative",
        name="云原生",
        description="Cloud Native, Kubernetes, Serverless",
        include_terms=[
            "cloud native",
            "Kubernetes",
            "serverless",
            "container",
            "infrastructure as code",
            "GitOps"
        ],
        exclude_terms=[],
        categories=["cs.DC", "cs.SE"]
    ),
    "custom": DomainPreset(
        key="custom",
        name="自定义查询",
        description="不使用预设过滤，直接使用原始查询",
        include_terms=[],
        exclude_terms=[],
        categories=[]
    )
}


def get_domain_preset(key: str) -> DomainPreset:
    """获取领域预设，不存在则返回 custom."""
    return DOMAIN_PRESETS.get(key, DOMAIN_PRESETS["custom"])


def list_domain_presets() -> List[DomainPreset]:
    """获取所有领域预设列表."""
    return list(DOMAIN_PRESETS.values())
