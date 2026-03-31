"""
ArxPrism Pydantic 数据契约

严格按照 PROMPT_ENGINEERING.md 中的定义实现所有 Pydantic V2 模型。
所有字段都有 Field(description=...) 和合理的默认值。

Reference: PROMPT_ENGINEERING.md Section 2, ARCHITECTURE.md Section 4
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ProposedMethod(BaseModel):
    """论文提出的方法/架构."""

    name: str = Field(
        default="NOT_MENTIONED",
        description="论文提出的新方法/架构名称（首选缩写，如 STRATUS）"
    )
    description: str = Field(
        default="NOT_MENTIONED",
        description="该方法的核心机制一句话描述（50-100字）"
    )


class KnowledgeGraphNodes(BaseModel):
    """知识图谱节点实体 (用于构建 Neo4j Nodes)."""

    baselines_beaten: List[str] = Field(
        default_factory=list,
        description="具体的被击败的基线模型名称列表（极度重要，用于构建 IMPROVES_UPON 图谱边）"
    )
    datasets_used: List[str] = Field(
        default_factory=list,
        description="实验中使用的数据集或工业环境名称列表"
    )
    metrics_improved: List[str] = Field(
        default_factory=list,
        description="核心提升的指标名称及幅度列表"
    )


class CriticalAnalysis(BaseModel):
    """关键分析，包括创新点和局限性."""

    key_innovations: List[str] = Field(
        default_factory=list,
        description="1-2条核心创新点（理论/架构层面）"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="1-2条局限性（作者承认的缺陷或专家视角的工程落地风险）"
    )


class ExtractionData(BaseModel):
    """论文萃取的核心数据."""

    core_problem: str = Field(
        default="NOT_MENTIONED",
        description="一句话总结要解决的底层痛点"
    )
    proposed_method: ProposedMethod
    knowledge_graph_nodes: KnowledgeGraphNodes
    critical_analysis: CriticalAnalysis


class PaperExtractionResponse(BaseModel):
    """LLM 萃取结果的主契约 (Primary Data Contract).

    所有 LLM 输出必须经过此模型校验后才写入 Neo4j。
    """

    is_relevant_to_domain: bool = Field(
        default=False,
        description="领域安全锁：如果该论文不属于SRE/分布式/云原生/AIOps领域，必须返回False"
    )
    paper_id: str = Field(description="论文的 arXiv ID (无版本号)")
    title: str = Field(description="论文英文标题")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    publication_date: str = Field(description="发布日期 YYYY-MM-DD")
    extraction_data: ExtractionData


# =============================================================================
# API 请求/响应模型
# =============================================================================

class APIResponse(BaseModel):
    """统一 API 响应封装.

    所有接口响应均包裹在 { "code": 200, "message": "success", "data": {} } 结构中。
    Reference: ARCHITECTURE.md Section 5
    """

    code: int = Field(description="HTTP 状态码")
    message: str = Field(description="响应消息")
    data: Optional[dict] = Field(default=None, description="响应数据载荷")


class PipelineTriggerRequest(BaseModel):
    """流水线触发请求.

    POST /api/v1/pipeline/trigger
    """

    topic_query: str = Field(
        description="arXiv 搜索查询 (例如: 'all:\"site reliability engineering\" OR all:\"microservices root cause\"')"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最多获取论文数量 (1-100)"
    )


class PipelineTriggerResponse(BaseModel):
    """流水线触发响应."""

    task_id: str = Field(description="Celery 任务 ID")
    status: str = Field(default="pending", description="任务状态")


class PaperGraphNode(BaseModel):
    """图谱中的单个节点."""

    id: str = Field(description="节点标识符 (arxiv_id 或 name)")
    labels: List[str] = Field(description="Neo4j 节点标签 (例如: ['Paper', 'Author'])")
    properties: dict = Field(description="节点属性")


class PaperGraphRelationship(BaseModel):
    """图谱中的关系."""

    source_id: str = Field(description="源节点 ID")
    target_id: str = Field(description="目标节点 ID")
    type: str = Field(description="关系类型 (例如: 'WRITTEN_BY', 'PROPOSES')")


class PaperGraphResponse(BaseModel):
    """论文图谱响应.

    GET /api/v1/graph/paper/{arxiv_id}
    返回论文的所有第一层相邻节点。
    """

    nodes: List[PaperGraphNode] = Field(description="图谱节点")
    relationships: List[PaperGraphRelationship] = Field(description="图谱关系")


class EvolutionTreeNode(BaseModel):
    """进化树中的节点 (D3.js/ECharts 格式)."""

    id: str = Field(description="方法节点 ID (name)")
    name: str = Field(description="方法显示名称")
    generation: int = Field(description="代数 (0 = 目标方法, 负数 = 祖先)")


class EvolutionTreeLink(BaseModel):
    """进化树中的链接."""

    source: str = Field(description="源方法 ID")
    target: str = Field(description="目标方法 ID")


class EvolutionTreeResponse(BaseModel):
    """进化树响应.

    GET /api/v1/graph/evolution
    返回方法的技术进化树，向上追溯 3 层祖先，向下扩展 3 层后代。
    格式: D3.js / ECharts Graph Node/Link 数组。
    """

    nodes: List[EvolutionTreeNode] = Field(description="树节点")
    links: List[EvolutionTreeLink] = Field(description="树链接 (source -> target)")
