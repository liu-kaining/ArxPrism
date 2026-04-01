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

from fastapi import APIRouter, HTTPException, Query

from src.database.neo4j_client import neo4j_client
from src.models.schemas import (
    APIResponse,
    PipelineTriggerRequest,
)
from src.worker.tasks import trigger_pipeline_task_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["pipeline", "graph"])


@router.post("/pipeline/trigger", response_model=APIResponse, status_code=202)
async def trigger_pipeline(request: PipelineTriggerRequest) -> APIResponse:
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
    logger.info(f"Pipeline trigger requested: query='{request.topic_query}'")

    try:
        # Dispatch to Celery (自动回退到同步模式如果 Redis 不可用)
        result = await trigger_pipeline_task_async(
            topic_query=request.topic_query,
            max_results=request.max_results
        )

        logger.info(f"Pipeline dispatched: {result}")

        return APIResponse(
            code=202,
            message="Pipeline triggered successfully",
            data=result
        )

    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {e}")
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
    logger.info(f"Fetching paper graph: arxiv_id={arxiv_id}")

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
        logger.error(f"Failed to fetch paper graph: {e}")
        raise HTTPException(status_code=500, detail=f"Graph fetch failed: {str(e)}")


@router.get("/graph/evolution", response_model=APIResponse)
async def get_evolution_tree(
    method_name: str = Query(..., description="Method name to trace")
) -> APIResponse:
    """
    构建方法技术进化树.

    GET /api/v1/graph/evolution?method_name={name}

    向上追溯 3 层祖先 (该方法改进的方法)，
    向下扩展 3 层后代 (改进该方法的方法)。

    Response 格式: D3.js / ECharts Graph Node/Link 数组。

    Args:
        method_name: 目标方法名称

    Returns:
        Evolution tree with nodes (including generation info) and links
    """
    logger.info(f"Fetching evolution tree: method={method_name}")

    try:
        tree_data = await neo4j_client.get_evolution_tree(method_name)

        if not tree_data.get("nodes"):
            raise HTTPException(
                status_code=404,
                detail=f"Method '{method_name}' not found in graph database"
            )

        # Format response
        nodes = [
            {
                "id": n["id"],
                "name": n["name"],
                "generation": n["generation"]
            }
            for n in tree_data["nodes"]
        ]

        links = [
            {
                "source": l["source"],
                "target": l["target"]
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
        logger.error(f"Failed to fetch evolution tree: {e}")
        raise HTTPException(status_code=500, detail=f"Evolution tree fetch failed: {str(e)}")


@router.get("/papers", response_model=APIResponse)
async def search_papers(
    query: str = Query("", description="Keyword/topic to search in stored papers"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> APIResponse:
    """
    按主题/关键词检索已入库论文列表（主路径：查 SRE 主题）。

    - query 为空：返回最近入库论文
    - query 非空：在 title/core_problem/method 中做 contains 匹配
    """
    try:
        total = await neo4j_client.count_search_papers(query=query)
        rows = await neo4j_client.search_papers(query=query, limit=limit, offset=offset)
        return APIResponse(
            code=200,
            message="success",
            data={
                "query": query,
                "limit": limit,
                "offset": offset,
                "total": total,
                "papers": rows,
            },
        )
    except Exception as e:
        logger.error(f"Failed to search papers: {e}")
        raise HTTPException(status_code=500, detail=f"Paper search failed: {str(e)}")


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
    logger.info(f"Fetching paper detail: arxiv_id={arxiv_id}")

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
        logger.error(f"Failed to fetch paper detail: {e}")
        raise HTTPException(status_code=500, detail=f"Paper detail fetch failed: {str(e)}")
