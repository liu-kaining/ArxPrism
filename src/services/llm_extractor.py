"""
LLM Extractor Service

使用官方 openai 异步客户端实现论文结构化萃取。
包含 PROMPT_ENGINEERING.md 中的系统提示词。
开启 response_format={ "type": "json_object" }。
强制使用 PaperExtractionResponse.model_validate_json() 解析结果。
加入最多 3 次的指数退避重试。

Reference: PROMPT_ENGINEERING.md, TECH_DESIGN.md Section 2,
CODE_REVIEW.md Section 3
"""

import asyncio
import json
import logging
from typing import Optional

from openai import AsyncOpenAI, RateLimitError, APITimeoutError
from pydantic import ValidationError

from src.core.config import settings
from src.models.schemas import PaperExtractionResponse

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompt (from PROMPT_ENGINEERING.md Section 1)
# =============================================================================
SYSTEM_PROMPT = """你现在是一位拥有 20 年经验的顶尖云原生架构师、SRE (站点可靠性工程) 专家和前沿学术研究员。
你的任务是阅读一篇最新的学术论文（通常为清洗后的 HTML 或 LaTeX 文本），并极其精确地从中萃取出结构化的核心知识。

【最高指令与防御机制】
1. 零幻觉容忍 (Zero Hallucination)：你提取的所有信息必须 100% 来源于提供的论文文本。严禁使用你的先验知识进行编造、脑补、推测或过度引申。如果论文中没有明确提及某个字段的信息（尤其是 baselines_beaten 或 datasets_used），请在该字段的数组中保持为空 `[]`，或在字符串字段严格输出 "NOT_MENTIONED"。
2. 领域安全锁 (Domain Gatekeeper)：在开始提取之前，请务必判断该论文是否真实属于"计算机系统、分布式计算、软件工程、AIOps、微服务、站点可靠性工程(SRE)"领域。如果它属于计算机视觉(如纯图像分类)、纯医学、纯物理学等毫不相干的领域（即使包含同名缩写如 SRE-CLIP），请将 `is_relevant_to_domain` 设置为 false，并停止后续所有深度提取（其他字段可留空或填默认值）。
3. 专家级精炼 (Expert Conciseness)：你的受众是资深技术专家（如量化研究员、架构师）。请使用极度精炼，专业、一针见血的学术/工程语言（中文）进行总结。拒绝废话、套话和诸如"本研究是一项很有意义的探索"之类的空泛表达。
4. 实体归一化 (Entity Normalization)：在提取 `baselines_beaten`、`datasets_used`、`metrics_improved` 等可能作为知识图谱节点 (Nodes) 的实体时，请尽量提取其专有名词或标准缩写（例如：提取 "DeepLog" 而不是 "a deep learning based log anomaly detection method"），以便于后续的图谱实体对齐。

【输出格式要求】
你必须且只能输出一个合法的 JSON 对象。不要包含任何 Markdown 格式符号（如 ```json），不要包含任何额外的解释性、过渡性文本。你的输出将被程序直接用 `json.loads()` 解析。JSON 结构必须严格遵守预定义的 Schema。
"""

USER_PROMPT_TEMPLATE = """请基于 System Prompt 中的指令和严格的 JSON Schema，对以下提供的论文文本进行专业萃取。

<PAPER_TEXT>
{paper_text}
</PAPER_TEXT>

请严格按照以下 JSON Schema 输出：
{{
  "is_relevant_to_domain": true,
  "paper_id": "论文的 arXiv ID (例如: 2506.02009)",
  "title": "论文的英文原文标题",
  "authors": ["Author 1", "Author 2"],
  "publication_date": "YYYY-MM-DD",

  "extraction_data": {{
    "core_problem": "用 1-2 句话，极其精准地概括这篇论文要解决的【底层痛点】。必须切中要害，说明为什么现有的方法不够好。",

    "proposed_method": {{
      "name": "论文提出的核心模型、架构或算法的名称（通常有缩写，如 STRATUS, AMER-RCL, FaithLog）。如果未命名，提炼一个能概括其核心特征的极简短语。",
      "description": "用 50-100 字，简要概括该方法的核心机制或工作流。它到底是怎么运作的？"
    }},

    "knowledge_graph_nodes": {{
      "baselines_beaten": ["基线模型A", "基线算法B"],
      "datasets_used": ["数据集A", "工业环境B"],
      "metrics_improved": ["指标A (提升 X%)", "指标B (降低 Y%)"]
    }},

    "critical_analysis": {{
      "key_innovations": [
        "核心创新点 1（理论或机制层面）",
        "核心创新点 2（架构或工程落地层面）"
      ],
      "limitations": [
        "局限性 1（重点提取作者在 Conclusion 或 Discussion 中明确承认的缺陷或未来工作）",
        "局限性 2（如果没有明确写出，结合你作为 SRE 专家的视角，指出该方法在极端高并发或真实生产环境中可能面临的工程落地阻碍，但必须注明这是专家推断）"
      ]
    }}
  }}
}}
"""


class LLMExtractor:
    """基于大模型的论文萃取服务 (支持指数退避重试)."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.max_retries = settings.llm_max_retries  # 最大重试次数 = 3
        self.base_delay = settings.llm_base_delay  # 基础延迟 = 2.0 秒
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

    async def extract(
        self,
        paper_text: str,
        paper_id: str,
        title: str,
        authors: list[str],
        publication_date: str
    ) -> Optional[PaperExtractionResponse]:
        """
        使用 LLM 从论文文本中萃取结构化信息.

        实现最多 3 次的指数退避重试 (针对解析失败或 API 异常)。
        失败时返回 None，绝不抛出异常阻断主程序。

        Args:
            paper_text: 清洗后的论文文本
            paper_id: arXiv ID
            title: 论文标题
            authors: 作者列表
            publication_date: 发布日期 (YYYY-MM-DD)

        Returns:
            PaperExtractionResponse if successful, None otherwise
        """
        logger.info(f"Starting LLM extraction for paper: {paper_id}")

        user_prompt = USER_PROMPT_TEMPLATE.format(paper_text=paper_text)
        last_error: str = "Unknown error"
        last_response: str = ""

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"LLM extraction attempt {attempt}/{self.max_retries}")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                response_content = response.choices[0].message.content
                last_response = response_content
                logger.debug(f"LLM raw response: {response_content[:200]}...")

                # =================================================================
                # 关键: 使用 model_validate_json() 进行 Pydantic 校验
                # Reference: TECH_DESIGN.md Section 2
                # =================================================================
                extraction = PaperExtractionResponse.model_validate_json(response_content)

                # 填充论文元数据 (LLM 输出可能不包含这些)
                extraction.paper_id = paper_id
                extraction.title = title
                extraction.authors = authors
                extraction.publication_date = publication_date

                logger.info(f"Successfully extracted data for paper: {paper_id}")
                return extraction

            except json.JSONDecodeError as e:
                last_error = f"JSON parse failed: {e}"
                logger.warning(
                    f"Attempt {attempt}: JSON parse failed - {e}. "
                    f"Response: {last_response[:100] if last_response else 'N/A'}"
                )

            except ValidationError as e:
                last_error = f"Pydantic validation failed: {e}"
                logger.warning(f"Attempt {attempt}: Pydantic validation failed - {e}")

            except (RateLimitError, APITimeoutError) as e:
                last_error = f"API error: {e}"
                logger.warning(f"Attempt {attempt}: API error - {e}")

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(f"Attempt {attempt}: Unexpected error - {e}")

            # =================================================================
            # 指数退避延迟
            # Reference: TECH_DESIGN.md Section 2
            # =================================================================
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {delay}s (exponential backoff)...")
                await asyncio.sleep(delay)

        # 所有重试都失败
        logger.error(
            f"Paper {paper_id}: All {self.max_retries} attempts failed. "
            f"Last error: {last_error}"
        )
        return None

    async def extract_with_semaphore(
        self,
        paper_text: str,
        paper_id: str,
        title: str,
        authors: list[str],
        publication_date: str,
        semaphore: Optional[asyncio.Semaphore] = None
    ) -> Optional[PaperExtractionResponse]:
        """
        使用信号量控制并发量的萃取方法.

        使用 asyncio.Semaphore 限制同时发往 OpenAI 的请求量 (最多 5 个)。
        Reference: TECH_DESIGN.md Section 3

        Args:
            paper_text: 清洗后的论文文本
            paper_id: arXiv ID
            title: 论文标题
            authors: 作者列表
            publication_date: 发布日期
            semaphore: asyncio.Semaphore for concurrency control

        Returns:
            PaperExtractionResponse if successful, None otherwise
        """
        if semaphore is None:
            semaphore = asyncio.Semaphore(5)

        async with semaphore:
            return await self.extract(
                paper_text=paper_text,
                paper_id=paper_id,
                title=title,
                authors=authors,
                publication_date=publication_date
            )


# 全局实例
llm_extractor = LLMExtractor()


def get_llm_extractor() -> LLMExtractor:
    """获取 LLM 萃取器实例."""
    return llm_extractor
