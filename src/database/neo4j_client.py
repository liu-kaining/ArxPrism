"""
Neo4j Database Client

使用 neo4j.AsyncGraphDatabase 实现异步图数据库客户端。
所有写入操作必须使用 MERGE 语句保证幂等性，必须使用参数化查询防注入。

防线2: 实体归一化算法 - 解决 Deep-Log / DeepLog / deeplog 节点对齐问题
防线4: 实验对比边 [:IMPROVES_UPON] 写入 discovered_at；技术血脉 [:EVOLVED_FROM] 写入 reason / discovered_at

Reference: ARCHITECTURE.md Section 3, TECH_DESIGN.md Section 1,
CODE_REVIEW.md Section 1
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, CypherSyntaxError

from src.core.config import settings
from src.models.schemas import PaperExtractionResponse

logger = logging.getLogger(__name__)


def _method_core_architecture(node: Any) -> str:
    """从 Neo4j Method 节点读取 core_architecture（字符串）。"""
    if node is None:
        return ""
    try:
        v = node.get("core_architecture")
    except Exception:
        v = None
    if v is None:
        return ""
    return str(v).strip()


# 向量检索（与 text-embedding-3-small dimensions=1536 一致）
_PAPER_VECTOR_INDEX = "paper_embedding"
# 绝对下限：过低会导致「搜一个词几乎返回全库」（同类论文向量仍较接近）
_VECTOR_MIN_SCORE = 0.42
# 相对下限：保留得分不低于「本轮第一名 × 该系数」的论文，压低弱相关尾巴
_VECTOR_RELATIVE_FLOOR = 0.88
_VECTOR_SCAN_CAP = 3000
_EMBEDDING_DIM = 1536
_QUERY_VEC_CACHE: Dict[str, tuple[List[float], float]] = {}
_QUERY_VEC_TTL_SEC = 300.0
_QUERY_VEC_CACHE_MAX = 256

# 管理端 JSON 快照：与 MERGE 键一致，便于跨库迁移
_SNAPSHOT_FORMAT = "arxprism-neo4j-snapshot"
_SNAPSHOT_VERSION = 1

_LABEL_PRIORITY = (
    "Paper",
    "Method",
    "Task",
    "Author",
    "Dataset",
    # "Innovation", # Removed
    # "Limitation", # Removed
    "Metric",
)

_LABEL_MERGE_KEYS: Dict[str, Tuple[str, ...]] = {
    "Paper": ("arxiv_id",),
    "Author": ("name",),
    "Task": ("name",),
    "Method": ("name",),
    "Dataset": ("name",),
    # "Innovation": ("content",), # Removed
    # "Limitation": ("content",), # Removed
    "Metric": ("name",),
}

_REL_TYPES: Dict[str, Tuple[str, Tuple[str, ...], str, Tuple[str, ...]]] = {
    "WRITTEN_BY": ("Paper", ("arxiv_id",), "Author", ("name",)),
    "ADDRESSES": ("Paper", ("arxiv_id",), "Task", ("name",)),
    "PROPOSES": ("Paper", ("arxiv_id",), "Method", ("name",)),
    "APPLIED_TO": ("Method", ("name",), "Task", ("name",)),
    "EVALUATED_ON": ("Paper", ("arxiv_id",), "Dataset", ("name",)),
    "IMPROVES_UPON": ("Method", ("name",), "Method", ("name",)),
    "EVOLVED_FROM": ("Method", ("name",), "Method", ("name",)),
    # "HAS_INNOVATION": ("Paper", ("arxiv_id",), "Innovation", ("content",)), # Removed
    # "HAS_LIMITATION": ("Paper", ("arxiv_id",), "Limitation", ("content",)), # Removed
    "MEASURES": ("Paper", ("arxiv_id",), "Metric", ("name",)),
}


def _jsonify_neo4j_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        return [_jsonify_neo4j_value(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _jsonify_neo4j_value(v) for k, v in value.items()}
    if hasattr(value, "iso_format"):
        try:
            return value.iso_format()
        except Exception:
            return str(value)
    return str(value)


def _jsonify_node_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _jsonify_neo4j_value(v) for k, v in dict(props).items()}


def _primary_label(labels: List[str]) -> Optional[str]:
    s = set(labels or [])
    for cand in _LABEL_PRIORITY:
        if cand in s:
            return cand
    return None


def _endpoint_from_node(labels: List[str], props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lbl = _primary_label(labels)
    if not lbl or lbl not in _LABEL_MERGE_KEYS:
        return None
    keys = _LABEL_MERGE_KEYS[lbl]
    match: Dict[str, Any] = {}
    for k in keys:
        if k not in props:
            return None
        match[k] = _jsonify_neo4j_value(props[k])
    return {"label": lbl, "match": match}


# =============================================================================
# 防线2: 极进实体归一化算法
# =============================================================================

# 无意义的常见后缀词（这些词会干扰实体对齐）
_ENTITY_SUFFIX_PATTERNS = [
    r'\s+model$',
    r'\s+framework$',
    r'\s+algorithm$',
    r'\s+approach$',
    r'\s+method$',
    r'\s+technique$',
    r'\s+system$',
    r'\s+network$',
    r'\s+architecture$',
    r'\s+scheme$',
    r'\s+protocol$',
    r'\s+strategy$',
    r'\s+optimization$',
    r'\s+learning$',
]


def _normalize_name(name: str) -> str:
    """
    归一化实体名称: 用于 Neo4j MERGE 的唯一合并键。

    防线2实现:
    1. 转小写 + 去首尾空格
    2. 去除常见无意义后缀 (model, framework, algorithm, approach, method 等)
    3. 剔除所有非字母和数字的特殊字符

    Example:
        "Deep-Log Model" -> "deeplog" (去后缀model，去连字符)
        "DeepLog model" -> "deeplog" (去后缀model)
        "DeepLog-model" -> "deeplogmodel" (无后缀，去连字符)
        "LSTM-N" -> "lstmn" (去连字符)

    Returns:
        归一化后的名称（全小写、无特殊字符）作为 MERGE 键
    """
    if not name or not isinstance(name, str):
        return ""

    # Step 1: 转小写 + 去首尾空格
    normalized = name.strip().lower()

    if not normalized:
        return ""

    # Step 2: 去除常见无意义后缀
    for pattern in _ENTITY_SUFFIX_PATTERNS:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

    # Step 3: 剔除所有非字母和数字的特殊字符
    normalized = re.sub(r'[^a-z0-9]', '', normalized)

    return normalized


def _is_placeholder_entity_name(raw: Optional[str]) -> bool:
    """
    模型占位输出：大小写/下划线/空格变体均视为无效，禁止 MERGE 成归一化后的 junk 键
    （例如 \"Not_Mentioned\" -> notmentioned）。
    """
    if raw is None or not isinstance(raw, str):
        return True
    compact = "".join(c for c in raw.lower() if c.isalnum())
    return compact in (
        "",
        "notmentioned",
        "na",
        "none",
        "unknown",
        "null",
        "tbd",
        "undefined",
    )


class Neo4jClient:
    """异步图数据库客户端 (单例模式)."""

    _instance: Optional["Neo4jClient"] = None
    _driver: Optional[AsyncDriver] = None

    def __new__(cls) -> "Neo4jClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """初始化异步 Neo4j 驱动."""
        if self._driver is None:
            logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            await self._ensure_paper_embedding_vector_index()
            await self._ensure_core_uniqueness_constraints()
            logger.info("Neo4j driver initialized successfully")

    async def _ensure_paper_embedding_vector_index(self) -> None:
        """创建 Paper.embedding 向量索引（Neo4j 5.x）；失败仅记录告警。"""
        if self._driver is None:
            return
        cypher = """
        CREATE VECTOR INDEX paper_embedding IF NOT EXISTS
        FOR (p:Paper)
        ON (p.embedding)
        OPTIONS {indexConfig: {
          `vector.dimensions`: 1536,
          `vector.similarity_function`: 'cosine'
        }}
        """
        try:
            async with self._driver.session() as session:
                await session.run(cypher)
            logger.info("Neo4j vector index %r ensured", _PAPER_VECTOR_INDEX)
        except Exception as e:
            logger.warning(
                "Could not create vector index %r (Neo4j 5.11+ required): %s",
                _PAPER_VECTOR_INDEX,
                e,
            )

    async def _ensure_core_uniqueness_constraints(self) -> None:
        """MERGE 键唯一约束：降低高并发下重复节点与死锁风险（Neo4j 5+）。"""
        if self._driver is None:
            return
        statements = [
            (
                "method_name_unique",
                "CREATE CONSTRAINT method_name_unique IF NOT EXISTS "
                "FOR (m:Method) REQUIRE m.name IS UNIQUE",
            ),
            (
                "paper_arxiv_id_unique",
                "CREATE CONSTRAINT paper_arxiv_id_unique IF NOT EXISTS "
                "FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE",
            ),
            (
                "task_name_unique",
                "CREATE CONSTRAINT task_name_unique IF NOT EXISTS "
                "FOR (t:Task) REQUIRE t.name IS UNIQUE",
            ),
        ]
        for name, cypher in statements:
            try:
                async with self._driver.session() as session:
                    await session.run(cypher)
                logger.info("Neo4j uniqueness constraint %r ensured", name)
            except Exception as e:
                err = str(e).lower()
                if (
                    "already exists" in err
                    or "equivalent" in err
                    or "there already is" in err
                ):
                    logger.debug("Neo4j constraint %r skipped (already present): %s", name, e)
                else:
                    logger.warning(
                        "Neo4j constraint %r could not be created: %s", name, e
                    )

    async def close(self) -> None:
        """关闭 Neo4j 驱动连接."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")

    async def verify_connectivity(self) -> bool:
        """验证 Neo4j 连接性."""
        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 AS verify")
                await result.single()
            logger.info("Neo4j connectivity verified")
            return True
        except ServiceUnavailable as e:
            logger.error(f"Neo4j connectivity failed: {e}")
            return False

    async def upsert_paper_graph(self, data: PaperExtractionResponse) -> bool:
        """
        将论文萃取数据写入 Neo4j 图谱.

        使用 MERGE 语句保证幂等性，所有查询使用参数化查询防注入。

        防线4: [:IMPROVES_UPON] 边写入 published_date 用于环路检测

        Args:
            data: 经过 Pydantic 校验的 PaperExtractionResponse

        Returns:
            True if successful, False otherwise
        """
        paper_id = data.paper_id
        logger.info(f"Upserting paper graph for: {paper_id}")

        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                await session.execute_write(
                    self._upsert_transaction,
                    data
                )
            logger.info(f"Successfully upserted paper {paper_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert paper {paper_id}: {e}")
            return False

    async def _upsert_transaction(
        self,
        tx: Any,
        data: PaperExtractionResponse
    ) -> None:
        """
        在事务中执行论文图谱写入.

        使用 MERGE (禁止 CREATE) + 参数化查询 + 名称归一化。
        防线2: Method/Dataset 等使用 _normalize_name()；Author 仅 strip+lower。
        防线4: [:IMPROVES_UPON] 边写入 discovered_at、dataset、metrics_improvement
        """
        paper_id = data.paper_id
        extraction = data.extraction_data
        published_date = data.publication_date
        core_problem = (
            extraction.core_problem if extraction is not None else "NOT_MENTIONED"
        )
        reasoning_process = (
            (extraction.reasoning_process or "") if extraction is not None else ""
        )
        summary_text = data.summary or ""
        summary_zh_text = (data.summary_zh or "").strip()
        emb = data.embedding
        has_embedding = bool(
            emb and isinstance(emb, list) and len(emb) == _EMBEDDING_DIM
        )
        embedding_param = emb if has_embedding else []

        # =========================================================================
        # 1. MERGE Paper 节点 (按 arxiv_id 唯一合并)
        # =========================================================================
        logger.debug(f"MERGing Paper node: {paper_id}")
        await tx.run(
            """
            MERGE (p:Paper {arxiv_id: $arxiv_id})
            ON CREATE SET
                p.title = $title,
                p.published_date = $published_date,
                p.url = $url,
                p.core_problem = $core_problem,
                p.summary = $summary,
                p.summary_zh = $summary_zh,
                p.reasoning_process = $reasoning_process,
                p.embedding = CASE WHEN $has_embedding THEN $embedding END
            ON MATCH SET
                p.title = $title,
                p.published_date = $published_date,
                p.url = $url,
                p.core_problem = $core_problem,
                p.summary = $summary,
                p.summary_zh = $summary_zh,
                p.reasoning_process = $reasoning_process,
                p.embedding = CASE WHEN $has_embedding THEN $embedding ELSE p.embedding END
            """,
            arxiv_id=paper_id,
            title=data.title,
            published_date=published_date,
            url=f"https://arxiv.org/abs/{paper_id}",
            core_problem=core_problem,
            summary=summary_text,
            summary_zh=summary_zh_text,
            reasoning_process=reasoning_process,
            has_embedding=has_embedding,
            embedding=embedding_param,
        )

        # =========================================================================
        # 2. MERGE Author 节点和 WRITTEN_BY 关系
        # 作者名仅 strip + lower，不用 _normalize_name，避免 "Y. Li" 与 "Ying Li" 被合并
        # =========================================================================
        for author_name in data.authors:
            if not isinstance(author_name, str) or not author_name.strip():
                continue
            normalized_name = author_name.strip().lower()
            logger.debug(f"MERGing Author: {author_name} -> key: {normalized_name}")
            await tx.run(
                """
                MERGE (a:Author {name: $name})
                ON CREATE SET a.original_name = $original_name
                ON MATCH SET a.original_name = $original_name
                WITH a
                MATCH (p:Paper {arxiv_id: $arxiv_id})
                MERGE (p)-[:WRITTEN_BY]->(a)
                """,
                name=normalized_name,
                original_name=author_name,
                arxiv_id=paper_id
            )

        if extraction is None:
            logger.info(
                f"Paper {paper_id}: extraction_data is None; "
                "skipped Method/Dataset/EVOLVED_FROM edges"
            )
            return

        normalized_task: Optional[str] = None
        task_name = extraction.task_name
        if task_name and not _is_placeholder_entity_name(task_name):
            normalized_task = _normalize_name(task_name)
            if normalized_task:
                logger.debug(f"MERGing Task: {task_name} -> normalized: {normalized_task}")
                await tx.run(
                    """
                    MERGE (t:Task {name: $task_name})
                    ON CREATE SET t.original_name = $original_task_name
                    ON MATCH SET t.original_name = $original_task_name
                    WITH t
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    MERGE (p)-[:ADDRESSES]->(t)
                    """,
                    task_name=normalized_task,
                    original_task_name=task_name,
                    arxiv_id=paper_id,
                )
            else:
                logger.warning(f"Skipping empty normalized task_name: {task_name}")

        # =========================================================================
        # 3. MERGE Method 节点和 PROPOSES 关系
        # =========================================================================
        method_name = extraction.proposed_method.name
        normalized_method: Optional[str] = None  # 初始化，避免未定义

        if method_name and not _is_placeholder_entity_name(method_name):
            normalized_method = _normalize_name(method_name)

            # 跳过空归一化结果
            if not normalized_method:
                logger.warning(f"Skipping empty normalized method name: {method_name}")
            else:
                logger.debug(f"MERGing Method: {method_name} -> normalized: {normalized_method}")
                await tx.run(
                    """
                    MERGE (m:Method {name: $name})
                    ON CREATE SET
                        m.description = $description,
                        m.original_name = $original_name,
                        m.core_architecture = $core_architecture,
                        m.key_innovations = $key_innovations,
                        m.limitations = $limitations
                    ON MATCH SET
                        m.description = $description,
                        m.original_name = $original_name,
                        m.core_architecture = $core_architecture,
                        m.key_innovations = $key_innovations,
                        m.limitations = $limitations
                    WITH m
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    MERGE (p)-[:PROPOSES]->(m)
                    """,
                    name=normalized_method,
                    original_name=method_name,
                    description=extraction.proposed_method.description,
                    core_architecture=extraction.proposed_method.core_architecture,
                    key_innovations=extraction.proposed_method.key_innovations,
                    limitations=extraction.proposed_method.limitations,
                    arxiv_id=paper_id
                )

                if normalized_task:
                    await tx.run(
                        """
                        MATCH (m:Method {name: $method_name})
                        MATCH (t:Task {name: $task_name})
                        MERGE (m)-[:APPLIED_TO]->(t)
                        """,
                        method_name=normalized_method,
                        task_name=normalized_task,
                    )

                # =========================================================================
                # 3b. evolution_lineages → 祖先 Method + (主方法)-[:EVOLVED_FROM]->(祖先)
                # =========================================================================
                for lin in extraction.knowledge_graph_nodes.evolution_lineages:
                    ancestor_raw = (lin.ancestor_method or "").strip()
                    if not ancestor_raw or ancestor_raw.upper() == "NOT_MENTIONED":
                        continue
                    normalized_ancestor = _normalize_name(ancestor_raw)
                    if not normalized_ancestor:
                        logger.warning(
                            "Skipping empty normalized ancestor_method: %s", ancestor_raw
                        )
                        continue
                    if normalized_ancestor == normalized_method:
                        logger.debug(
                            "Skipping EVOLVED_FROM self-loop: %s", normalized_method
                        )
                        continue
                    reason_text = (lin.evolution_reason or "").strip()
                    logger.debug(
                        "MERGing EVOLVED_FROM: %s -> %s",
                        method_name,
                        ancestor_raw,
                    )
                    await tx.run(
                        """
                        MERGE (child:Method {name: $child_name})
                        MERGE (anc:Method {name: $ancestor_name})
                        ON CREATE SET
                            anc.original_name = $ancestor_original_name,
                            anc.first_appeared = $published_date
                        ON MATCH SET
                            anc.original_name = $ancestor_original_name,
                            anc.first_appeared = CASE
                                WHEN $published_date < coalesce(anc.first_appeared, $published_date)
                                THEN $published_date
                                ELSE anc.first_appeared
                            END
                        MERGE (child)-[r:EVOLVED_FROM]->(anc)
                        SET r.reason = $evolution_reason,
                            r.discovered_at = $published_date
                        """,
                        child_name=normalized_method,
                        ancestor_name=normalized_ancestor,
                        ancestor_original_name=ancestor_raw,
                        published_date=published_date,
                        evolution_reason=reason_text,
                    )

                # =========================================================================
                # 4–6. comparisons → Dataset + EVALUATED_ON、基线 Method + [:IMPROVES_UPON]
                #
                # 每条对比在 IMPROVES_UPON 边上写入 dataset / metrics_improvement / discovered_at
                # （指标不再单独建 Metric 节点）。
                # =========================================================================
                for comp in extraction.knowledge_graph_nodes.comparisons:
                    baseline_raw = (comp.baseline_method or "").strip()
                    dataset_raw = (comp.dataset or "").strip()
                    metrics_text = (comp.metrics_improvement or "").strip()

                    if (
                        not baseline_raw
                        or baseline_raw.upper() == "NOT_MENTIONED"
                    ):
                        continue

                    normalized_baseline = _normalize_name(baseline_raw)
                    if not normalized_baseline:
                        logger.warning(
                            "Skipping empty normalized baseline: %s", baseline_raw
                        )
                        continue

                    if (
                        dataset_raw
                        and dataset_raw.upper() != "NOT_MENTIONED"
                    ):
                        normalized_dataset = _normalize_name(dataset_raw)
                        if normalized_dataset:
                            logger.debug(
                                "MERGing Dataset: %s -> normalized: %s",
                                dataset_raw,
                                normalized_dataset,
                            )
                            await tx.run(
                                """
                                MERGE (d:Dataset {name: $name})
                                ON CREATE SET d.original_name = $original_name
                                ON MATCH SET d.original_name = $original_name
                                WITH d
                                MATCH (p:Paper {arxiv_id: $arxiv_id})
                                MERGE (p)-[:EVALUATED_ON]->(d)
                                """,
                                name=normalized_dataset,
                                original_name=dataset_raw,
                                arxiv_id=paper_id,
                            )
                        else:
                            logger.warning(
                                "Skipping empty normalized dataset: %s", dataset_raw
                            )

                    logger.debug(
                        "MERGing IMPROVES_UPON: %s -> %s (normalized baseline: %s)",
                        method_name,
                        baseline_raw,
                        normalized_baseline,
                    )
                    await tx.run(
                        """
                        MERGE (improved:Method {name: $method_name})
                        MERGE (baseline:Method {name: $baseline_name})
                        ON CREATE SET
                            baseline.original_name = $baseline_original_name,
                            baseline.first_appeared = $published_date
                        ON MATCH SET
                            baseline.original_name = $baseline_original_name,
                            baseline.first_appeared = CASE
                                WHEN $published_date < baseline.first_appeared
                                THEN $published_date
                                ELSE baseline.first_appeared
                            END
                        MERGE (improved)-[r:IMPROVES_UPON]->(baseline)
                        SET r.dataset = $dataset,
                            r.metrics_improvement = $metrics_improvement,
                            r.discovered_at = $published_date
                        """,
                        method_name=normalized_method,
                        baseline_name=normalized_baseline,
                        baseline_original_name=baseline_raw,
                        published_date=published_date,
                        dataset=dataset_raw,
                        metrics_improvement=metrics_text,
                    )

        logger.debug(f"Completed upsert for paper: {paper_id}")

    async def check_paper_exists(self, arxiv_id: str) -> bool:
        """
        检查论文是否已存在于数据库.

        Args:
            arxiv_id: arXiv ID

        Returns:
            True if exists, False otherwise
        """
        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run(
                    "MATCH (p:Paper {arxiv_id: $arxiv_id}) RETURN p",
                    arxiv_id=arxiv_id
                )
                record = await result.single()
                exists = record is not None
            logger.debug(f"Paper {arxiv_id} exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking paper existence: {e}")
            return False

    async def get_paper_graph(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取论文的完整图谱.

        GET /api/v1/graph/paper/{arxiv_id}
        返回论文的所有第一层相邻节点。

        Args:
            arxiv_id: arXiv ID

        Returns:
            Dict with 'nodes' and 'relationships' lists
        """
        logger.info(f"Fetching paper graph for: {arxiv_id}")

        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    OPTIONAL MATCH (p)-[r]-(connected)
                    RETURN p, r, connected
                    """,
                    arxiv_id=arxiv_id
                )

                nodes: List[Dict[str, Any]] = []
                relationships: List[Dict[str, Any]] = []
                seen_nodes: set = set()

                async for record in result:
                    paper = record["p"]
                    rel = record["r"]
                    connected = record["connected"]

                    # Add paper node
                    if paper and paper.element_id not in seen_nodes:
                        seen_nodes.add(paper.element_id)
                        nodes.append({
                            "id": paper["arxiv_id"],
                            "labels": list(paper.labels),
                            "properties": dict(paper)
                        })

                    # Add connected node and relationship
                    if connected and rel:
                        if connected.element_id not in seen_nodes:
                            seen_nodes.add(connected.element_id)
                            labels = list(connected.labels) if hasattr(connected, 'labels') else []
                            nodes.append({
                                "id": connected.get("name") or connected.get("arxiv_id") or connected.element_id,
                                "labels": labels,
                                "properties": dict(connected)
                            })

                        start_id = paper["arxiv_id"] if paper else None
                        end_id = connected.get("name") or connected.get("arxiv_id") or connected.element_id

                        if start_id and end_id:
                            relationships.append({
                                "source_id": start_id,
                                "target_id": end_id,
                                "type": rel.type
                            })

                logger.info(f"Retrieved {len(nodes)} nodes and {len(relationships)} relationships")
                return {"nodes": nodes, "relationships": relationships}

        except Exception as e:
            logger.error(f"Failed to fetch paper graph: {e}")
            return {"nodes": [], "relationships": []}

    async def get_evolution_tree(self, method_name: str) -> Dict[str, Any]:
        """
        获取方法的技术进化树.

        GET /api/v1/graph/evolution?method_name={name}
        沿 [:EVOLVED_FROM] 向上追溯 3 层祖先（子方法继承自祖先），向下 3 层后代。

        解析顺序：1) 归一化键 m.name；2) 展示名 m.original_name（与论文列表/详情一致）。
        曾用 UNWIND 空列表会丢掉整行，导致「索引里有方法却查不出树」；已改为单次 RETURN。
        """
        raw = (method_name or "").strip()
        normalized_name = _normalize_name(raw)
        logger.info(
            "Fetching evolution tree raw=%r normalized=%r", raw, normalized_name
        )

        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                mres = await session.run(
                    """
                    MATCH (m:Method)
                    WHERE ($norm <> '' AND m.name = $norm)
                       OR ($raw <> '' AND toLower(trim(coalesce(m.original_name, '')))
                            = toLower(trim($raw)))
                    RETURN m AS target
                    ORDER BY
                      CASE WHEN $norm <> '' AND m.name = $norm THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    norm=normalized_name or "",
                    raw=raw,
                )
                mrow = await mres.single()
                if not mrow or mrow.get("target") is None:
                    logger.info("Evolution tree: no Method node for %r", raw)
                    return {"nodes": [], "links": []}

                target_key = mrow["target"]["name"]
                if not target_key:
                    return {"nodes": [], "links": []}

                target = mrow["target"]

                ares = await session.run(
                    """
                    MATCH (t:Method {name: $tk})
                    MATCH p = (t)-[:EVOLVED_FROM*1..3]->(a:Method)
                    WHERE a <> t
                    WITH a, min(length(p)) AS depth
                    RETURN a, depth
                    ORDER BY depth, a.name
                    """,
                    tk=target_key,
                )
                ancestor_rows = await ares.data()

                dres = await session.run(
                    """
                    MATCH (t:Method {name: $tk})
                    MATCH p = (t)<-[:EVOLVED_FROM*1..3]-(d:Method)
                    WHERE d <> t
                    WITH d, min(length(p)) AS depth
                    RETURN d, depth
                    ORDER BY depth, d.name
                    """,
                    tk=target_key,
                )
                descendant_rows = await dres.data()

                nodes: List[Dict[str, Any]] = []
                links: List[Dict[str, Any]] = []
                seen_methods: set = set()

                if target:
                    nodes.append(
                        {
                            "id": target["name"],
                            "name": target.get("original_name") or target["name"],
                            "generation": 0,
                            "core_architecture": _method_core_architecture(target),
                        }
                    )
                    seen_methods.add(target["name"])

                # (child)-[:EVOLVED_FROM]->(ancestor)；generation = ±最短路径边数
                for row in ancestor_rows:
                    ancestor = row.get("a")
                    depth = row.get("depth")
                    if ancestor is None or depth is None:
                        continue
                    if ancestor["name"] in seen_methods:
                        continue
                    d_int = int(depth)
                    nodes.append(
                        {
                            "id": ancestor["name"],
                            "name": ancestor.get("original_name")
                            or ancestor["name"],
                            "generation": -d_int,
                            "core_architecture": _method_core_architecture(ancestor),
                        }
                    )
                    seen_methods.add(ancestor["name"])
                    links.append(
                        {
                            "source": target["name"],
                            "target": ancestor["name"],
                            "relationshipType": "EVOLVED_FROM",
                        }
                    )

                for row in descendant_rows:
                    descendant = row.get("d")
                    depth = row.get("depth")
                    if descendant is None or depth is None:
                        continue
                    if descendant["name"] in seen_methods:
                        continue
                    d_int = int(depth)
                    nodes.append(
                        {
                            "id": descendant["name"],
                            "name": descendant.get("original_name")
                            or descendant["name"],
                            "generation": d_int,
                            "core_architecture": _method_core_architecture(descendant),
                        }
                    )
                    seen_methods.add(descendant["name"])
                    links.append(
                        {
                            "source": descendant["name"],
                            "target": target["name"],
                            "relationshipType": "EVOLVED_FROM",
                        }
                    )

                id_list = list(seen_methods)
                if id_list:
                    res_edges = await session.run(
                        """
                        MATCH (s:Method)-[r:EVOLVED_FROM]->(t:Method)
                        WHERE s.name IN $ids AND t.name IN $ids
                        RETURN s.name AS source, t.name AS target,
                               coalesce(r.reason, '') AS reason,
                               coalesce(toString(r.discovered_at), '') AS discovered_at,
                               coalesce(r.dataset, '') AS dataset,
                               coalesce(r.metrics_improvement, '') AS metrics_improvement
                        """,
                        ids=id_list,
                    )
                    edge_meta: Dict[tuple, Dict[str, str]] = {}
                    for edge_rec in await res_edges.data():
                        key = (edge_rec["source"], edge_rec["target"])
                        if key not in edge_meta:
                            edge_meta[key] = {
                                "reason": edge_rec.get("reason") or "",
                                "discovered_at": edge_rec.get("discovered_at") or "",
                                "dataset": edge_rec.get("dataset") or "",
                                "metrics_improvement": edge_rec.get(
                                    "metrics_improvement"
                                )
                                or "",
                            }
                    for link in links:
                        meta = edge_meta.get((link["source"], link["target"]))
                        if meta:
                            link["reason"] = meta["reason"]
                            link["discovered_at"] = meta["discovered_at"]
                            link["dataset"] = meta["dataset"]
                            link["metrics_improvement"] = meta["metrics_improvement"]

                logger.info(
                    "Evolution tree: %s nodes, %s links", len(nodes), len(links)
                )
                return {"nodes": nodes, "links": links}

        except Exception as e:
            logger.error(f"Failed to fetch evolution tree: {e}")
            return {"nodes": [], "links": []}

    async def list_evolution_methods(self) -> Dict[str, Any]:
        """
        供前端「发现」进化树入口：
        - with_evolution: 至少参与一条 EVOLVED_FROM 的 Method（推荐点击）
        - other_methods: 图中有节点、但当前无任何 EVOLVED_FROM 关联的方法（仍可尝试以根查询）
        """
        if self._driver is None:
            await self.connect()
        if self._driver is None:
            return {"with_evolution": [], "other_methods": []}

        with_evolution: List[Dict[str, Any]] = []
        other_methods: List[Dict[str, Any]] = []

        try:
            async with self._driver.session() as session:
                res1 = await session.run(
                    """
                    MATCH (m:Method)-[r:EVOLVED_FROM]-(:Method)
                    WITH m, count(r) AS edge_count
                    RETURN m.name AS name_key,
                           coalesce(m.original_name, m.name) AS label,
                           edge_count
                    ORDER BY toLower(label)
                    LIMIT 400
                    """
                )
                for row in await res1.data():
                    with_evolution.append(
                        {
                            "name_key": row["name_key"],
                            "label": row["label"] or row["name_key"],
                            "edge_count": int(row["edge_count"] or 0),
                        }
                    )

                res2 = await session.run(
                    """
                    MATCH (m:Method)
                    WHERE NOT (m)-[:EVOLVED_FROM]-(:Method)
                    RETURN m.name AS name_key,
                           coalesce(m.original_name, m.name) AS label
                    ORDER BY toLower(label)
                    LIMIT 120
                    """
                )
                for row in await res2.data():
                    other_methods.append(
                        {
                            "name_key": row["name_key"],
                            "label": row["label"] or row["name_key"],
                        }
                    )

            logger.info(
                "Evolution method index: %s with edges, %s without",
                len(with_evolution),
                len(other_methods),
            )
        except Exception as e:
            logger.error(f"Failed to list evolution methods: {e}")

        return {"with_evolution": with_evolution, "other_methods": other_methods}

    @staticmethod
    def _vector_scan_topk(offset: int, limit: int) -> int:
        return min(_VECTOR_SCAN_CAP, max(100, offset + limit + 200))

    @staticmethod
    def _normalize_comparison_rows(raw: Any) -> List[Dict[str, Any]]:
        if not raw:
            return []
        out: List[Dict[str, Any]] = []
        for item in raw:
            if not item or not isinstance(item, dict):
                continue
            b = item.get("baseline")
            if not b:
                continue
            out.append(
                {
                    "baseline": b,
                    "dataset": item.get("dataset") or "",
                    "metrics_improvement": item.get("metrics_improvement") or "",
                }
            )
        return out

    async def _resolve_query_embedding(self, q_raw: str) -> Optional[List[float]]:
        key = (q_raw or "").strip().lower()
        if not key:
            return None
        if len(_QUERY_VEC_CACHE) >= _QUERY_VEC_CACHE_MAX:
            _QUERY_VEC_CACHE.clear()
        now = time.monotonic()
        hit = _QUERY_VEC_CACHE.get(key)
        if hit is not None:
            vec, ts = hit
            if now - ts <= _QUERY_VEC_TTL_SEC:
                return vec
            del _QUERY_VEC_CACHE[key]

        from src.services.llm_extractor import get_llm_extractor

        vec = await get_llm_extractor().generate_embedding(q_raw)
        if vec and len(vec) == _EMBEDDING_DIM:
            _QUERY_VEC_CACHE[key] = (vec, now)
            return vec
        return None

    @staticmethod
    def _use_semantic_vector(
        q_raw: str, search_mode: str, query_vector: Optional[List[float]]
    ) -> bool:
        if not q_raw.strip():
            return False
        if (search_mode or "semantic").strip().lower() == "keyword":
            return False
        return query_vector is not None

    async def search_papers(
        self,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
        task_topic: str = "",
        search_mode: str = "semantic",
    ) -> List[Dict[str, Any]]:
        """
        Hybrid 检索：语义模式在向量可用时用向量索引 + 相对阈值压尾巴；keyword 强制标题/摘要/方法 CONTAINS。
        query 为空：按时间倒序浏览（仍受 task_topic 约束）。
        """
        q_raw = (query or "").strip()
        q_lower = q_raw.lower()
        tt = (task_topic or "").strip()
        if self._driver is None:
            await self.connect()

        expand_graph = """
        OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:WRITTEN_BY]->(a:Author)
        OPTIONAL MATCH (p)-[:EVALUATED_ON]->(d:Dataset)
        OPTIONAL MATCH (p)-[:MEASURES]->(mt:Metric)
        OPTIONAL MATCH (m)-[imp:IMPROVES_UPON]->(baseline:Method)
        WITH p,
             collect(DISTINCT coalesce(m.original_name, m.name)) AS methods,
             collect(DISTINCT coalesce(a.original_name, a.name)) AS authors,
             collect(DISTINCT coalesce(d.original_name, d.name)) AS datasets,
             collect(DISTINCT coalesce(mt.original_name, mt.name)) AS metrics,
             collect(DISTINCT coalesce(t.original_name, t.name)) AS tasks,
             collect(DISTINCT CASE WHEN baseline IS NOT NULL THEN {
               baseline: coalesce(baseline.original_name, baseline.name),
               dataset: imp.dataset,
               metrics_improvement: imp.metrics_improvement
             } END) AS comparison_rows
        RETURN
          p.arxiv_id AS arxiv_id,
          p.title AS title,
          p.published_date AS published_date,
          p.core_problem AS core_problem,
          methods[0] AS proposed_method,
          tasks[0] AS task_name,
          authors AS authors,
          datasets AS datasets,
          metrics AS metrics,
          baselines AS baselines,
          comparison_rows AS comparison_rows
        """

        try:
            async with self._driver.session() as session:
                query_vector: Optional[List[float]] = None
                if q_raw:
                    query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = self._use_semantic_vector(q_raw, search_mode, query_vector)

                if use_vector:
                    assert query_vector is not None
                    topk = self._vector_scan_topk(offset, limit)
                    cypher = (
                        """
                    CALL db.index.vector.queryNodes($index_name, $topk, $query_vector)
                    YIELD node AS p, score
                    WHERE score >= $min_score
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, score, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p, score
                    ORDER BY score DESC
                    WITH collect({p: p, score: score}) AS rows
                    WITH rows, CASE WHEN size(rows) > 0 THEN rows[0].score ELSE 0.0 END AS top_score
                    UNWIND rows AS row
                    WITH row.p AS p, row.score AS score, top_score
                    WHERE top_score > 0
                      AND score >= top_score * $rel_floor
                      AND score >= $min_score
                    WITH DISTINCT p, score
                    ORDER BY score DESC
                    SKIP $offset
                    LIMIT $limit
                    WITH p
                    """
                        + expand_graph
                    )
                    result = await session.run(
                        cypher,
                        index_name=_PAPER_VECTOR_INDEX,
                        topk=topk,
                        query_vector=query_vector,
                        min_score=_VECTOR_MIN_SCORE,
                        rel_floor=_VECTOR_RELATIVE_FLOOR,
                        task_topic=tt,
                        offset=offset,
                        limit=limit,
                    )
                else:
                    cypher = (
                        """
                    MATCH (p:Paper)
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                    WITH p, t
                    WHERE $task_topic = "" OR coalesce(t.original_name, t.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                    OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
                    WITH p, collect(DISTINCT coalesce(m.original_name, m.name)) AS methods
                    WHERE $q = "" OR toLower(coalesce(p.title,"")) CONTAINS $q
                       OR toLower(coalesce(p.core_problem,"")) CONTAINS $q
                       OR any(x IN methods WHERE toLower(coalesce(x,"")) CONTAINS $q)
                    WITH DISTINCT p
                    """
                        + expand_graph
                        + """
                    ORDER BY p.published_date DESC
                    SKIP $offset
                    LIMIT $limit
                    """
                    )
                    result = await session.run(
                        cypher,
                        q=q_lower,
                        task_topic=tt,
                        offset=offset,
                        limit=limit,
                    )
                rows = await result.data()
            for row in rows:
                row["experiment_comparisons"] = self._normalize_comparison_rows(
                    row.pop("comparison_rows", None)
                )
            return rows
        except Exception as e:
            logger.error(f"Failed to search papers: {e}")
            return []

    async def count_search_papers(
        self,
        query: str = "",
        task_topic: str = "",
        search_mode: str = "semantic",
    ) -> int:
        """与 search_papers 相同过滤条件下的命中总数。"""
        q_raw = (query or "").strip()
        q_lower = q_raw.lower()
        tt = (task_topic or "").strip()
        if self._driver is None:
            await self.connect()

        try:
            async with self._driver.session() as session:
                query_vector: Optional[List[float]] = None
                if q_raw:
                    query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = self._use_semantic_vector(q_raw, search_mode, query_vector)

                if use_vector:
                    assert query_vector is not None
                    topk = _VECTOR_SCAN_CAP
                    cypher = """
                    CALL db.index.vector.queryNodes($index_name, $topk, $query_vector)
                    YIELD node AS p, score
                    WHERE score >= $min_score
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, score, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p, score
                    ORDER BY score DESC
                    WITH collect({p: p, score: score}) AS rows
                    WITH rows, CASE WHEN size(rows) > 0 THEN rows[0].score ELSE 0.0 END AS top_score
                    UNWIND rows AS row
                    WITH row.p AS p, row.score AS score, top_score
                    WHERE top_score > 0
                      AND score >= top_score * $rel_floor
                      AND score >= $min_score
                    RETURN count(DISTINCT p) AS total
                    """
                    result = await session.run(
                        cypher,
                        index_name=_PAPER_VECTOR_INDEX,
                        topk=topk,
                        query_vector=query_vector,
                        min_score=_VECTOR_MIN_SCORE,
                        rel_floor=_VECTOR_RELATIVE_FLOOR,
                        task_topic=tt,
                    )
                else:
                    cypher = """
                    MATCH (p:Paper)
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                    WITH p, t
                    WHERE $task_topic = "" OR coalesce(t.original_name, t.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p
                    OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
                    WITH p, collect(DISTINCT coalesce(m.original_name, m.name)) AS methods
                    WHERE $q = "" OR toLower(coalesce(p.title,"")) CONTAINS $q
                       OR toLower(coalesce(p.core_problem,"")) CONTAINS $q
                       OR any(x IN methods WHERE toLower(coalesce(x,"")) CONTAINS $q)
                    RETURN count(DISTINCT p) AS total
                    """
                    result = await session.run(cypher, q=q_lower, task_topic=tt)
                row = await result.single()
                return int(row["total"]) if row else 0
        except Exception as e:
            logger.error(f"Failed to count search papers: {e}")
            return 0

    async def get_topic_breakdown_for_search(
        self,
        query: str = "",
        task_topic: str = "",
        search_mode: str = "semantic",
    ) -> List[Dict[str, Any]]:
        """
        与 search_papers 相同的论文集合上，按 ADDRESSES→Task 标签聚合篇数。
        """
        q_raw = (query or "").strip()
        q_lower = q_raw.lower()
        tt = (task_topic or "").strip()
        if self._driver is None:
            await self.connect()

        try:
            async with self._driver.session() as session:
                query_vector: Optional[List[float]] = None
                if q_raw:
                    query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = self._use_semantic_vector(q_raw, search_mode, query_vector)

                if use_vector:
                    assert query_vector is not None
                    topk = _VECTOR_SCAN_CAP
                    cypher = """
                    CALL db.index.vector.queryNodes($index_name, $topk, $query_vector)
                    YIELD node AS p, score
                    WHERE score >= $min_score
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, score, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p, score
                    ORDER BY score DESC
                    WITH collect({p: p, score: score}) AS rows
                    WITH rows, CASE WHEN size(rows) > 0 THEN rows[0].score ELSE 0.0 END AS top_score
                    UNWIND rows AS row
                    WITH row.p AS p, row.score AS score, top_score
                    WHERE top_score > 0
                      AND score >= top_score * $rel_floor
                      AND score >= $min_score
                    WITH DISTINCT p
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                    WITH coalesce(t.original_name, t.name, '(未标注主题)') AS topic, p
                    RETURN topic,
                           count(DISTINCT p) AS paper_count,
                           min(p.arxiv_id) AS sample_arxiv_id
                    ORDER BY paper_count DESC, topic ASC
                    """
                    result = await session.run(
                        cypher,
                        index_name=_PAPER_VECTOR_INDEX,
                        topk=topk,
                        query_vector=query_vector,
                        min_score=_VECTOR_MIN_SCORE,
                        rel_floor=_VECTOR_RELATIVE_FLOOR,
                        task_topic=tt,
                    )
                else:
                    cypher = """
                    MATCH (p:Paper)
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
                    WITH DISTINCT p
                    OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
                    WITH p, collect(DISTINCT coalesce(m.original_name, m.name)) AS methods
                    WHERE $q = "" OR toLower(coalesce(p.title,"")) CONTAINS $q
                       OR toLower(coalesce(p.core_problem,"")) CONTAINS $q
                       OR any(x IN methods WHERE toLower(coalesce(x,"")) CONTAINS $q)
                    WITH p
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                    WITH coalesce(t.original_name, t.name, '(未标注主题)') AS topic, p
                    RETURN topic,
                           count(DISTINCT p) AS paper_count,
                           min(p.arxiv_id) AS sample_arxiv_id
                    ORDER BY paper_count DESC, topic ASC
                    """
                    result = await session.run(cypher, q=q_lower, task_topic=tt)
                rows = await result.data()
            return [
                {
                    "topic": row["topic"],
                    "paper_count": int(row["paper_count"]),
                    "sample_arxiv_id": row.get("sample_arxiv_id"),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get topic breakdown for search: {e}")
            return []

    async def get_library_stats(
        self,
        search_query: str = "",
        topic_filter: str = "",
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        图库概览：论文数、作者规模、作者关系、按 Task 聚类。

        - 无 search_query 且无 topic_filter：by_topic 为全库分布，by_topic_scope=global
        - 否则：by_topic 仅在「与列表检索相同条件」命中的论文上聚合，by_topic_scope=filtered
        """
        if self._driver is None:
            await self.connect()

        sq = (search_query or "").strip()
        tf = (topic_filter or "").strip()
        use_filtered_topics = bool(sq) or bool(tf)

        out: Dict[str, Any] = {
            "paper_count": 0,
            "author_count": 0,
            "papers_with_authors": 0,
            "author_paper_links": 0,
            "by_topic": [],
            "by_topic_scope": "filtered" if use_filtered_topics else "global",
        }

        try:
            async with self._driver.session() as session:
                r1 = await session.run("MATCH (p:Paper) RETURN count(p) AS c")
                rec1 = await r1.single()
                out["paper_count"] = int(rec1["c"]) if rec1 and rec1.get("c") is not None else 0

                r2 = await session.run("MATCH (a:Author) RETURN count(a) AS c")
                rec2 = await r2.single()
                out["author_count"] = int(rec2["c"]) if rec2 and rec2.get("c") is not None else 0

                r3 = await session.run(
                    """
                    MATCH (p:Paper)-[:WRITTEN_BY]->(:Author)
                    RETURN count(DISTINCT p) AS c
                    """
                )
                rec3 = await r3.single()
                out["papers_with_authors"] = int(rec3["c"]) if rec3 and rec3.get("c") is not None else 0

                r4 = await session.run(
                    """
                    MATCH (:Paper)-[r:WRITTEN_BY]->(:Author)
                    RETURN count(r) AS c
                    """
                )
                rec4 = await r4.single()
                out["author_paper_links"] = int(rec4["c"]) if rec4 and rec4.get("c") is not None else 0

                if use_filtered_topics:
                    out["by_topic"] = await self.get_topic_breakdown_for_search(
                        query=sq, task_topic=tf, search_mode=search_mode
                    )
                else:
                    r5 = await session.run(
                        """
                        MATCH (p:Paper)
                        OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
                        WITH coalesce(t.original_name, t.name, '(未标注主题)') AS topic, p
                        RETURN topic,
                               count(DISTINCT p) AS paper_count,
                               min(p.arxiv_id) AS sample_arxiv_id
                        ORDER BY paper_count DESC
                        """
                    )
                    rows = await r5.data()
                    out["by_topic"] = [
                        {
                            "topic": row["topic"],
                            "paper_count": int(row["paper_count"]),
                            "sample_arxiv_id": row.get("sample_arxiv_id"),
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Failed to get library stats: {e}")

        return out

    async def get_paper_by_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 arXiv ID 获取论文详情.

        Args:
            arxiv_id: arXiv 论文 ID

        Returns:
            论文详情字典，包含基本信息和萃取数据
        """
        if self._driver is None:
            await self.connect()

        cypher = """
        MATCH (p:Paper {arxiv_id: $arxiv_id})
        OPTIONAL MATCH (p)-[:WRITTEN_BY]->(a:Author)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:EVALUATED_ON]->(d:Dataset)
        OPTIONAL MATCH (p)-[:MEASURES]->(mt:Metric)
        OPTIONAL MATCH (p)-[:ADDRESSES]->(t:Task)
        OPTIONAL MATCH (m)-[imp:IMPROVES_UPON]->(baseline:Method)

        RETURN
          p.arxiv_id AS arxiv_id,
          p.title AS title,
          p.published_date AS published_date,
          p.core_problem AS core_problem,
          p.summary AS summary,
          coalesce(p.summary_zh, '') AS summary_zh,
          coalesce(p.reasoning_process, '') AS reasoning_process,
          collect(DISTINCT coalesce(a.original_name, a.name)) AS authors,
          collect(DISTINCT {
            name: coalesce(m.original_name, m.name),
            name_key: m.name,
            description: m.description,
            core_architecture: m.core_architecture,
            key_innovations: m.key_innovations,
            limitations: m.limitations
          }) AS methods,
          collect(DISTINCT coalesce(baseline.original_name, baseline.name)) AS baselines,
          collect(DISTINCT coalesce(d.original_name, d.name)) AS datasets,
          collect(DISTINCT coalesce(mt.original_name, mt.name)) AS metrics,
          collect(DISTINCT coalesce(t.original_name, t.name)) AS tasks,
          collect(DISTINCT CASE WHEN baseline IS NOT NULL THEN {
            baseline: coalesce(baseline.original_name, baseline.name),
            dataset: imp.dataset,
            metrics_improvement: imp.metrics_improvement
          } END) AS comparison_rows
        """

        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, arxiv_id=arxiv_id)
                rows = await result.data()

            if not rows:
                return None

            row = rows[0]
            method_entries = [
                m
                for m in (row.get("methods") or [])
                if m and isinstance(m, dict) and m.get("name")
            ]
            method_names = [m["name"] for m in method_entries]
            proposed_method_key = (
                (method_entries[0].get("name_key") or "").strip()
                if method_entries
                else ""
            )
            # Extract new method properties
            proposed_method_description = (method_entries[0].get("description") or "") if method_entries else ""
            proposed_method_architecture = (method_entries[0].get("core_architecture") or "") if method_entries else ""
            proposed_method_innovations = (method_entries[0].get("key_innovations") or []) if method_entries else []
            proposed_method_limitations = (method_entries[0].get("limitations") or []) if method_entries else []

            author_list = [x for x in row.get("authors") or [] if x]
            experiment_comparisons = self._normalize_comparison_rows(
                row.get("comparison_rows")
            )

            return {
                "arxiv_id": row["arxiv_id"],
                "title": row["title"],
                "published_date": row.get("published_date", ""),
                "core_problem": row.get("core_problem", ""),
                "summary": row.get("summary", ""),
                "summary_zh": row.get("summary_zh") or "",
                "reasoning_process": row.get("reasoning_process") or "",
                "authors": author_list,
                "proposed_method": method_names[0] if method_names else "",
                "proposed_method_name_key": proposed_method_key,
                "proposed_method_description": proposed_method_description,
                "proposed_method_architecture": proposed_method_architecture,
                "proposed_method_innovations": proposed_method_innovations,
                "proposed_method_limitations": proposed_method_limitations,
                "innovations": list(proposed_method_innovations),
                "limitations": list(proposed_method_limitations),
                "baselines": [b for b in row["baselines"] if b],
                "datasets": [d for d in row["datasets"] if d],
                "metrics": [m for m in row["metrics"] if m],
                "tasks": [t for t in row["tasks"] if t],
                "experiment_comparisons": experiment_comparisons,
            }

        except Exception as e:
            logger.error(f"Failed to get paper by id: {e}")
            return None

    async def get_all_method_names(self) -> List[str]:
        """返回库中 Method.name 列表（最多 500，避免单次 Token 过大）。"""
        if self._driver is None:
            await self.connect()
        cypher = """
        MATCH (m:Method)
        RETURN m.name AS name
        ORDER BY name ASC
        LIMIT 500
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher)
                rows = await result.data()
            names = [r["name"] for r in rows if r.get("name")]
            return names
        except Exception as e:
            logger.error("Failed to list method names: %s", e)
            return []

    @staticmethod
    async def _merge_method_alias_in_tx(tx: Any, primary: str, alias: str) -> bool:
        """
        在写事务内将 alias Method 的边迁到 primary 后 DETACH DELETE alias。
        覆盖 PROPOSES、IMPROVES_UPON（入/出）、EVOLVED_FROM（入/出）、APPLIED_TO；不依赖 APOC。
        """
        probe = await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            RETURN 1 AS ok
            LIMIT 1
            """,
            primary=primary,
            alias=alias,
        )
        if not await probe.single():
            return False

        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (p:Paper)-[r:PROPOSES]->(alias)
            MERGE (p)-[:PROPOSES]->(primary)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (src:Method)-[r:IMPROVES_UPON]->(alias)
            WITH primary, alias, src, r
            MERGE (src)-[nr:IMPROVES_UPON]->(primary)
            SET nr += properties(r)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (alias)-[r:IMPROVES_UPON]->(tgt:Method)
            WITH primary, alias, tgt, r
            MERGE (primary)-[nr:IMPROVES_UPON]->(tgt)
            SET nr += properties(r)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (src:Method)-[r:EVOLVED_FROM]->(alias)
            WITH primary, alias, src, r
            MERGE (src)-[nr:EVOLVED_FROM]->(primary)
            SET nr += properties(r)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (alias)-[r:EVOLVED_FROM]->(tgt:Method)
            WITH primary, alias, tgt, r
            MERGE (primary)-[nr:EVOLVED_FROM]->(tgt)
            SET nr += properties(r)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            MATCH (alias)-[r:APPLIED_TO]->(t:Task)
            MERGE (primary)-[:APPLIED_TO]->(t)
            DELETE r
            """,
            primary=primary,
            alias=alias,
        )
        await tx.run(
            """
            MATCH (primary:Method {name: $primary})
            MATCH (alias:Method {name: $alias})
            WHERE primary <> alias
            DETACH DELETE alias
            """,
            primary=primary,
            alias=alias,
        )
        return True

    async def merge_method_nodes(self, primary_name: str, aliases: List[str]) -> int:
        """
        将多个同义 Method 物理融合到 primary_name：边重定向后删除 alias 节点。

        Returns:
            成功删除的 alias 节点数量。
        """
        primary = (primary_name or "").strip()
        if not primary:
            return 0
        clean_aliases = [
            a.strip()
            for a in (aliases or [])
            if isinstance(a, str) and a.strip() and a.strip() != primary
        ]
        if not clean_aliases:
            return 0
        if self._driver is None:
            await self.connect()

        merged_count = 0

        async def work(tx: Any) -> None:
            nonlocal merged_count
            for al in clean_aliases:
                if await Neo4jClient._merge_method_alias_in_tx(tx, primary, al):
                    merged_count += 1
                    logger.info(
                        "Merged Method alias %r into primary %r", al, primary
                    )
                else:
                    logger.debug(
                        "Skipped Method merge (missing nodes or same id): %r -> %r",
                        al,
                        primary,
                    )

        async with self._driver.session() as session:
            await session.execute_write(work)
        return merged_count

    async def export_graph_snapshot(
        self, *, include_embeddings: bool = True
    ) -> Dict[str, Any]:
        """
        导出当前 Neo4j 全库为 JSON 快照（节点 + 有向关系），便于备份与迁移。

        关系端点使用与 MERGE 一致的业务键（如 Paper.arxiv_id），不依赖 elementId。
        """
        if self._driver is None:
            await self.connect()
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        nodes: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        async with self._driver.session() as session:
            nres = await session.run(
                """
                MATCH (n)
                RETURN labels(n) AS labels, properties(n) AS properties
                """
            )
            async for rec in nres:
                labels = list(rec["labels"])
                props = dict(rec["properties"])
                if not include_embeddings:
                    props.pop("embedding", None)
                nodes.append(
                    {
                        "labels": labels,
                        "properties": _jsonify_node_properties(props),
                    }
                )

            rres = await session.run(
                """
                MATCH (a)-[r]->(b)
                RETURN labels(a) AS la, properties(a) AS pa,
                       type(r) AS rt, properties(r) AS pr,
                       labels(b) AS lb, properties(b) AS pb
                """
            )
            async for rec in rres:
                la = list(rec["la"])
                lb = list(rec["lb"])
                pa = dict(rec["pa"])
                pb = dict(rec["pb"])
                rt = rec["rt"]
                pr = dict(rec["pr"])
                start_ep = _endpoint_from_node(la, pa)
                end_ep = _endpoint_from_node(lb, pb)
                if not start_ep or not end_ep:
                    logger.debug(
                        "export snapshot: skip relationship %s (unmapped endpoint)",
                        rt,
                    )
                    continue
                if rt not in _REL_TYPES:
                    logger.debug("export snapshot: skip unknown rel type %s", rt)
                    continue
                sl, _, el, _ = _REL_TYPES[str(rt)]
                if start_ep["label"] != sl or end_ep["label"] != el:
                    logger.debug(
                        "export snapshot: skip %s rel endpoint mismatch %s->%s",
                        rt,
                        start_ep["label"],
                        end_ep["label"],
                    )
                    continue
                relationships.append(
                    {
                        "type": str(rt),
                        "start": start_ep,
                        "end": end_ep,
                        "properties": _jsonify_node_properties(pr),
                    }
                )

        return {
            "format": _SNAPSHOT_FORMAT,
            "version": _SNAPSHOT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "include_embeddings": include_embeddings,
            "nodes": nodes,
            "relationships": relationships,
        }

    async def _merge_snapshot_node_tx(self, tx: Any, lbl: str, props: Dict[str, Any]) -> bool:
        keys = _LABEL_MERGE_KEYS[lbl]
        for k in keys:
            if k not in props:
                return False
        if lbl == "Paper":
            await tx.run(
                "MERGE (n:Paper {arxiv_id: $k}) SET n += $p",
                k=props["arxiv_id"],
                p=props,
            )
        elif lbl == "Author":
            await tx.run(
                "MERGE (n:Author {name: $k}) SET n += $p",
                k=props["name"],
                p=props,
            )
        elif lbl == "Task":
            await tx.run(
                "MERGE (n:Task {name: $k}) SET n += $p",
                k=props["name"],
                p=props,
            )
        elif lbl == "Method":
            await tx.run(
                "MERGE (n:Method {name: $k}) SET n += $p",
                k=props["name"],
                p=props,
            )
        elif lbl == "Dataset":
            await tx.run(
                "MERGE (n:Dataset {name: $k}) SET n += $p",
                k=props["name"],
                p=props,
            )
        # elif lbl == "Innovation": # Removed
        #     await tx.run(
        #         "MERGE (n:Innovation {content: $k}) SET n += $p",
        #         k=props["content"],
        #         p=props,
        #     )
        # elif lbl == "Limitation": # Removed
        #     await tx.run(
        #         "MERGE (n:Limitation {content: $k}) SET n += $p",
        #         k=props["content"],
        #         p=props,
        #     )
        elif lbl == "Metric":
            await tx.run(
                "MERGE (n:Metric {name: $k}) SET n += $p",
                k=props["name"],
                p=props,
            )
        else:
            return False
        return True

    async def _merge_snapshot_rel_tx(self, tx: Any, rel: Dict[str, Any]) -> bool:
        rt = rel.get("type")
        if not isinstance(rt, str) or rt not in _REL_TYPES:
            return False
        sl, sk, el, ek = _REL_TYPES[rt]
        st = rel.get("start") or {}
        en = rel.get("end") or {}
        rp = rel.get("properties") if isinstance(rel.get("properties"), dict) else {}
        if st.get("label") != sl or en.get("label") != el:
            return False
        sm = st.get("match") or {}
        em = en.get("match") or {}
        if not isinstance(sm, dict) or not isinstance(em, dict):
            return False
        for k in sk:
            if k not in sm:
                return False
        for k in ek:
            if k not in em:
                return False

        if rt == "WRITTEN_BY":
            await tx.run(
                """
                MATCH (a:Paper {arxiv_id: $sa})
                MATCH (b:Author {name: $nb})
                MERGE (a)-[r:WRITTEN_BY]->(b)
                SET r += $rp
                """,
                sa=sm["arxiv_id"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "ADDRESSES":
            await tx.run(
                """
                MATCH (a:Paper {arxiv_id: $sa})
                MATCH (b:Task {name: $nb})
                MERGE (a)-[r:ADDRESSES]->(b)
                SET r += $rp
                """,
                sa=sm["arxiv_id"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "PROPOSES":
            await tx.run(
                """
                MATCH (a:Paper {arxiv_id: $sa})
                MATCH (b:Method {name: $nb})
                MERGE (a)-[r:PROPOSES]->(b)
                SET r += $rp
                """,
                sa=sm["arxiv_id"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "APPLIED_TO":
            await tx.run(
                """
                MATCH (a:Method {name: $sa})
                MATCH (b:Task {name: $nb})
                MERGE (a)-[r:APPLIED_TO]->(b)
                SET r += $rp
                """,
                sa=sm["name"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "EVALUATED_ON":
            await tx.run(
                """
                MATCH (a:Paper {arxiv_id: $sa})
                MATCH (b:Dataset {name: $nb})
                MERGE (a)-[r:EVALUATED_ON]->(b)
                SET r += $rp
                """,
                sa=sm["arxiv_id"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "IMPROVES_UPON":
            await tx.run(
                """
                MATCH (a:Method {name: $sa})
                MATCH (b:Method {name: $nb})
                MERGE (a)-[r:IMPROVES_UPON]->(b)
                SET r += $rp
                """,
                sa=sm["name"],
                nb=em["name"],
                rp=rp,
            )
        elif rt == "EVOLVED_FROM":
            await tx.run(
                """
                MATCH (a:Method {name: $sa})
                MATCH (b:Method {name: $nb})
                MERGE (a)-[r:EVOLVED_FROM]->(b)
                SET r += $rp
                """,
                sa=sm["name"],
                nb=em["name"],
                rp=rp,
            )
        # elif rt == "HAS_INNOVATION": # Removed
        #     await tx.run(
        #         """
        #         MATCH (a:Paper {arxiv_id: $sa})
        #         MATCH (b:Innovation {content: $nb})
        #         MERGE (a)-[r:HAS_INNOVATION]->(b)
        #         SET r += $rp
        #         """,
        #         sa=sm["arxiv_id"],
        #         nb=em["content"],
        #         rp=rp,
        #     )
        # elif rt == "HAS_LIMITATION": # Removed
        #     await tx.run(
        #         """
        #         MATCH (a:Paper {arxiv_id: $sa})
        #         MATCH (b:Limitation {content: $nb})
        #         MERGE (a)-[r:HAS_LIMITATION]->(b)
        #         SET r += $rp
        #         """,
        #         sa=sm["arxiv_id"],
        #         nb=em["content"],
        #         rp=rp,
        #     )
        elif rt == "MEASURES":
            await tx.run(
                """
                MATCH (a:Paper {arxiv_id: $sa})
                MATCH (b:Metric {name: $nb})
                MERGE (a)-[r:MEASURES]->(b)
                SET r += $rp
                """,
                sa=sm["arxiv_id"],
                nb=em["name"],
                rp=rp,
            )
        else:
            return False
        return True

    async def import_graph_snapshot(
        self, payload: Dict[str, Any], *, replace: bool = False
    ) -> Dict[str, int]:
        """
        从 export_graph_snapshot 生成的 JSON 恢复图数据。

        merge：与现有数据按 MERGE 键合并；replace：先清空 Neo4j 再导入（不清理 Redis）。
        """
        if payload.get("format") != _SNAPSHOT_FORMAT:
            raise ValueError(
                "invalid snapshot: expected format 'arxprism-neo4j-snapshot'"
            )
        ver = payload.get("version")
        if ver != _SNAPSHOT_VERSION:
            raise ValueError(
                f"unsupported snapshot version (expected {_SNAPSHOT_VERSION}, got {ver!r})"
            )
        nodes = payload.get("nodes")
        rels = payload.get("relationships")
        if not isinstance(nodes, list) or not isinstance(rels, list):
            raise ValueError("snapshot must contain 'nodes' and 'relationships' arrays")

        if self._driver is None:
            await self.connect()
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        if replace:
            await self.wipe_all_graph_data()

        stats: Dict[str, int] = {
            "nodes_upserted": 0,
            "relationships_upserted": 0,
            "nodes_skipped": 0,
            "relationships_skipped": 0,
        }

        async def work(tx: Any) -> None:
            for entry in nodes:
                if not isinstance(entry, dict):
                    stats["nodes_skipped"] += 1
                    continue
                labels = entry.get("labels")
                props = entry.get("properties")
                if not isinstance(labels, list) or not isinstance(props, dict):
                    stats["nodes_skipped"] += 1
                    continue
                lbl = _primary_label(labels)
                if not lbl:
                    stats["nodes_skipped"] += 1
                    continue
                ok = await self._merge_snapshot_node_tx(tx, lbl, props)
                if ok:
                    stats["nodes_upserted"] += 1
                else:
                    stats["nodes_skipped"] += 1
            for rel in rels:
                if not isinstance(rel, dict):
                    stats["relationships_skipped"] += 1
                    continue
                ok = await self._merge_snapshot_rel_tx(tx, rel)
                if ok:
                    stats["relationships_upserted"] += 1
                else:
                    stats["relationships_skipped"] += 1

        async with self._driver.session() as session:
            await session.execute_write(work)

        return stats

    async def count_total_nodes(self) -> int:
        """返回库中节点总数（用于管理态概览）。"""
        if self._driver is None:
            await self.connect()
        if self._driver is None:
            return 0
        try:
            async with self._driver.session() as session:
                result = await session.run("MATCH (n) RETURN count(n) AS c")
                rec = await result.single()
                if rec and rec.get("c") is not None:
                    return int(rec["c"])
        except Exception as e:
            logger.warning("count_total_nodes failed: %s", e)
        return 0

    async def wipe_all_graph_data(self) -> Dict[str, int]:
        """
        删除当前 Neo4j 库中全部节点与关系（DETACH DELETE）。

        仅应由受保护的管理员接口调用。
        """
        if self._driver is None:
            await self.connect()
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        async with self._driver.session() as session:
            count_result = await session.run("MATCH (n) RETURN count(n) AS c")
            rec = await count_result.single()
            n_before = int(rec["c"]) if rec and rec.get("c") is not None else 0
            await session.run("MATCH (n) DETACH DELETE n")

        logger.warning("Neo4j wiped: removed %s nodes (and their relationships)", n_before)
        return {"nodes_deleted": n_before}


# 单例实例
neo4j_client = Neo4jClient()


async def get_neo4j_client() -> Neo4jClient:
    """Neo4j 客户端依赖注入."""
    return neo4j_client
