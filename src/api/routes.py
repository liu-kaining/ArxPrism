"""
FastAPI API Routes

实现所有 API 端点:
- POST /api/v1/pipeline/trigger: 下发 Celery 任务
- GET /api/v1/graph/paper/{arxiv_id}: 获取论文图谱
- GET /api/v1/graph/evolution?method_name={name}: 获取方法进化树 (3层溯源)

所有响应使用统一封装: { "code": 200, "message": "success", "data": {...} }

Reference: ARCHITECTURE.md Section 5
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.auth import CurrentUser, require_user
from src.api.deps_quota import (
    PIPELINE_TRIGGER_MAX_QUOTA_UNITS,
    consume_n_task_quotas,
    refund_n_task_quotas,
)
from src.database.neo4j_client import neo4j_client
from src.models.schemas import (
    APIResponse,
    PipelineTriggerRequest,
)
from src.worker.tasks import trigger_pipeline_task_async

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["pipeline", "graph"],
    dependencies=[Depends(require_user)],
)


@router.post("/pipeline/trigger", response_model=APIResponse, status_code=202)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    user: CurrentUser = Depends(require_user),
) -> APIResponse:
    """
    触发论文萃取流水线.

    POST /api/v1/pipeline/trigger

    Payload:
        - topic_query: arXiv 搜索查询
        - max_results: 最多获取论文数量

    Action:
        将抓取任务丢入 Celery 队列，立即返回 HTTP 202 Accepted 及 task_id。

    Returns:
        HTTP 202 Accepted with task_id for tracking.
    """
    logger.info("Pipeline trigger requested: query='%s'", request.topic_query)

    effective_max = min(request.max_results, PIPELINE_TRIGGER_MAX_QUOTA_UNITS)
    try:
        await consume_n_task_quotas(user, effective_max)
    except HTTPException:
        raise

    try:
        # Dispatch to Celery (自动回退到同步模式如果 Redis 不可用)
        result = await trigger_pipeline_task_async(
            topic_query=request.topic_query,
            max_results=effective_max,
        )

        logger.info("Pipeline dispatched: %s", result)

        return APIResponse(
            code=202,
            message="Pipeline triggered successfully",
            data={
                **result,
                "max_results_capped_to": effective_max,
                "quota_units_charged": effective_max,
            },
        )

    except HTTPException:
        await refund_n_task_quotas(user.id, effective_max)
        raise
    except Exception as e:
        logger.error("Failed to trigger pipeline: %s", e)
        await refund_n_task_quotas(user.id, effective_max)
        raise HTTPException(status_code=500, detail=f"Pipeline trigger failed: {str(e)}")


@router.get("/graph/paper/{arxiv_id}", response_model=APIResponse)
async def get_paper_graph(arxiv_id: str) -> APIResponse:
    """
    获取论文知识图谱.

    GET /api/v1/graph/paper/{arxiv_id}

    返回论文的所有第一层相邻节点 (作者、方法、数据集、局限性)。

    Args:
        arxiv_id: arXiv 论文 ID (例如: "2506.02009")

    Returns:
        Graph nodes and relationships
    """
    logger.info("Fetching paper graph: arxiv_id=%s", arxiv_id)

    try:
        graph_data = await neo4j_client.get_paper_graph(arxiv_id)

        if not graph_data.get("nodes"):
            raise HTTPException(
                status_code=404,
                detail=f"Paper {arxiv_id} not found in graph database"
            )

        # Format response
        nodes = [
            {
                "id": n["id"],
                "labels": n["labels"],
                "properties": n["properties"]
            }
            for n in graph_data["nodes"]
        ]

        relationships = [
            {
                "source_id": r["source_id"],
                "target_id": r["target_id"],
                "type": r["type"]
            }
            for r in graph_data["relationships"]
        ]

        return APIResponse(
            code=200,
            message="success",
            data={
                "arxiv_id": arxiv_id,
                "nodes": nodes,
                "relationships": relationships
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch paper graph: %s", e)
        raise HTTPException(status_code=500, detail=f"Graph fetch failed: {str(e)}")


@router.get("/graph/evolution/methods", response_model=APIResponse)
async def list_evolution_methods() -> APIResponse:
    """
    列出可用于浏览进化树的方法（有 EVOLVED_FROM 血脉边的优先，其余为图中无该边的 Method 节点）。

    GET /api/v1/graph/evolution/methods
    """
    try:
        data = await neo4j_client.list_evolution_methods()
        return APIResponse(code=200, message="success", data=data)
    except Exception as e:
        logger.error("Failed to list evolution methods: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Evolution method list failed: {str(e)}"
        ) from e


@router.get("/graph/evolution", response_model=APIResponse)
async def get_evolution_tree(
    method_name: str = Query(..., description="Method name to trace")
) -> APIResponse:
    """
    构建方法技术进化树.

    GET /api/v1/graph/evolution?method_name={name}

    沿 EVOLVED_FROM 向上追溯 3 层祖先（该方法继承、扩展或受其启发的方法），
    向下扩展 3 层后代（将本方法列为祖先的方法）。

    Response 格式: D3.js / ECharts Graph Node/Link 数组。
    若库中无该方法或无进化边，仍返回 HTTP 200，nodes/links 为空数组（由前端提示）。

    Args:
        method_name: 目标方法名称

    Returns:
        Evolution tree with nodes (including generation info) and links
    """
    logger.info("Fetching evolution tree: method=%s", method_name)

    try:
        tree_data = await neo4j_client.get_evolution_tree(method_name)

        # 空结果用 200 + 空数组，避免日志/监控里刷屏 404。
        # 常见原因：归一化后的 Method 不在库中，或尚未出现在任何 EVOLVED_FROM 边上。
        if not tree_data.get("nodes"):
            return APIResponse(
                code=200,
                message="success",
                data={
                    "method_name": method_name,
                    "nodes": [],
                    "links": [],
                },
            )

        # Format response
        nodes = [
            {
                "id": n["id"],
                "name": n["name"],
                "generation": n["generation"],
                "core_architecture": (n.get("core_architecture") or "").strip(),
            }
            for n in tree_data["nodes"]
        ]

        links = [
            {
                "source": l["source"],
                "target": l["target"],
                "relationshipType": l.get("relationshipType", "EVOLVED_FROM"),
                "reason": l.get("reason") or "",
                "discovered_at": l.get("discovered_at") or "",
                "dataset": l.get("dataset") or "",
                "metrics_improvement": l.get("metrics_improvement") or "",
            }
            for l in tree_data["links"]
        ]

        return APIResponse(
            code=200,
            message="success",
            data={
                "method_name": method_name,
                "nodes": nodes,
                "links": links
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch evolution tree: %s", e)
        raise HTTPException(status_code=500, detail=f"Evolution tree fetch failed: {str(e)}")


@router.get("/papers", response_model=APIResponse)
async def search_papers(
    query: str = Query("", description="Keyword/topic to search in stored papers"),
    task_topic: str = Query(
        "",
        description="按萃取 Task 聚类名精确筛选（与 GET /papers/stats 中 by_topic.topic 一致）",
    ),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    search_mode: str = Query(
        "semantic",
        description="semantic=向量相似度（带相对阈值）；keyword=标题/核心问题/方法名子串匹配",
        pattern="^(semantic|keyword)$",
    ),
) -> APIResponse:
    """
    按主题/关键词检索已入库论文列表。

    - query 为空：按时间倒序浏览（仍受 task_topic 约束）
    - query 非空 + semantic：向量检索（与最高分挂钩的相对阈值 + 绝对下限）
    - query 非空 + keyword：title/core_problem/method CONTAINS
    """
    try:
        total = await neo4j_client.count_search_papers(
            query=query, task_topic=task_topic, search_mode=search_mode
        )
        rows = await neo4j_client.search_papers(
            query=query,
            limit=limit,
            offset=offset,
            task_topic=task_topic,
            search_mode=search_mode,
        )
        return APIResponse(
            code=200,
            message="success",
            data={
                "query": query,
                "task_topic": task_topic,
                "search_mode": search_mode,
                "limit": limit,
                "offset": offset,
                "total": total,
                "papers": rows,
            },
        )
    except Exception as e:
        logger.error("Failed to search papers: %s", e)
        raise HTTPException(status_code=500, detail=f"Paper search failed: {str(e)}")


@router.get("/papers/stats", response_model=APIResponse)
async def get_papers_library_stats(
    query: str = Query(
        "",
        description="与 GET /papers 一致；非空时 by_topic 仅统计命中论文内的 Task 分布",
    ),
    task_topic: str = Query(
        "",
        description="与 GET /papers 一致；非空时与 query 组合过滤后再聚类 by_topic",
    ),
    search_mode: str = Query(
        "semantic",
        description="与 GET /papers 的 search_mode 一致",
        pattern="^(semantic|keyword)$",
    ),
) -> APIResponse:
    """
    图库统计：论文总数、作者节点数、作者-论文关联、按萃取主题(Task)分组的篇数。

    上方四张卡片始终为**全库**；by_topic 在带 query/task_topic 时为**当前筛选命中集合**内分布，
    与论文列表一致，避免「搜了一批相关论文，主题条却仍是全库」的错位。
    """
    try:
        stats = await neo4j_client.get_library_stats(
            search_query=query,
            topic_filter=task_topic,
            search_mode=search_mode,
        )
        return APIResponse(code=200, message="success", data=stats)
    except Exception as e:
        logger.error("Failed to get library stats: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Library stats failed: {str(e)}"
        )


@router.get("/papers/{arxiv_id}", response_model=APIResponse)
async def get_paper_detail(arxiv_id: str) -> APIResponse:
    """
    获取论文详情.

    GET /api/v1/papers/{arxiv_id}

    返回论文的完整信息，包括：
    - 基本元数据 (标题、作者、日期)
    - 萃取数据 (核心问题、提出方法、创新点、局限性)
    - 实验数据 (基线、数据集、指标)
    - 关联图谱

    Args:
        arxiv_id: arXiv 论文 ID (例如: "2506.02009")

    Returns:
        Paper detail with extraction data and graph
    """
    logger.info("Fetching paper detail: arxiv_id=%s", arxiv_id)

    try:
        # 获取论文基本信息
        paper_data = await neo4j_client.get_paper_by_id(arxiv_id)

        if not paper_data:
            raise HTTPException(
                status_code=404,
                detail=f"Paper {arxiv_id} not found"
            )

        # 获取关联图谱
        graph_data = await neo4j_client.get_paper_graph(arxiv_id)

        # 格式化图谱数据
        nodes = [
            {
                "id": n["id"],
                "labels": n["labels"],
                "properties": n["properties"]
            }
            for n in graph_data.get("nodes", [])
        ]

        relationships = [
            {
                "source_id": r["source_id"],
                "target_id": r["target_id"],
                "type": r["type"]
            }
            for r in graph_data.get("relationships", [])
        ]

        return APIResponse(
            code=200,
            message="success",
            data={
                "paper": paper_data,
                "graph": {
                    "nodes": nodes,
                    "relationships": relationships
                }
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch paper detail: %s", e)
        raise HTTPException(status_code=500, detail=f"Paper detail fetch failed: {str(e)}")
