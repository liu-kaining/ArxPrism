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
from typing import List, Optional

from openai import AsyncOpenAI, RateLimitError, APITimeoutError
from pydantic import ValidationError

from src.core.config import settings
from src.models.schemas import (
    EntityResolutionResponse,
    PaperExtractionResponse,
    TriageResponse,
)

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompt (from PROMPT_ENGINEERING.md Section 1)
# =============================================================================
SYSTEM_PROMPT = """你现在是一位拥有 20 年经验的顶尖云原生架构师、SRE (站点可靠性工程) 专家和前沿学术研究员。
你的任务是阅读一篇最新的学术论文（通常为清洗后的 HTML 或 LaTeX 文本），并极其精确地从中萃取出结构化的核心知识。

【最高指令与防御机制】
1. 零幻觉容忍 (Zero Hallucination)：你提取的所有信息必须 100% 来源于提供的论文文本。严禁使用你的先验知识进行编造、脑补、推测或过度引申。若论文未给出某对比实验的基线、数据集或指标，请将 `knowledge_graph_nodes.comparisons` 中对应条目留空字段或整条省略；字符串字段无依据时输出 "NOT_MENTIONED" 或保持空字符串。
2. 领域安全锁 (Domain Gatekeeper)：在开始提取之前，请务必判断该论文是否真实属于"计算机系统、分布式计算、软件工程、AIOps、微服务、站点可靠性工程(SRE)"领域。如果它属于计算机视觉(如纯图像分类)、纯医学、纯物理学等毫不相干的领域（即使包含同名缩写如 SRE-CLIP），请将 `is_relevant_to_domain` 设置为 false，并停止后续所有深度提取（其他字段可留空或填默认值）。
3. 专家级精炼 (Expert Conciseness)：你的受众是资深技术专家（如量化研究员、架构师）。请使用极度精炼，专业、一针见血的学术/工程语言（中文）进行总结。拒绝废话、套话和诸如"本研究是一项很有意义的探索"之类的空泛表达。
4. 实体归一化 (Entity Normalization)：在 `comparisons` 中填写 `baseline_method` 与 `dataset` 时，尽量使用论文中的专有名词或标准缩写（如 "DeepLog"、"HDFS"），避免整句描述，便于图谱实体对齐。`metrics_improvement` 用简短可读的幅度表述（如 "F1 +5.2%"）。

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
    "reasoning_process": "先思考…再提取…：通读实验与对比章节，列出在哪些数据集上、相对哪些基线、报告了哪些指标变化；再据此填写 comparisons。",

    "core_problem": "用 1-2 句话，极其精准地概括这篇论文要解决的【底层痛点】。必须切中要害，说明为什么现有的方法不够好。",

    "task_name": "提炼该论文要解决的核心任务专有名词（英文短语），如 Root Cause Analysis、Log Anomaly Detection；若无法概括则 NOT_MENTIONED",

    "proposed_method": {{
      "name": "论文提出的核心模型、架构或算法的名称（通常有缩写，如 STRATUS, AMER-RCL, FaithLog）。如果未命名，提炼一个能概括其核心特征的极简短语。",
      "description": "用 50-100 字，简要概括该方法的核心机制或工作流。它到底是怎么运作的？"
    }},

    "knowledge_graph_nodes": {{
      "comparisons": [
        {{
          "baseline_method": "DeepLog",
          "dataset": "HDFS",
          "metrics_improvement": "Accuracy +5.2%"
        }}
      ]
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

ENTITY_RESOLUTION_SYSTEM = """你是一个图谱实体对齐专家。
你的任务是阅读给定的算法/模型/方法名称列表（来自学术知识图谱的 Method 节点归一化键），
判断其中哪些名称指代**完全相同**的同一技术实体。
只有在含义与所指对象实质相同时才归为一组；不要强行合并仅相关或相似但不同的技术。"""

ENTITY_RESOLUTION_USER_TEMPLATE = """以下名称列表中的每一项都是图谱中已存在的 Method.name，请**原样**使用其中的字符串作为 primary_name 与 aliases，不要改写大小写或拼写。

名称列表（JSON 数组）：
{names_json}

请输出唯一一个 JSON 对象，格式严格如下（不要 Markdown）：
{{"clusters": [{{"primary_name": "<必须来自上述列表>", "aliases": ["<同义别名，均须来自上述列表>", "..."]}}]}}

规则：
- 只有 aliases 非空时才有融合意义；无同义词的名称不要生成 cluster。
- 同一名称不得同时出现在多个 cluster 中。
- primary_name 应选该组里最标准、最广为人知的写法（仍须是列表中的某一项）。
"""


class LLMExtractor:
    """基于大模型的论文萃取服务 (支持指数退避重试)."""

    def __init__(self) -> None:
        client_kwargs = {"api_key": settings.llm_api_key}
        if settings.llm_base_url:
            client_kwargs["base_url"] = settings.llm_base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.max_retries = settings.llm_max_retries  # 最大重试次数 = 3
        self.base_delay = settings.llm_base_delay  # 基础延迟 = 2.0 秒
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

    async def triage_paper(self, title: str, abstract: str) -> bool:
        """
        分诊台：仅根据标题与摘要判断是否值得下载全文并做深度萃取。

        失败时 fail-open 返回 True，避免因 LLM 抖动误杀全部流量。
        """
        triage_system = (
            "你是一个严格的学术审稿助手。只根据给出的论文标题与摘要判断："
            "该工作是否属于计算机系统、SRE、云原生、微服务、分布式系统、后端架构、"
            "AIOps、可观测性、日志/链路分析、AI 基础设施（训练/推理系统工程）等相关工程领域。"
            "若是纯 CV/纯 NLP 应用且与系统可靠性无关、纯医学/物理/社科等，则判为不相关。"
            "你必须只输出一个 JSON 对象，字段 is_relevant (boolean) 与 reason (string)。"
        )
        user_payload = (
            f"标题:\n{title}\n\n摘要:\n{(abstract or '').strip()}\n\n"
            "请输出 JSON: {\"is_relevant\": true/false, \"reason\": \"...\"}"
        )
        last_err = ""
        triage_max_tokens = 256
        triage_retries = 2

        for attempt in range(1, triage_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": triage_system},
                        {"role": "user", "content": user_payload},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=triage_max_tokens,
                )
                raw = resp.choices[0].message.content
                if not raw:
                    raise ValueError("empty triage response")
                parsed = TriageResponse.model_validate_json(raw)
                logger.info(
                    f"Triage: is_relevant={parsed.is_relevant} reason={parsed.reason[:120]!r}"
                )
                return parsed.is_relevant
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = str(e)
                logger.warning(f"Triage attempt {attempt}/{triage_retries} parse/validate failed: {e}")
            except (RateLimitError, APITimeoutError) as e:
                last_err = str(e)
                logger.warning(f"Triage attempt {attempt}/{triage_retries} API error: {e}")
            except Exception as e:
                last_err = str(e)
                logger.error(f"Triage attempt {attempt}/{triage_retries} unexpected: {e}")

            if attempt < triage_retries:
                await asyncio.sleep(self.base_delay * attempt)

        logger.warning(
            f"Triage failed after {triage_retries} attempts ({last_err}); fail-open -> proceed"
        )
        return True

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

    async def resolve_method_entities(
        self, method_names: List[str]
    ) -> Optional[EntityResolutionResponse]:
        """
        调用 LLM 对 Method 名称做同义聚类，供图谱物理融合使用。

        失败时返回 None；输入为空时返回空 clusters，不调用模型。
        """
        unique: List[str] = []
        seen: set[str] = set()
        for n in method_names:
            if not n or not isinstance(n, str):
                continue
            s = n.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            unique.append(s)

        if not unique:
            return EntityResolutionResponse(clusters=[])

        user_prompt = ENTITY_RESOLUTION_USER_TEMPLATE.format(
            names_json=json.dumps(unique, ensure_ascii=False)
        )
        last_error = ""
        last_response = ""
        max_tok = min(8192, self.max_tokens)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": ENTITY_RESOLUTION_SYSTEM},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=max_tok,
                )
                content = response.choices[0].message.content
                last_response = content or ""
                return EntityResolutionResponse.model_validate_json(content)
            except json.JSONDecodeError as e:
                last_error = f"JSON parse failed: {e}"
                logger.warning("resolve_method_entities attempt %s: %s", attempt, last_error)
            except ValidationError as e:
                last_error = f"Pydantic validation failed: {e}"
                logger.warning("resolve_method_entities attempt %s: %s", attempt, last_error)
            except (RateLimitError, APITimeoutError) as e:
                last_error = f"API error: {e}"
                logger.warning("resolve_method_entities attempt %s: %s", attempt, last_error)
            except Exception as e:
                last_error = str(e)
                logger.error("resolve_method_entities attempt %s: %s", attempt, e)

            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error(
            "resolve_method_entities failed after %s attempts: %s raw=%s",
            self.max_retries,
            last_error,
            (last_response[:200] if last_response else ""),
        )
        return None

    async def generate_embedding(self, text: str) -> list[float]:
        """
        调用 OpenAI Embeddings API（text-embedding-3-small，1536 维）。
        最多 2 次退避重试；全部失败返回 []。
        """
        if not (text or "").strip():
            return []
        cleaned = text.replace("\n", " ")
        if len(cleaned) > 24000:
            cleaned = cleaned[:24000]
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = await self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=cleaned,
                    dimensions=1536,
                )
                vec = response.data[0].embedding
                return list(vec) if vec is not None else []
            except Exception as e:
                last_error = e
                logger.warning(
                    "Embedding attempt %s/3 failed: %s",
                    attempt + 1,
                    e,
                )
                if attempt < 2:
                    await asyncio.sleep(self.base_delay * (attempt + 1))
        logger.error("Embedding failed after retries: %s", last_error)
        return []


# 全局实例
llm_extractor = LLMExtractor()


def get_llm_extractor() -> LLMExtractor:
    """获取 LLM 萃取器实例."""
    return llm_extractor
