"""
arXiv Radar Service

使用 arxiv 包实现异步论文抓取。
获取论文元数据，提取 summary 或清洗 HTML 正文。
实现幂等性检查、速率限制、内容长度校验。
支持 PDF 下载到本地存储。

防线3: 论文首尾截断算法 - 解决长文本 Token 爆炸和注意力丢失问题

领域预设优化：通过构建精确的 arXiv 搜索查询，提高论文相关性。

Reference: ARCHITECTURE.md Section 2 (Module A), TECH_DESIGN.md Section 3,
CODE_REVIEW.md Section 2, 4
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import arxiv
import httpx
from bs4 import BeautifulSoup

from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.models.task_models import get_domain_preset, DomainPreset

logger = logging.getLogger(__name__)


# =============================================================================
# 防线3: 论文首尾截断算法常量
# =============================================================================

# 最大文本长度（字符数）
MAX_TEXT_LENGTH = 15000
# 头部保留长度
HEAD_LENGTH = 7500
# 尾部保留长度
TAIL_LENGTH = 7500
# 中间省略标记
MIDDLE_OMISSION = "\n\n...[MIDDLE OMITTED FOR CONTEXT OPTIMIZATION]...\n\n"


# =============================================================================
# 领域预设与查询构建
# =============================================================================

def build_optimized_query(user_query: str, domain_preset_key: str = "sre") -> str:
    """
    构建优化的 arXiv 搜索查询.

    通过领域预设添加包含词、排除词和类别限定，大幅提高搜索结果相关性。

    Args:
        user_query: 用户输入的原始查询
        domain_preset_key: 领域预设键名 (sre/aiops/microservices/distributed/cloudnative/custom)

    Returns:
        优化后的 arXiv 搜索查询字符串

    Example:
        >>> build_optimized_query("site reliability engineering", "sre")
        '(all:"site reliability engineering" OR all:"incident management" OR all:"SLO") ANDNOT (all:"CLIP" OR all:"image segmentation") AND (cat:cs.SE OR cat:cs.DC)'
    """
    preset = get_domain_preset(domain_preset_key)

    # custom 预设不添加任何过滤
    if preset.key == "custom":
        logger.info(f"Using custom query mode: '{user_query}'")
        return user_query

    # 构建核心查询：用户查询 + 包含词
    include_parts = [f'all:"{user_query}"']

    # 添加领域相关词 (最多取前3个避免查询过长)
    for term in preset.include_terms[:3]:
        include_parts.append(f'all:"{term}"')

    # OR 组合包含条件
    query = f'({" OR ".join(include_parts)})'

    # 添加排除词
    if preset.exclude_terms:
        exclude_parts = [f'all:"{term}"' for term in preset.exclude_terms]
        query += f' ANDNOT ({" OR ".join(exclude_parts)})'

    # 添加 arXiv 类别限定
    if preset.categories:
        cat_parts = [f'cat:{cat}' for cat in preset.categories]
        query += f' AND ({" OR ".join(cat_parts)})'

    logger.info(f"Built optimized query for domain '{preset.name}': {query}")
    return query


@dataclass
class PaperContent:
    """论文内容和元数据容器."""
    arxiv_id: str
    title: str
    authors: list[str]
    published_date: str
    text_content: str
    html_url: str
    pdf_path: Optional[str] = None  # 本地 PDF 路径


class ArxivRadar:
    """arXiv 论文雷达服务 (异步实现)."""

    def __init__(self) -> None:
        self.rate_limit_delay = settings.arxiv_rate_limit_delay  # 3 秒间隔
        self.min_content_length = settings.arxiv_min_content_length  # 500 字符

    async def fetch_recent_papers(
        self,
        query: str,
        max_results: int = 10,
        domain_preset: str = "sre"
    ) -> list[PaperContent]:
        """
        搜索并获取 arXiv 论文.

        实现完整的流水线:
        1. 构建优化查询 (基于领域预设)
        2. 搜索 arXiv
        3. 幂等性检查 (检查是否已存在于 Neo4j)
        4. 异步获取 HTML 并清洗
        5. 内容长度校验
        6. 返回有效论文列表

        Args:
            query: arXiv 搜索查询 (用户输入)
            max_results: 最大获取数量
            domain_preset: 领域预设 (sre/aiops/microservices/distributed/cloudnative/custom)

        Returns:
            List of PaperContent for new papers
        """
        # 构建优化查询
        optimized_query = build_optimized_query(query, domain_preset)
        logger.info(f"Fetching papers: original='{query}', optimized='{optimized_query}', max_results={max_results}")

        # Step 1: Search arXiv with optimized query
        papers = self._search_papers(optimized_query, max_results)
        if not papers:
            logger.warning(f"No papers found for query: {optimized_query}")
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
            query: arXiv 搜索查询 (已优化的)
            max_results: 最大结果数

        Returns:
            List of arxiv.Result
        """
        logger.info(f"Searching arXiv with optimized query: '{query}'")

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

            # Step 3: 防线3 - 论文首尾截断 (Token 优化)
            # 如果文本过长，保留头部(Abstract/Introduction)和尾部(Experiments/Conclusion)
            text_content = self._truncate_text(text_content)

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

    def _truncate_text(self, text: str) -> str:
        """
        论文首尾截断算法 (Lost in the Middle / Cost Saving).

        防线3实现:
        - 如果文本长度超过 MAX_TEXT_LENGTH (15000字符)
        - 保留前 HEAD_LENGTH (7500字符) - 涵盖 Abstract 和 Introduction
        - 保留后 TAIL_LENGTH (7500字符) - 涵盖 Experiments 和 Conclusion
        - 中间部分替换为省略标记

        这样可以大幅减少 Token 消耗，同时保留最重要的头部和尾部信息。

        Args:
            text: 原始论文文本

        Returns:
            截断后的文本
        """
        if len(text) <= MAX_TEXT_LENGTH:
            return text

        head = text[:HEAD_LENGTH]
        tail = text[-TAIL_LENGTH:]

        logger.info(
            f"Truncating text: {len(text)} -> {HEAD_LENGTH + len(MIDDLE_OMISSION) + TAIL_LENGTH} chars "
            f"(head={HEAD_LENGTH}, tail={TAIL_LENGTH})"
        )

        return head + MIDDLE_OMISSION + tail


# =============================================================================
# PDF 下载功能
# =============================================================================

    async def download_paper_pdf(self, arxiv_id: str) -> Optional[str]:
        """
        下载论文 PDF 到本地存储.

        Args:
            arxiv_id: arXiv 论文 ID (不含版本号)

        Returns:
            本地 PDF 文件路径，失败返回 None
        """
        pdf_storage_path = Path(settings.pdf_storage_path)
        pdf_storage_path.mkdir(parents=True, exist_ok=True)

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_local_path = pdf_storage_path / f"{arxiv_id}.pdf"

        # 已存在则跳过
        if pdf_local_path.exists():
            logger.info(f"PDF already exists: {pdf_local_path}")
            return str(pdf_local_path)

        try:
            logger.info(f"Downloading PDF: {pdf_url}")
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                # 写入文件
                with open(pdf_local_path, "wb") as f:
                    f.write(response.content)

                file_size = len(response.content)
                logger.info(f"PDF downloaded successfully: {pdf_local_path} ({file_size} bytes)")
                return str(pdf_local_path)

        except Exception as e:
            logger.error(f"Failed to download PDF for {arxiv_id}: {e}")
            # 清理不完整的文件
            if pdf_local_path.exists():
                pdf_local_path.unlink(missing_ok=True)
            return None

    async def fetch_paper_with_pdf(
        self,
        paper: arxiv.Result
    ) -> Optional[PaperContent]:
        """
        获取论文内容并下载 PDF.

        Args:
            paper: arxiv.Result object

        Returns:
            PaperContent if successful, None otherwise
        """
        arxiv_id = self._normalize_arxiv_id(paper.entry_id)

        # 先获取 HTML 内容
        content = await self._fetch_paper_html(paper)
        if content is None:
            return None

        # 再下载 PDF (串行执行，避免对 arXiv 造成过大压力)
        try:
            pdf_path = await self.download_paper_pdf(arxiv_id)
            content.pdf_path = pdf_path
        except Exception as e:
            logger.warning(f"Failed to download PDF for {arxiv_id}: {e}")
            content.pdf_path = None

        return content


# 全局实例
arxiv_radar = ArxivRadar()


def get_arxiv_radar() -> ArxivRadar:
    """获取 arXiv Radar 实例."""
    return arxiv_radar
