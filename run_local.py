#!/usr/bin/env python3
"""
ArxPrism 本地执行脚本

用于本地测试论文萃取流水线，无需启动 Docker 或 Celery。
直接执行: Radar -> LLM Extractor -> Neo4j

Usage:
    python run_local.py --query "site reliability engineering" --max_results 3
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.services.arxiv_radar import arxiv_radar, PaperContent
from src.services.llm_extractor import llm_extractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def print_header(text: str) -> None:
    """打印带样式的标题."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_step(step: str, text: str, emoji: str = "➜") -> None:
    """打印步骤信息."""
    print(f"  {emoji} [{step}] {text}")


def print_success(text: str) -> None:
    """打印成功信息."""
    print(f"  ✅ {text}")


def print_warning(text: str) -> None:
    """打印警告信息."""
    print(f"  ⚠️  {text}")


def print_error(text: str) -> None:
    """打印错误信息."""
    print(f"  ❌ {text}")


def print_paper(paper: PaperContent, index: int, total: int) -> None:
    """打印论文信息."""
    print(f"\n  📄 [{index}/{total}] {paper.arxiv_id}")
    print(f"      标题: {paper.title[:60]}..." if len(paper.title) > 60 else f"      标题: {paper.title}")
    print(f"      作者: {', '.join(paper.authors[:2])}{'...' if len(paper.authors) > 2 else ''}")
    print(f"      日期: {paper.published_date}")
    print(f"      内容长度: {len(paper.text_content)} chars")


async def process_single_paper(
    paper: PaperContent,
    index: int,
    total: int
) -> dict:
    """
    处理单篇论文的完整流水线.

    Returns:
        Dict with status, paper_id, and optional error message
    """
    print_paper(paper, index, total)

    # Step 1: LLM 萃取
    print_step("LLM", "正在萃取论文内容...", "🔮")

    try:
        extraction = await llm_extractor.extract(
            paper_text=paper.text_content,
            paper_id=paper.arxiv_id,
            title=paper.title,
            authors=paper.authors,
            publication_date=paper.published_date
        )
    except Exception as e:
        print_error(f"LLM 萃取失败: {e}")
        return {"status": "failed", "paper_id": paper.arxiv_id, "reason": str(e)}

    if extraction is None:
        print_warning("LLM 萃取返回 None (所有重试均失败)")
        return {"status": "failed", "paper_id": paper.arxiv_id, "reason": "extraction_failed"}

    # Step 2: 领域相关性检查
    if not extraction.is_relevant_to_domain:
        print_warning("论文不属于 SRE/云原生/AIOps 领域，已跳过")
        return {"status": "skipped", "paper_id": paper.arxiv_id, "reason": "domain_not_relevant"}

    if extraction.extraction_data is None:
        print_warning("领域相关但未返回 extraction_data，无法写入图谱")
        return {
            "status": "failed",
            "paper_id": paper.arxiv_id,
            "reason": "missing_extraction_data",
        }

    # 打印萃取结果摘要
    method_name = extraction.extraction_data.proposed_method.name
    comps = extraction.extraction_data.knowledge_graph_nodes.comparisons
    print_success(f"萃取成功! 方法: {method_name}")
    if comps:
        lines = [
            f"{c.baseline_method or '?'} @ {c.dataset or '?'} ({c.metrics_improvement or '—'})"
            for c in comps[:3]
        ]
        print(f"     对比实验: {'; '.join(lines)}")

    ed = extraction.extraction_data
    sum_txt = (paper.summary or "").strip()
    summary_zh = ""
    if sum_txt:
        print_step("翻译", "正在将摘要译为专业中文...", "🌐")
        tr = await llm_extractor.translate_arxiv_abstract_to_zh(
            abstract_en=sum_txt,
            paper_title=extraction.title or "",
        )
        summary_zh = (tr or "").strip()
        if summary_zh:
            print_success("摘要中译完成")
        else:
            print_warning("摘要中译失败或为空，将仅保存原文摘要")
    embed_parts = [extraction.title or "", ed.core_problem or ""]
    if sum_txt:
        embed_parts.append(sum_txt)
    embed_text = "\n\n".join(p for p in embed_parts if p)
    vec = await llm_extractor.generate_embedding(embed_text)
    upd = {"summary": sum_txt, "summary_zh": summary_zh}
    if vec and len(vec) == 1536:
        upd["embedding"] = vec
    extraction = extraction.model_copy(update=upd)

    # Step 3: 写入 Neo4j
    print_step("Neo4j", "正在写入图数据库...", "🗄️")

    try:
        success = await neo4j_client.upsert_paper_graph(extraction)
    except Exception as e:
        print_error(f"Neo4j 写入失败: {e}")
        return {"status": "failed", "paper_id": paper.arxiv_id, "reason": str(e)}

    if success:
        print_success(f"成功写入论文 {paper.arxiv_id} 到图数据库")
        return {"status": "success", "paper_id": paper.arxiv_id}
    else:
        print_error(f"Neo4j 写入返回失败")
        return {"status": "failed", "paper_id": paper.arxiv_id, "reason": "neo4j_upsert_failed"}


async def run_pipeline(query: str, max_results: int) -> dict:
    """
    执行完整的论文萃取流水线.

    Returns:
        Dict with summary of processing results
    """
    print_header("🚀 ArxPrism 本地执行流水线")

    print(f"  查询: {query}")
    print(f"  最大结果数: {max_results}")
    print()

    # Step 1: 初始化 Neo4j
    print_step("Neo4j", "正在连接图数据库...", "🔗")
    try:
        await neo4j_client.connect()
        is_connected = await neo4j_client.verify_connectivity()
        if is_connected:
            print_success(f"已连接到 Neo4j at {settings.neo4j_uri}")
        else:
            print_warning("无法验证 Neo4j 连接，但将继续尝试...")
    except Exception as e:
        print_error(f"Neo4j 连接失败: {e}")
        return {
            "status": "error",
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "results": []
        }

    # Step 2: 抓取论文
    print_header("📡 论文抓取阶段")
    print_step("Radar", f"正在搜索 arXiv: {query}", "🔍")

    try:
        papers = await arxiv_radar.fetch_recent_papers(query, max_results)
    except Exception as e:
        print_error(f"论文抓取失败: {e}")
        papers = []

    if not papers:
        print_warning("未找到任何论文")
        await neo4j_client.close()
        return {
            "status": "completed",
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "results": []
        }

    print_success(f"成功获取 {len(papers)} 篇论文")

    # Step 3: 萃取并写入
    print_header("🔮 论文萃取阶段")

    results = []
    for i, paper in enumerate(papers, 1):
        result = await process_single_paper(paper, i, len(papers))
        results.append(result)
        print()  # 空行分隔

    # 汇总统计
    success_count = sum(1 for r in results if r["status"] == "success")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    # 关闭 Neo4j 连接
    print_header("🔌 清理阶段")
    print_step("Neo4j", "正在关闭连接...", "👋")
    await neo4j_client.close()
    print_success("Neo4j 连接已关闭")

    # 最终汇总
    print_header("📊 执行结果汇总")
    print(f"  总计处理: {len(papers)} 篇")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ⏭️  跳过: {skipped_count} (领域不相关)")
    print(f"  ❌ 失败: {failed_count}")

    if success_count > 0:
        print(f"\n  🎉 {success_count} 篇论文已成功写入 Neo4j 图数据库!")

    return {
        "status": "completed",
        "total": len(papers),
        "success": success_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "results": results
    }


def main() -> None:
    """主入口函数."""
    parser = argparse.ArgumentParser(
        description="ArxPrism 本地执行脚本 - 论文萃取流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_local.py --query "site reliability engineering" --max_results 5
  python run_local.py --query "microservices" --max_results 10
  python run_local.py  # 使用默认参数
        """
    )

    parser.add_argument(
        "--query",
        type=str,
        default="site reliability engineering",
        help="arXiv 搜索查询 (default: 'site reliability engineering')"
    )

    parser.add_argument(
        "--max_results",
        type=int,
        default=3,
        help="最多抓取论文数量 (default: 3)"
    )

    args = parser.parse_args()

    # 验证参数
    if args.max_results < 1:
        print_error("max_results 必须 >= 1")
        sys.exit(1)

    if args.max_results > 100:
        print_warning("max_results > 100，可能需要较长时间")

    # 运行流水线
    try:
        result = asyncio.run(run_pipeline(args.query, args.max_results))

        # 根据结果返回退出码
        if result["status"] == "error":
            sys.exit(1)
        elif result["failed"] > 0 and result["success"] == 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")
        sys.exit(130)
    except Exception as e:
        print_error(f"执行过程中发生未预期错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
