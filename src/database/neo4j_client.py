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
            logger.info("Neo4j driver initialized successfully")

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
        防线2: 所有 MERGE 使用 _normalize_name() 处理后的名称
        防线4: [:IMPROVES_UPON] 边写入 published_date
        """
        paper_id = data.paper_id
        extraction = data.extraction_data
        published_date = data.publication_date

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
                p.core_problem = $core_problem
            ON MATCH SET
                p.title = $title,
                p.published_date = $published_date,
                p.url = $url,
                p.core_problem = $core_problem
            """,
            arxiv_id=paper_id,
            title=data.title,
            published_date=published_date,
            url=f"https://arxiv.org/abs/{paper_id}",
            core_problem=extraction.core_problem
        )

        # =========================================================================
        # 2. MERGE Author 节点和 WRITTEN_BY 关系
        # =========================================================================
        for author_name in data.authors:
            normalized_name = _normalize_name(author_name)
            logger.debug(f"MERGing Author: {author_name} -> normalized: {normalized_name}")
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

        # =========================================================================
        # 3. MERGE Method 节点和 PROPOSES 关系
        # =========================================================================
        method_name = extraction.proposed_method.name
        normalized_method = None  # 初始化，避免未定义

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

                # =========================================================================
                # 4. MERGE baselines_beaten -> Method 节点和 [:IMPROVES_UPON] 关系 (核心边)
                #
                # 防线2: 使用 _normalize_name() 归一化后的名称作为 MERGE 键
                # 防线4: 写入 published_date 到边属性，防止环路
                # =========================================================================
                for baseline_name in extraction.knowledge_graph_nodes.baselines_beaten:
                    normalized_baseline = _normalize_name(baseline_name)

                    # 跳过空归一化结果
                    if not normalized_baseline:
                        logger.warning(f"Skipping empty normalized baseline: {baseline_name}")
                        continue

                    logger.debug(f"MERGing IMPROVES_UPON: {method_name} -> {baseline_name} (normalized: {normalized_baseline})")
                    await tx.run(
                        """
                        MERGE (improved:Method {name: $method_name})
                        MERGE (baseline:Method {name: $baseline_name})
                        ON CREATE SET
                            baseline.original_name = $baseline_original_name,
                            baseline.first_appeared = $published_date
                        ON MATCH SET
                            baseline.original_name = $baseline_original_name
                        WITH improved, baseline
                        MATCH (paper:Paper {arxiv_id: $arxiv_id})
                        MERGE (improved)-[r:IMPROVES_UPON]->(baseline)
                        SET r.discovered_at = $published_date
                        """,
                        method_name=normalized_method,
                        baseline_name=normalized_baseline,
                        baseline_original_name=baseline_name,
                        published_date=published_date,
                        arxiv_id=paper_id
                    )

        # =========================================================================
        # 5. MERGE Dataset 节点和 EVALUATED_ON 关系
        # =========================================================================
        for dataset_name in extraction.knowledge_graph_nodes.datasets_used:
            normalized_dataset = _normalize_name(dataset_name)

            if not normalized_dataset:
                logger.warning(f"Skipping empty normalized dataset: {dataset_name}")
                continue

            logger.debug(f"MERGing Dataset: {dataset_name} -> normalized: {normalized_dataset}")
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
                original_name=dataset_name,
                arxiv_id=paper_id
            )

        # =========================================================================
        # 6. MERGE Metric 节点和 MEASURES 关系
        # =========================================================================
        for metric_name in extraction.knowledge_graph_nodes.metrics_improved:
            normalized_metric = _normalize_name(metric_name)

            if not normalized_metric:
                logger.warning(f"Skipping empty normalized metric: {metric_name}")
                continue

            logger.debug(f"MERGing Metric: {metric_name} -> normalized: {normalized_metric}")
            await tx.run(
                """
                MERGE (m:Metric {name: $name})
                ON CREATE SET m.original_name = $original_name
                ON MATCH SET m.original_name = $original_name
                WITH m
                MATCH (p:Paper {arxiv_id: $arxiv_id})
                MERGE (p)-[:MEASURES]->(m)
                """,
                name=normalized_metric,
                original_name=metric_name,
                arxiv_id=paper_id
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

                        # Link ancestor to target
                        if ancestor:
                            links.append({
                                "source": ancestor["name"],
                                "target": method_name
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

                        # Link target to descendant
                        if descendant:
                            links.append({
                                "source": method_name,
                                "target": descendant["name"]
                            })

                logger.info(f"Evolution tree: {len(nodes)} nodes, {len(links)} links")
                return {"nodes": nodes, "links": links}

        except Exception as e:
            logger.error(f"Failed to fetch evolution tree: {e}")
            return {"nodes": [], "links": []}

    async def search_papers(self, query: str = "", limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        按主题/关键词检索已入库论文（用于"查 SRE 主题"这条主路径）。

        匹配字段：
        - Paper.title
        - Paper.core_problem
        - Proposed method original_name/name（可选）

        全部使用参数化查询，避免注入。
        """
        q = (query or "").strip().lower()
        if self._driver is None:
            await self.connect()

        cypher = """
        MATCH (p:Paper)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        WITH p, collect(DISTINCT coalesce(m.original_name, m.name)) AS methods
        WHERE $q = "" OR toLower(coalesce(p.title,"")) CONTAINS $q
           OR toLower(coalesce(p.core_problem,"")) CONTAINS $q
           OR any(x IN methods WHERE toLower(coalesce(x,"")) CONTAINS $q)
        RETURN
          p.arxiv_id AS arxiv_id,
          p.title AS title,
          p.published_date AS published_date,
          p.core_problem AS core_problem,
          methods AS methods
        ORDER BY p.published_date DESC
        SKIP $offset
        LIMIT $limit
        """

        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, q=q, limit=limit, offset=offset)
                rows = await result.data()
            return rows
        except Exception as e:
            logger.error(f"Failed to search papers: {e}")
            return []

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
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:INNOVATES]->(i:Innovation)
        OPTIONAL MATCH (p)-[:HAS_LIMITATION]->(l:Limitation)
        OPTIONAL MATCH (p)-[:OUTPERFORMS]->(b:Method)
        OPTIONAL MATCH (p)-[:USES_DATASET]->(d:Dataset)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m2:Method)-[:USES_DATASET]->(m2d:Dataset)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m3:Method)-[:EVALUATES_USING]->(mt:Metric)

        RETURN
          p.arxiv_id AS arxiv_id,
          p.title AS title,
          p.published_date AS published_date,
          p.core_problem AS core_problem,
          p.summary AS summary,
          collect(DISTINCT {
            name: coalesce(m.original_name, m.name),
            description: m.description
          }) AS methods,
          collect(DISTINCT i.content) AS innovations,
          collect(DISTINCT l.content) AS limitations,
          collect(DISTINCT coalesce(b.original_name, b.name)) AS baselines,
          collect(DISTINCT d.name) AS datasets,
          collect(DISTINCT mt.name) AS metrics
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

            return {
                "arxiv_id": row["arxiv_id"],
                "title": row["title"],
                "published_date": row.get("published_date", ""),
                "core_problem": row.get("core_problem", ""),
                "summary": row.get("summary", ""),
                "authors": [],  # 作者信息可能需要单独存储或从其他来源获取
                "proposed_method": method_names[0] if method_names else "",
                "innovations": [i for i in row["innovations"] if i],
                "limitations": [l for l in row["limitations"] if l],
                "baselines": [b for b in row["baselines"] if b],
                "datasets": [d for d in row["datasets"] if d],
                "metrics": [m for m in row["metrics"] if m],
            }

        except Exception as e:
            logger.error(f"Failed to get paper by id: {e}")
            return None


# 单例实例
neo4j_client = Neo4jClient()


async def get_neo4j_client() -> Neo4jClient:
    """Neo4j 客户端依赖注入."""
    return neo4j_client
