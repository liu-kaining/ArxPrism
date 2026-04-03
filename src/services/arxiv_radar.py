"""
arXiv Radar Service

使用 arxiv 包实现异步论文抓取。
**HTML-First**：优先解析 arXiv HTML 实验版正文；PDF 仅作兜底（减轻双栏错位幻觉）。
摘要分诊 (Triage)：下载全文前用 LLM 基于标题+摘要过滤非目标领域，节约 Token。
实现幂等性检查、速率限制、内容长度校验。

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
from typing import Any, Optional

import arxiv
import httpx
from bs4 import BeautifulSoup

from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.models.task_models import get_domain_preset, DomainPreset
from src.services.llm_extractor import get_llm_extractor
from src.services.r2_storage import get_r2_storage

logger = logging.getLogger(__name__)

# PyMuPDF 导入 (PDF 解析)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed, PDF parsing will be disabled")


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


def _arxiv_safe_phrase(text: str) -> str:
    """去掉会破坏 all:\"...\" 的引号与多余空白。"""
    if not text:
        return ""
    return " ".join(text.replace('"', " ").replace("\\", " ").split())


def build_optimized_query(user_query: str, domain_preset_key: str = "sre") -> str:
    """
    构建优化的 arXiv 搜索查询。

    旧逻辑曾把「用户关键词」与「预设 cat: 限定」用 AND 绑死，例如 SRE 预设限定
    cs.SE/cs.DC 时，用户搜 \"artificial intelligence\" 会几乎永远 0 条（AI 论文多在 cs.AI/cs.LG）。

    现逻辑：
    - 用户词：all: 全文字段匹配，不受预设类别限制。
    - 预设词 + 类别：另一支路，用于在目标学科里按预设主题捞文。
    - 两支路 OR 合并，再套排除词。

    custom：原样返回用户查询（自行承担 arXiv 语法）。
    """
    preset = get_domain_preset(domain_preset_key)

    if preset.key == "custom":
        q = (user_query or "").strip()
        logger.info("Using custom query mode: %r", q)
        return q

    user_q = _arxiv_safe_phrase((user_query or "").strip())

    exclude_suffix = ""
    if preset.exclude_terms:
        exclude_parts = [
            f'all:"{_arxiv_safe_phrase(t)}"' for t in preset.exclude_terms
        ]
        exclude_suffix = f' ANDNOT ({" OR ".join(exclude_parts)})'

    cat_parts = [f"cat:{c}" for c in preset.categories] if preset.categories else []
    cat_clause = f'({" OR ".join(cat_parts)})' if cat_parts else None

    preset_fragments = [
        f'all:"{_arxiv_safe_phrase(t)}"' for t in preset.include_terms[:3]
    ]
    preset_or = f'({" OR ".join(preset_fragments)})' if preset_fragments else ""

    branches: list[str] = []
    if user_q:
        branches.append(f'all:"{user_q}"')
    if preset_or and cat_clause:
        branches.append(f"({preset_or} AND {cat_clause})")
    elif preset_or:
        branches.append(f"({preset_or})")
    elif cat_clause and user_q:
        branches.append(f'(all:"{user_q}" AND {cat_clause})')

    if not branches:
        core = 'all:"computer"'
    elif len(branches) == 1:
        core = branches[0]
    else:
        core = f'({" OR ".join(branches)})'

    query = core + exclude_suffix
    logger.info("Built optimized query for domain %r: %s", preset.name, query)
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
    source: str = "unknown"  # 内容来源: "pdf", "html", "summary"


@dataclass(frozen=True)
class ArxivFetchStats:
    """一次抓取的可观测统计（任务说明与排障）。"""

    original_query: str
    optimized_query: str
    search_hits: int
    accepted: int


class ArxivRadar:
    """arXiv 论文雷达服务 (异步实现).

    内容获取优先级:
    1. PDF 下载 + PyMuPDF 解析 (最佳质量)
    2. HTML 页面解析 (中等质量)
    3. arXiv summary 兜底 (最低质量)
    """

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
        4. 下载 PDF 并解析 (优先)
        5. 内容长度校验
        6. 返回有效论文列表

        Args:
            query: arXiv 搜索查询 (用户输入)
            max_results: 最大获取数量
            domain_preset: 领域预设 (sre/aiops/microservices/distributed/cloudnative/custom)

        Returns:
            List of PaperContent for new papers
        """
        papers, _ = await self.fetch_recent_papers_with_stats(
            query, max_results, domain_preset
        )
        return papers

    async def fetch_recent_papers_with_stats(
        self,
        query: str,
        max_results: int = 10,
        domain_preset: str = "sre",
    ) -> tuple[list[PaperContent], ArxivFetchStats]:
        """同 fetch_recent_papers，额外返回 arXiv 命中数与最终可处理篇数。"""
        optimized_query = build_optimized_query(query, domain_preset)
        logger.info(
            "Fetching papers: original=%r, optimized=%r, max_results=%s",
            query,
            optimized_query,
            max_results,
        )

        papers = self._search_papers(optimized_query, max_results)
        search_hits = len(papers)
        if not papers:
            logger.warning("No papers from arXiv search for query: %s", optimized_query)
            return [], ArxivFetchStats(
                original_query=query,
                optimized_query=optimized_query,
                search_hits=0,
                accepted=0,
            )

        results: list[PaperContent] = []
        for paper in papers:
            try:
                content = await self._fetch_paper_with_dedup(paper)
                if content is not None:
                    results.append(content)
            except Exception as e:
                logger.error(
                    "Failed to process paper %s: %s. Continuing...",
                    paper.entry_id,
                    e,
                )
                continue

        logger.info(
            "Fetched %s new papers out of %s search hits (original=%r)",
            len(results),
            search_hits,
            query,
        )
        stats = ArxivFetchStats(
            original_query=query,
            optimized_query=optimized_query,
            search_hits=search_hits,
            accepted=len(results),
        )
        return results, stats

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

        内容获取优先级（见 _fetch_paper_content）: HTML-First，PDF 兜底，summary 最后。

        Args:
            paper: arxiv.Result object

        Returns:
            PaperContent if new paper, None if exists or fetch fails
        """
        arxiv_id = self._normalize_arxiv_id(paper.entry_id)

        # Step 1: Idempotency check - 检查是否已存在于 Neo4j
        try:
            exists = await neo4j_client.check_paper_exists(arxiv_id)
            if exists:
                logger.info(f"Paper {arxiv_id} already exists in database, skipping")
                return None
        except Exception as e:
            logger.warning(f"Failed to check paper existence for {arxiv_id}: {e}")

        # Step 2: Rate limiting (arXiv 君子协定)
        await asyncio.sleep(self.rate_limit_delay)

        # Step 2b: LLM 分诊（标题+摘要），不相关则绝不下载 PDF/HTML 全文
        abstract = getattr(paper, "summary", "") or ""
        try:
            is_relevant = await get_llm_extractor().triage_paper(paper.title, abstract)
        except Exception as e:
            logger.warning(f"Triage raised for {arxiv_id}, fail-open: {e}")
            is_relevant = True
        if not is_relevant:
            logger.info(f"Triage rejected: {arxiv_id}")
            return None

        # Step 3: 尝试获取全文 (HTML-First -> PDF 兜底 -> Summary)
        content = await self._fetch_paper_content(paper)
        return content

    async def _fetch_paper_content(
        self,
        paper: arxiv.Result
    ) -> Optional[PaperContent]:
        """
        获取论文内容，按优先级尝试不同来源.

        优先级: **HTML-First** > PDF（兜底）> arXiv Summary

        Args:
            paper: arxiv.Result object

        Returns:
            PaperContent if successful, None otherwise
        """
        arxiv_id = self._normalize_arxiv_id(paper.entry_id)
        html_url = f"https://arxiv.org/html/{arxiv_id}"
        entry_url = getattr(paper, "entry_id", f"https://arxiv.org/abs/{arxiv_id}")

        # ===== 优先级 1: HTML 解析（HTML-First，减轻 PDF 双栏错位幻觉）=====
        text_content = await self._try_fetch_from_html(arxiv_id, html_url)
        if text_content and len(text_content) >= self.min_content_length:
            text_content = self._truncate_text(text_content)
            logger.info(
                f"Paper {arxiv_id}: HTML-First — extracted from HTML ({len(text_content)} chars)"
            )
            return PaperContent(
                arxiv_id=arxiv_id,
                title=paper.title,
                authors=[author.name for author in paper.authors],
                published_date=self._format_date(
                    getattr(paper, "published", None)
                    or getattr(paper, "published_date", None)
                    or getattr(paper, "updated", None)
                ),
                text_content=text_content,
                html_url=html_url,
                pdf_path=None,
                source="html"
            )
        logger.warning(
            f"Paper {arxiv_id}: HTML-First path failed or too short; falling back to PDF if available"
        )

        # ===== 优先级 2: PDF 解析（兜底）=====
        if PYMUPDF_AVAILABLE:
            text_content, local_pdf_path, public_pdf_url = await self._try_fetch_from_pdf(arxiv_id)
            if text_content and len(text_content) >= self.min_content_length:
                text_content = self._truncate_text(text_content)
                logger.info(
                    f"Paper {arxiv_id}: PDF fallback — extracted ({len(text_content)} chars)"
                )
                return PaperContent(
                    arxiv_id=arxiv_id,
                    title=paper.title,
                    authors=[author.name for author in paper.authors],
                    published_date=self._format_date(
                        getattr(paper, "published", None)
                        or getattr(paper, "published_date", None)
                        or getattr(paper, "updated", None)
                    ),
                    text_content=text_content,
                    html_url=html_url,
                    pdf_path=public_pdf_url,
                    source="pdf"
                )
            logger.warning(f"Paper {arxiv_id}: PDF fallback failed or too short; trying summary")

        # ===== 优先级 3: arXiv Summary 兜底 =====
        text_content = (getattr(paper, "summary", "") or "").strip()
        if text_content and len(text_content) >= self.min_content_length:
            text_content = self._truncate_text(text_content)
            logger.info(
                f"Paper {arxiv_id}: Summary fallback (priority 3) ({len(text_content)} chars)"
            )
            return PaperContent(
                arxiv_id=arxiv_id,
                title=paper.title,
                authors=[author.name for author in paper.authors],
                published_date=self._format_date(
                    getattr(paper, "published", None)
                    or getattr(paper, "published_date", None)
                    or getattr(paper, "updated", None)
                ),
                text_content=text_content,
                html_url=entry_url,
                pdf_path=None,
                source="summary"
            )

        logger.error(f"Paper {arxiv_id}: All content extraction methods failed")
        return None

    async def _try_fetch_from_pdf(
        self,
        arxiv_id: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        尝试从 PDF 提取文本内容.

        Args:
            arxiv_id: arXiv 论文 ID

        Returns:
            (text_content, local_pdf_path, public_pdf_url) 或 (None, None, None)
            - local_pdf_path: 本地 PDF 路径
            - public_pdf_url: R2 公开访问 URL (如果 R2 未启用则为 None)
        """
        pdf_storage_path = Path(settings.pdf_storage_path)
        pdf_storage_path.mkdir(parents=True, exist_ok=True)

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_local_path = pdf_storage_path / f"{arxiv_id}.pdf"

        try:
            # 下载 PDF
            logger.info(f"Downloading PDF: {pdf_url}")
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                # 写入本地文件
                with open(pdf_local_path, "wb") as f:
                    f.write(response.content)

                file_size = len(response.content)
                logger.info(f"PDF downloaded: {pdf_local_path} ({file_size} bytes)")

            # 解析 PDF (使用 to_thread 避免阻塞事件循环)
            text_content = await asyncio.to_thread(self._extract_text_from_pdf, str(pdf_local_path))
            if text_content:
                # 上传到 R2 (如果启用)
                r2_storage = get_r2_storage()
                public_url = r2_storage.upload_pdf(str(pdf_local_path), arxiv_id)
                if public_url:
                    logger.info(f"PDF uploaded to R2: {public_url}")
                    return text_content, str(pdf_local_path), public_url
                else:
                    # R2 未启用，返回本地路径作为 public_url
                    return text_content, str(pdf_local_path), str(pdf_local_path)
            else:
                # 解析失败，删除文件
                pdf_local_path.unlink(missing_ok=True)
                return None, None, None

        except Exception as e:
            logger.error(f"Failed to download/parse PDF for {arxiv_id}: {e}")
            # 清理不完整的文件
            if pdf_local_path.exists():
                pdf_local_path.unlink(missing_ok=True)
            return None, None, None

    def _extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        使用 PyMuPDF 从 PDF 提取文本.

        Args:
            pdf_path: 本地 PDF 文件路径

        Returns:
            提取的文本内容，失败返回 None
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available, cannot extract PDF text")
            return None

        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc):
                # 提取文本，保留布局
                text = page.get_text("text")
                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n\n".join(text_parts)

            # 清理文本
            full_text = re.sub(r"\s+", " ", full_text)
            full_text = full_text.strip()

            logger.info(f"Extracted {len(full_text)} chars from PDF: {pdf_path}")
            return full_text

        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            return None

    async def _try_fetch_from_html(
        self,
        arxiv_id: str,
        html_url: str
    ) -> Optional[str]:
        """
        尝试从 arXiv HTML 页面提取文本.

        Args:
            arxiv_id: arXiv 论文 ID
            html_url: HTML 页面 URL

        Returns:
            提取的文本内容，失败返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(html_url)
                response.raise_for_status()
                html = response.text

            text_content = self._clean_html(html)
            return text_content

        except Exception as e:
            logger.warning(f"Failed to fetch HTML for {arxiv_id}: {e}")
            return None

    def _clean_html(self, html: str) -> str:
        """
        清洗 HTML 内容.

        移除:
        - style, script, nav, footer, header 标签及其内容
        - 参考文献部分（避免 LLM 幻觉）
        - Base64 图片
        - meta 标签
        - 过多空白字符

        Reference: ARCHITECTURE.md Section 2
        """
        soup = BeautifulSoup(html, "html.parser")

        # Step 1: 移除无用标签
        for tag in soup.find_all(["style", "script", "nav", "footer", "header"]):
            tag.decompose()

        # Step 2: 移除参考文献部分（避免 LLM 产生幻觉）
        for elem in soup.find_all(class_=re.compile(r"(bibliography|references)", re.IGNORECASE)):
            elem.decompose()

        # 也检查 id 属性
        for elem in soup.find_all(id=re.compile(r"(bibliography|references)", re.IGNORECASE)):
            elem.decompose()

        # Step 3: 移除 Base64 图片
        for img in soup.find_all("img"):
            if img.get("src", "").startswith("data:"):
                img.decompose()

        # Step 4: 移除 meta 标签
        for meta in soup.find_all("meta"):
            meta.decompose()

        # Step 5: 提取全部正文文本
        text = soup.get_text(separator=" ", strip=True)

        # Step 6: 清理多余空白
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

        Args:
            text: 原始论文文本

        Returns:
            截断后的文本
        """
        # 切除 References / Bibliography 之后的内容，避免尾部截断全是参考文献诱发 baseline 幻觉
        ref_boundary = re.search(
            r"\n(?:\d+\.\s*)?(?:References|Bibliography)\s*\n",
            text,
            re.IGNORECASE,
        )
        if ref_boundary:
            text = text[: ref_boundary.start()]

        if len(text) <= MAX_TEXT_LENGTH:
            return text

        head = text[:HEAD_LENGTH]
        tail = text[-TAIL_LENGTH:]

        logger.info(
            f"Truncating text: {len(text)} -> {HEAD_LENGTH + len(MIDDLE_OMISSION) + TAIL_LENGTH} chars "
            f"(head={HEAD_LENGTH}, tail={TAIL_LENGTH})"
        )

        return head + MIDDLE_OMISSION + tail

    def preview_arxiv_search(
        self,
        query: str,
        domain_preset: str,
        limit: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        仅查询 arXiv 元数据（标题/作者/摘要），不下载全文、不写库、不分诊。
        用于创建抓取任务前确认「当前关键词 + 领域预设」是否命中论文。
        """
        q = (query or "").strip()
        if not q:
            return "", []
        cap = max(1, min(int(limit), 25))
        optimized = build_optimized_query(q, domain_preset)
        raw = self._search_papers(optimized, cap)
        papers: list[dict[str, Any]] = []
        for r in raw:
            entry = getattr(r, "entry_id", "") or ""
            aid = self._normalize_arxiv_id(entry)
            title = (getattr(r, "title", None) or "").replace("\n", " ").strip()
            auth_objs = getattr(r, "authors", None) or []
            authors: list[str] = []
            for a in auth_objs:
                name = getattr(a, "name", None) or str(a)
                if name:
                    authors.append(name)
            pub = getattr(r, "published", None)
            published_date = self._format_date(pub) if pub else ""
            summ = getattr(r, "summary", None) or ""
            summ = " ".join(summ.split())
            preview = summ[:420] + ("…" if len(summ) > 420 else "")
            papers.append(
                {
                    "arxiv_id": aid,
                    "title": title,
                    "authors": authors,
                    "published_date": published_date,
                    "summary_preview": preview,
                }
            )
        return optimized, papers


# 全局实例
arxiv_radar = ArxivRadar()


def get_arxiv_radar() -> ArxivRadar:
    """获取 arXiv Radar 实例."""
    return arxiv_radar
