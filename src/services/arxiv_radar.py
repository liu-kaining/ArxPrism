"""
arXiv Radar Service

使用 arxiv 包实现异步论文抓取。
获取论文元数据，提取 summary 或清洗 HTML 正文。
实现幂等性检查、速率限制、内容长度校验。

Reference: ARCHITECTURE.md Section 2 (Module A), TECH_DESIGN.md Section 3,
CODE_REVIEW.md Section 2, 4
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

import arxiv
import httpx
from bs4 import BeautifulSoup

from src.core.config import settings
from src.database.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


@dataclass
class PaperContent:
    """论文内容和元数据容器."""
    arxiv_id: str
    title: str
    authors: list[str]
    published_date: str
    text_content: str
    html_url: str


class ArxivRadar:
    """arXiv 论文雷达服务 (异步实现)."""

    def __init__(self) -> None:
        self.rate_limit_delay = settings.arxiv_rate_limit_delay  # 3 秒间隔
        self.min_content_length = settings.arxiv_min_content_length  # 500 字符

    async def fetch_recent_papers(
        self,
        query: str,
        max_results: int = 10
    ) -> list[PaperContent]:
        """
        搜索并获取 arXiv 论文.

        实现完整的流水线:
        1. 搜索 arXiv
        2. 幂等性检查 (检查是否已存在于 Neo4j)
        3. 异步获取 HTML 并清洗
        4. 内容长度校验
        5. 返回有效论文列表

        Args:
            query: arXiv 搜索查询
            max_results: 最大获取数量

        Returns:
            List of PaperContent for new papers
        """
        logger.info(f"Fetching papers: query='{query}', max_results={max_results}")

        # Step 1: Search arXiv
        papers = self._search_papers(query, max_results)
        if not papers:
            logger.warning(f"No papers found for query: {query}")
            return []

        # Step 2: Fetch each paper with dedup and rate limiting
        results: list[PaperContent] = []
        for paper in papers:
            try:
                content = await self._fetch_paper_with_dedup(paper)
                if content is not None:
                    results.append(content)
            except Exception as e:
                # 防御性编程: 绝不让单篇失败中断整个批处理
                logger.error(
                    f"Failed to process paper {paper.entry_id}: {e}. "
                    f"Continuing with next paper..."
                )
                continue

        logger.info(f"Fetched {len(results)} new papers out of {len(papers)} found")
        return results

    def _search_papers(
        self,
        query: str,
        max_results: int
    ) -> list[arxiv.Result]:
        """
        搜索 arXiv 论文.

        Args:
            query: arXiv 搜索查询
            max_results: 最大结果数

        Returns:
            List of arxiv.Result
        """
        logger.info(f"Searching arXiv: query='{query}', max_results={max_results}")

        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            results = list(client.results(search))
            logger.info(f"Found {len(results)} papers from arXiv")
            return results

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    async def _fetch_paper_with_dedup(
        self,
        paper: arxiv.Result
    ) -> Optional[PaperContent]:
        """
        获取论文内容前先检查是否已存在 (幂等性).

        Args:
            paper: arxiv.Result object

        Returns:
            PaperContent if new paper, None if exists or fetch fails
        """
        arxiv_id = self._normalize_arxiv_id(paper.entry_id)

        # Step 1: Idempotency check - 检查是否已存在于 Neo4j
        # Reference: ARCHITECTURE.md Section 2
        try:
            exists = await neo4j_client.check_paper_exists(arxiv_id)
            if exists:
                logger.info(f"Paper {arxiv_id} already exists in database, skipping")
                return None
        except Exception as e:
            # 幂等性检查失败不阻断处理
            logger.warning(f"Failed to check paper existence for {arxiv_id}: {e}")

        # Step 2: Rate limiting (arXiv 君子协定)
        await asyncio.sleep(self.rate_limit_delay)

        # Step 3: Fetch and parse HTML
        return await self._fetch_paper_html(paper)

    async def _fetch_paper_html(self, paper: arxiv.Result) -> Optional[PaperContent]:
        """
        获取并清洗论文 HTML 内容.

        使用异步 httpx 避免阻塞事件循环。
        清洗规则: 移除 style, script, nav, footer, header, Base64 图片等。
        内容长度校验: 少于 500 字符视为无效页面。

        Args:
            paper: arxiv.Result object

        Returns:
            PaperContent if successful, None if parsing fails
        """
        arxiv_id = self._normalize_arxiv_id(paper.entry_id)
        logger.info(f"Fetching paper: {arxiv_id}")

        try:
            # arxiv 包不同版本的 Result 结构不同：有的没有 html_url
            html_url = getattr(paper, "html_url", None)
            if not html_url:
                # 尝试构造 arXiv HTML 页面（不带版本号）
                html_url = f"https://arxiv.org/html/{arxiv_id}"

            text_content: str = ""
            try:
                # 使用异步 HTTP 客户端 (避免阻塞 FastAPI 事件循环)
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    response = await client.get(html_url)
                    response.raise_for_status()
                    html = response.text

                # Step 1: 清洗 HTML
                text_content = self._clean_html(html)
            except Exception as e:
                # 兜底：至少用 arxiv summary 跑通链路（可后续再优化为 PDF/TeX 全文）
                logger.warning(
                    f"Paper {arxiv_id}: Failed to fetch/parse HTML ({html_url}): {e}. "
                    f"Falling back to arXiv summary."
                )
                text_content = (getattr(paper, "summary", "") or "").strip()
                html_url = getattr(paper, "entry_id", html_url) or html_url

            # Step 2: 内容长度校验
            # Reference: TECH_DESIGN.md Section 2
            if len(text_content) < self.min_content_length:
                logger.warning(
                    f"Paper {arxiv_id}: Content too short ({len(text_content)} chars), "
                    f"likely invalid page or paywall"
                )
                return None

            paper_content = PaperContent(
                arxiv_id=arxiv_id,
                title=paper.title,
                authors=[author.name for author in paper.authors],
                published_date=self._format_date(
                    getattr(paper, "published", None)
                    or getattr(paper, "published_date", None)
                    or getattr(paper, "updated", None)
                ),
                text_content=text_content,
                html_url=html_url
            )

            logger.info(f"Successfully fetched paper {arxiv_id} ({len(text_content)} chars)")
            return paper_content

        except Exception as e:
            logger.error(f"Failed to fetch paper {arxiv_id}: {e}")
            return None

    def _clean_html(self, html: str) -> str:
        """
        清洗 HTML 内容.

        移除:
        - style, script, nav, footer, header 标签及其内容
        - Base64 图片
        - meta 标签
        - 过多空白字符

        Reference: ARCHITECTURE.md Section 2
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted tags
        for tag in soup.find_all(["style", "script", "nav", "footer", "header"]):
            tag.decompose()

        # Remove Base64 images
        for img in soup.find_all("img"):
            if img.get("src", "").startswith("data:"):
                img.decompose()

        # Try to find main content - arXiv typically has abstract in .abstract
        abstract = soup.find("div", class_="abstract")
        if abstract:
            text = abstract.get_text(separator=" ", strip=True)
        else:
            # Fallback: full body text
            for meta in soup.find_all("meta"):
                meta.decompose()
            text = soup.get_text(separator=" ", strip=True)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _normalize_arxiv_id(self, entry_id: str) -> str:
        """
        归一化 arXiv ID (去除版本号).

        Example: https://arxiv.org/abs/2506.02009v3 -> 2506.02009
        """
        match = re.search(r"(\d{4}\.\d{4,5})", entry_id)
        if match:
            return match.group(1)
        return entry_id

    def _format_date(self, date) -> str:
        """格式化日期为 YYYY-MM-DD."""
        if hasattr(date, "strftime"):
            return date.strftime("%Y-%m-%d")
        return str(date)[:10]


# 全局实例
arxiv_radar = ArxivRadar()


def get_arxiv_radar() -> ArxivRadar:
    """获取 arXiv Radar 实例."""
    return arxiv_radar
