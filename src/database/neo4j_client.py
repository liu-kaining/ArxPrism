"""
Neo4j Database Client

使用 neo4j.AsyncGraphDatabase 实现异步图数据库客户端。
所有写入操作必须使用 MERGE 语句保证幂等性，必须使用参数化查询防注入。

防线2: 实体归一化算法 - 解决 Deep-Log / DeepLog / deeplog 节点对齐问题
防线4: DAG 环路防范 - [:IMPROVES_UPON] 边写入 published_date

Reference: ARCHITECTURE.md Section 3, TECH_DESIGN.md Section 1,
CODE_REVIEW.md Section 1
"""

import logging
import re
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, CypherSyntaxError

from src.core.config import settings
from src.models.schemas import PaperExtractionResponse

logger = logging.getLogger(__name__)

# 向量检索（与 text-embedding-3-small dimensions=1536 一致）
_PAPER_VECTOR_INDEX = "paper_embedding"
_VECTOR_MIN_SCORE = 0.3
_VECTOR_SCAN_CAP = 3000
_EMBEDDING_DIM = 1536


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
                p.reasoning_process = $reasoning_process,
                p.embedding = CASE WHEN $has_embedding THEN $embedding END
            ON MATCH SET
                p.title = $title,
                p.published_date = $published_date,
                p.url = $url,
                p.core_problem = $core_problem,
                p.summary = $summary,
                p.reasoning_process = $reasoning_process,
                p.embedding = CASE WHEN $has_embedding THEN $embedding ELSE p.embedding END
            """,
            arxiv_id=paper_id,
            title=data.title,
            published_date=published_date,
            url=f"https://arxiv.org/abs/{paper_id}",
            core_problem=core_problem,
            summary=summary_text,
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
                "skipped Method/Dataset/Innovation/Limitation edges"
            )
            return

        normalized_task: Optional[str] = None
        task_name = extraction.task_name
        if task_name and task_name != "NOT_MENTIONED":
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

        if method_name and method_name != "NOT_MENTIONED":
            normalized_method = _normalize_name(method_name)

            # 跳过空归一化结果
            if not normalized_method:
                logger.warning(f"Skipping empty normalized method name: {method_name}")
            else:
                logger.debug(f"MERGing Method: {method_name} -> normalized: {normalized_method}")
                await tx.run(
                    """
                    MERGE (m:Method {name: $name})
                    ON CREATE SET m.description = $description, m.original_name = $original_name
                    ON MATCH SET m.description = $description, m.original_name = $original_name
                    WITH m
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    MERGE (p)-[:PROPOSES]->(m)
                    """,
                    name=normalized_method,
                    original_name=method_name,
                    description=extraction.proposed_method.description,
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

        # =========================================================================
        # 7. MERGE Innovation 节点和 HAS_INNOVATION 关系
        # =========================================================================
        for innovation_content in extraction.critical_analysis.key_innovations:
            normalized_content = _normalize_name(innovation_content)

            if not normalized_content:
                logger.warning(f"Skipping empty normalized innovation: {innovation_content}")
                continue

            logger.debug(f"MERGing Innovation: {innovation_content[:50]}...")
            await tx.run(
                """
                MERGE (i:Innovation {content: $content})
                ON CREATE SET i.original_content = $original_content
                ON MATCH SET i.original_content = $original_content
                WITH i
                MATCH (p:Paper {arxiv_id: $arxiv_id})
                MERGE (p)-[:HAS_INNOVATION]->(i)
                """,
                content=normalized_content,
                original_content=innovation_content,
                arxiv_id=paper_id
            )

        # =========================================================================
        # 8. MERGE Limitation 节点和 HAS_LIMITATION 关系
        # =========================================================================
        for limitation_content in extraction.critical_analysis.limitations:
            normalized_content = _normalize_name(limitation_content)

            if not normalized_content:
                logger.warning(f"Skipping empty normalized limitation: {limitation_content}")
                continue

            logger.debug(f"MERGing Limitation: {limitation_content[:50]}...")
            await tx.run(
                """
                MERGE (l:Limitation {content: $content})
                ON CREATE SET l.original_content = $original_content
                ON MATCH SET l.original_content = $original_content
                WITH l
                MATCH (p:Paper {arxiv_id: $arxiv_id})
                MERGE (p)-[:HAS_LIMITATION]->(l)
                """,
                content=normalized_content,
                original_content=limitation_content,
                arxiv_id=paper_id
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
        向上追溯 3 层祖先，向下扩展 3 层后代。

        使用原生 Cypher 查询 [:IMPROVES_UPON] 关系。

        Args:
            method_name: 目标方法名称

        Returns:
            Dict with 'nodes' and 'links' in D3.js/ECharts format
        """
        logger.info(f"Fetching evolution tree for method: {method_name}")
        normalized_name = _normalize_name(method_name)

        try:
            if self._driver is None:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (target:Method {name: $method_name})
                    OPTIONAL MATCH path_ancestors = (target)-[:IMPROVES_UPON*1..3]-(ancestor:Method)
                    OPTIONAL MATCH path_descendants = (target)<-[:IMPROVES_UPON*1..3]-(descendant:Method)
                    WITH collect(DISTINCT ancestor) AS ancestors,
                         collect(DISTINCT descendant) AS descendants,
                         target
                    UNWIND ancestors AS a
                    WITH collect(DISTINCT a) AS ancestors, descendants, target
                    UNWIND descendants AS d
                    WITH ancestors, collect(DISTINCT d) AS descendants, target
                    RETURN ancestors, descendants, target
                    """,
                    method_name=normalized_name
                )

                records = await result.data()
                nodes: List[Dict[str, Any]] = []
                links: List[Dict[str, Any]] = []
                seen_methods: set = set()

                for record in records:
                    ancestors = record.get("ancestors", []) or []
                    descendants = record.get("descendants", []) or []
                    target = record.get("target")

                    # Add target method (generation 0)
                    if target:
                        nodes.append({
                            "id": target["name"],
                            "name": target.get("original_name") or target["name"],
                            "generation": 0
                        })
                        seen_methods.add(target["name"])

                    # Add ancestors (negative generations, going back)
                    for i, ancestor in enumerate(ancestors):
                        if ancestor and ancestor["name"] not in seen_methods:
                            nodes.append({
                                "id": ancestor["name"],
                                "name": ancestor.get("original_name") or ancestor["name"],
                                "generation": -(i + 1)
                            })
                            seen_methods.add(ancestor["name"])

                        # Link ancestor → target (IDs 必须与节点 id 一致：归一化 name)
                        if ancestor and target:
                            links.append({
                                "source": ancestor["name"],
                                "target": target["name"],
                            })

                    # Add descendants (positive generations, going forward)
                    for i, descendant in enumerate(descendants):
                        if descendant and descendant["name"] not in seen_methods:
                            nodes.append({
                                "id": descendant["name"],
                                "name": descendant.get("original_name") or descendant["name"],
                                "generation": i + 1
                            })
                            seen_methods.add(descendant["name"])

                        # Link target → descendant
                        if descendant and target:
                            links.append({
                                "source": target["name"],
                                "target": descendant["name"],
                            })

                id_list = list(seen_methods)
                if id_list:
                    res_edges = await session.run(
                        """
                        MATCH (s:Method)-[r:IMPROVES_UPON]->(t:Method)
                        WHERE s.name IN $ids AND t.name IN $ids
                        RETURN s.name AS source, t.name AS target,
                               coalesce(r.dataset, '') AS dataset,
                               coalesce(r.metrics_improvement, '') AS metrics_improvement
                        """,
                        ids=id_list,
                    )
                    edge_meta: Dict[tuple, Dict[str, str]] = {}
                    for erow in await res_edges.data():
                        key = (erow["source"], erow["target"])
                        if key not in edge_meta:
                            edge_meta[key] = {
                                "dataset": erow.get("dataset") or "",
                                "metrics_improvement": erow.get("metrics_improvement")
                                or "",
                            }
                    for link in links:
                        meta = edge_meta.get((link["source"], link["target"]))
                        if meta:
                            link["dataset"] = meta["dataset"]
                            link["metrics_improvement"] = meta["metrics_improvement"]

                logger.info(f"Evolution tree: {len(nodes)} nodes, {len(links)} links")
                return {"nodes": nodes, "links": links}

        except Exception as e:
            logger.error(f"Failed to fetch evolution tree: {e}")
            return {"nodes": [], "links": []}

    async def list_evolution_methods(self) -> Dict[str, Any]:
        """
        供前端「发现」进化树入口：
        - with_evolution: 至少参与一条 IMPROVES_UPON 的 Method（推荐点击）
        - other_methods: 图中有节点、但当前无任何 IMPROVES_UPON 关联的方法（仍可尝试以根查询）
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
                    MATCH (m:Method)-[r:IMPROVES_UPON]-(:Method)
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
                    WHERE NOT (m)-[:IMPROVES_UPON]-(:Method)
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
        if not q_raw.strip():
            return None
        from src.services.llm_extractor import get_llm_extractor

        vec = await get_llm_extractor().generate_embedding(q_raw)
        if vec and len(vec) == _EMBEDDING_DIM:
            return vec
        return None

    async def search_papers(
        self,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
        task_topic: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Hybrid 检索：有查询词且向量化成功时用向量索引；否则按时间倒序全量或关键词 CONTAINS。
        task_topic 与列表/统计一致。
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
             collect(DISTINCT coalesce(baseline.original_name, baseline.name)) AS baselines,
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
                query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = bool(q_raw) and query_vector is not None

                if use_vector:
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
        self, query: str = "", task_topic: str = ""
    ) -> int:
        """与 search_papers 相同过滤条件下的命中总数。"""
        q_raw = (query or "").strip()
        q_lower = q_raw.lower()
        tt = (task_topic or "").strip()
        if self._driver is None:
            await self.connect()

        try:
            async with self._driver.session() as session:
                query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = bool(q_raw) and query_vector is not None

                if use_vector:
                    topk = _VECTOR_SCAN_CAP
                    cypher = """
                    CALL db.index.vector.queryNodes($index_name, $topk, $query_vector)
                    YIELD node AS p, score
                    WHERE score >= $min_score
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, score, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
                    RETURN count(DISTINCT p) AS total
                    """
                    result = await session.run(
                        cypher,
                        index_name=_PAPER_VECTOR_INDEX,
                        topk=topk,
                        query_vector=query_vector,
                        min_score=_VECTOR_MIN_SCORE,
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
        self, query: str = "", task_topic: str = ""
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
                query_vector = await self._resolve_query_embedding(q_raw)
                use_vector = bool(q_raw) and query_vector is not None

                if use_vector:
                    topk = _VECTOR_SCAN_CAP
                    cypher = """
                    CALL db.index.vector.queryNodes($index_name, $topk, $query_vector)
                    YIELD node AS p, score
                    WHERE score >= $min_score
                    OPTIONAL MATCH (p)-[:ADDRESSES]->(t0:Task)
                    WITH p, score, t0
                    WHERE $task_topic = "" OR coalesce(t0.original_name, t0.name, '(未标注主题)') = $task_topic
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
                        query=sq, task_topic=tf
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
        OPTIONAL MATCH (p)-[:HAS_INNOVATION]->(i:Innovation)
        OPTIONAL MATCH (p)-[:HAS_LIMITATION]->(l:Limitation)
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
          coalesce(p.reasoning_process, '') AS reasoning_process,
          collect(DISTINCT coalesce(a.original_name, a.name)) AS authors,
          collect(DISTINCT {
            name: coalesce(m.original_name, m.name),
            description: m.description
          }) AS methods,
          collect(DISTINCT coalesce(i.original_content, i.content)) AS innovations,
          collect(DISTINCT coalesce(l.original_content, l.content)) AS limitations,
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
            # 提取方法名称列表
            method_names = [m["name"] for m in row["methods"] if m.get("name")]
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
                "reasoning_process": row.get("reasoning_process") or "",
                "authors": author_list,
                "proposed_method": method_names[0] if method_names else "",
                "innovations": [i for i in row["innovations"] if i],
                "limitations": [l for l in row["limitations"] if l],
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
        覆盖 PROPOSES、IMPROVES_UPON（入/出）、APPLIED_TO；不依赖 APOC。
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
