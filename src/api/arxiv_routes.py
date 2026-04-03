"""
arXiv 检索预览 API（不入库、不抓取全文）.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.schemas import APIResponse
from src.services.arxiv_radar import arxiv_radar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arxiv", tags=["arxiv"])


class ArxivPreviewSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="用户搜索词")
    domain_preset: str = Field(default="sre", max_length=64, description="与创建任务相同的领域预设")
    limit: int = Field(default=15, ge=1, le=25, description="预览条数上限")


@router.post("/preview-search", response_model=APIResponse)
async def preview_arxiv_search(body: ArxivPreviewSearchRequest) -> APIResponse:
    """
    预览 arXiv 检索结果（仅元数据）.

    使用与抓取任务相同的 `build_optimized_query` 逻辑，便于在「创建任务」前
    确认关键词与领域预设是否过严或过宽。实际抓取仍会经过在库去重、分诊与全文拉取。
    """
    try:
        optimized, papers = await asyncio.to_thread(
            arxiv_radar.preview_arxiv_search,
            body.query.strip(),
            body.domain_preset,
            body.limit,
        )
    except Exception as e:
        logger.exception("arXiv preview search failed: %s", e)
        raise HTTPException(status_code=502, detail=f"arXiv 检索失败: {e}") from e

    return APIResponse(
        code=200,
        message="success",
        data={
            "optimized_query": optimized,
            "returned": len(papers),
            "papers": papers,
            "note": (
                "以上为 arXiv 即时检索结果；创建任务后还会过滤已在库论文、"
                "LLM 分诊与全文可用性，最终入库篇数可能更少。"
            ),
        },
    )
