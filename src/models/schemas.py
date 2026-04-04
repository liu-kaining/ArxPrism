"""
ArxPrism Pydantic 数据契约

严格按照 PROMPT_ENGINEERING.md 中的定义实现所有 Pydantic V2 模型。
所有字段都有 Field(description=...) 和合理的默认值。

v2.0：`KnowledgeGraphNodes` 使用立体 `comparisons`；`ExtractionData` 含 CoT 字段 `reasoning_process`。

Reference: PROMPT_ENGINEERING.md Section 2, ARCHITECTURE.md Section 4
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ProposedMethod(BaseModel):
    """论文提出的方法/架构."""

    name: str = Field(description="提出的核心方法或系统名称")
    description: str = Field(description="该方法的一句话核心介绍")
    core_architecture: str = Field(default="NOT_MENTIONED", description="核心技术架构或机制（如 Transformer, 动态阈值, RLHF）")
    key_innovations: List[str] = Field(default_factory=list, description="该方法的核心技术创新点列表")
    limitations: List[str] = Field(default_factory=list, description="论文中承认的该方法的局限性或缺陷")


class EvolutionLineage(BaseModel):
    """技术血脉：提出的方法建立在哪些既有工作之上、受谁启发或扩展了谁。"""

    ancestor_method: str = Field(
        description="被继承、扩展或受其启发的祖先方法名称（如 'ResNet', 'Transformer', 'DeepLog'）"
    )
    evolution_reason: str = Field(
        description="具体的演进原因或继承特性（如 '引入了其多头注意力机制', '改进了其在长文本下的显存瓶颈'）"
    )


class ExperimentComparison(BaseModel):
    """立体实验对比：在 A 数据集上相对 B 基线方法的指标变化。"""

    baseline_method: str = Field(
        default="",
        description="作为基线的对比方法名称",
    )
    dataset: str = Field(
        default="",
        description="实验使用的数据集或环境",
    )
    metrics_improvement: str = Field(
        default="",
        description="核心指标的具体提升（如 F1 +5%, Latency -10ms）",
    )


class KnowledgeGraphNodes(BaseModel):
    """知识图谱：技术血脉（EVOLVED_FROM）与实验对比（IMPROVES_UPON 等）。"""

    evolution_lineages: List[EvolutionLineage] = Field(
        default_factory=list,
        description="技术血脉传承。记录提出的方法是建立在哪些现有技术基础之上、受谁启发，或者直接扩展了谁。",
    )
    comparisons: List[ExperimentComparison] = Field(
        default_factory=list,
        description="具体的对比实验结果列表。记录在什么数据集上相对什么基线、指标如何变化。",
    )


class TriageResponse(BaseModel):
    """轻量级领域分诊（标题+摘要），用于在下载全文前过滤无关论文以节约 Token。"""

    is_relevant: bool = Field(
        description="是否属于计算机系统/SRE/云原生/后端架构/AI 基础设施等指定工程领域"
    )
    reason: str = Field(description="一句话判定理由")
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="与目标领域的相关度 0~1；提供时与 system_settings.triage_threshold 比较",
    )


class ExtractionData(BaseModel):
    """论文萃取的核心数据."""

    reasoning_process: str = Field(
        default="",
        description=(
            "思维链推理过程：仔细阅读论文的实验部分，思考提出了什么方法，"
            "在哪些数据集上和哪些基线模型做了对比？"
        ),
    )
    core_problem: str = Field(
        default="NOT_MENTIONED",
        description="一句话总结要解决的底层痛点"
    )
    task_name: str = Field(
        default="NOT_MENTIONED",
        description=(
            "该论文要解决的核心任务专有名词，如 'Root Cause Analysis', 'Log Anomaly Detection'"
        ),
    )
    proposed_method: ProposedMethod
    knowledge_graph_nodes: KnowledgeGraphNodes


class AbstractTranslationResponse(BaseModel):
    """arXiv 摘要专业中译（仅 LLM 输出校验用）。"""

    translation: str = Field(
        default="",
        description="与原文信息对等的简体中文学术摘要译文，不得编造原文不存在的内容",
    )


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
    extraction_data: Optional[ExtractionData] = Field(
        default=None,
        description=(
            "论文萃取结构化数据；当 is_relevant_to_domain 为 false 时 LLM 可省略该字段，"
            "不得因此触发校验失败"
        ),
    )
    summary: str = Field(
        default="",
        description="arXiv 摘要等全文外文本，由流水线在 LLM 萃取后注入，用于入库与向量拼接",
    )
    summary_zh: str = Field(
        default="",
        description="摘要的专业简体中文译文，由流水线调用翻译模型写入；与 summary 信息对等",
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="text-embedding-3-small 1536 维向量，由流水线调用 Embeddings API 注入",
    )


class EntityCluster(BaseModel):
    """LLM 建议的同义 Method 聚类（物理融合前契约）。"""

    primary_name: str = Field(
        description="该技术最标准、最广为人知的核心名称（如 'deeplog' 或 'llm'）"
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="应该被合并到 primary_name 的其他别名列表",
    )


class EntityResolutionResponse(BaseModel):
    """实体对齐：Method 节点融合建议列表。"""

    clusters: List[EntityCluster] = Field(
        default_factory=list,
        description="识别出的实体同义词聚类列表",
    )


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
    core_architecture: str = Field(
        default="",
        description="Method 节点上的核心技术架构摘要（图谱属性）",
    )


class EvolutionTreeLink(BaseModel):
    """进化树中的链接 (沿 EVOLVED_FROM：子方法 → 祖先)."""

    source: str = Field(description="源方法 ID（子方法 / 后代）")
    target: str = Field(description="目标方法 ID（祖先）")
    relationshipType: Optional[str] = Field(
        default="EVOLVED_FROM", description="关系类型，默认技术血脉边"
    )
    reason: Optional[str] = Field(default=None, description="边上记录的演进原因")
    discovered_at: Optional[str] = Field(default=None, description="边发现/写入时间")
    dataset: Optional[str] = Field(default=None, description="遗留：实验对比边属性")
    metrics_improvement: Optional[str] = Field(default=None, description="遗留：实验对比边属性")


class EvolutionTreeResponse(BaseModel):
    """进化树响应.

    GET /api/v1/graph/evolution
    沿 [:EVOLVED_FROM] 向上追溯 3 层祖先、向下 3 层后代。
    格式: D3.js / ECharts Graph Node/Link 数组。
    """

    nodes: List[EvolutionTreeNode] = Field(description="树节点")
    links: List[EvolutionTreeLink] = Field(description="树链接 (source -> target)")
