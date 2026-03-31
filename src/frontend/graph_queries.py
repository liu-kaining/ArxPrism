"""
Graph Queries Module

Neo4j 查询逻辑与 Streamlit 渲染解耦。
提供独立的图数据库查询接口。

Reference: ARCHITECTURE.md Section 3
"""

import logging
from typing import Any, Dict, List, Optional

from src.database.neo4j_client import Neo4jClient
from src.core.config import settings

logger = logging.getLogger(__name__)


class GraphQueries:
    """Neo4j 图谱查询接口."""

    def __init__(self):
        self._client: Optional[Neo4jClient] = None

    def _get_client(self) -> Optional[Neo4jClient]:
        """获取或创建 Neo4j 客户端 (延迟初始化)."""
        if self._client is None:
            try:
                self._client = Neo4jClient()
            except Exception as e:
                logger.error(f"Failed to create Neo4j client: {e}")
                return None
        return self._client

    async def verify_connection(self) -> bool:
        """验证 Neo4j 连接性."""
        client = self._get_client()
        if client is None:
            return False
        try:
            return await client.verify_connectivity()
        except Exception as e:
            logger.error(f"Neo4j connection verification failed: {e}")
            return False

    async def get_evolution_tree_data(self, method_name: str) -> Dict[str, Any]:
        """
        获取方法进化树数据.

        Args:
            method_name: 方法名称

        Returns:
            Dict with 'nodes' and 'links' lists, or empty dict on error
        """
        client = self._get_client()
        if client is None:
            logger.error("Neo4j client not available")
            return {"nodes": [], "links": [], "error": "Neo4j client not available"}

        try:
            return await client.get_evolution_tree(method_name)
        except Exception as e:
            logger.error(f"Failed to fetch evolution tree for '{method_name}': {e}")
            return {"nodes": [], "links": [], "error": str(e)}

    async def get_paper_graph_data(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取论文图谱数据.

        Args:
            arxiv_id: arXiv ID

        Returns:
            Dict with 'nodes' and 'relationships' lists, or empty dict on error
        """
        client = self._get_client()
        if client is None:
            logger.error("Neo4j client not available")
            return {"nodes": [], "relationships": [], "error": "Neo4j client not available"}

        try:
            return await client.get_paper_graph(arxiv_id)
        except Exception as e:
            logger.error(f"Failed to fetch paper graph for '{arxiv_id}': {e}")
            return {"nodes": [], "relationships": [], "error": str(e)}

    async def close(self) -> None:
        """关闭 Neo4j 连接."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.error(f"Failed to close Neo4j client: {e}")
            self._client = None


# 同步版本，用于 Streamlit callbacks
class SyncGraphQueries:
    """同步版本的图谱查询 (用于 Streamlit)."""

    def __init__(self):
        self._client: Optional[Neo4jClient] = None

    def _get_client(self) -> Optional[Neo4jClient]:
        """获取或创建 Neo4j 客户端."""
        if self._client is None:
            try:
                self._client = Neo4jClient()
                # 同步连接
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._client.connect())
                loop.close()
            except Exception as e:
                logger.error(f"Failed to create Neo4j client: {e}")
                return None
        return self._client

    def verify_connection(self) -> bool:
        """验证 Neo4j 连接性 (同步版本)."""
        client = self._get_client()
        if client is None:
            return False
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(client.verify_connectivity())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Neo4j connection verification failed: {e}")
            return False

    def get_evolution_tree_data(self, method_name: str) -> Dict[str, Any]:
        """
        获取方法进化树数据 (同步版本).

        Args:
            method_name: 方法名称

        Returns:
            Dict with 'nodes' and 'links' lists, or empty dict on error
        """
        client = self._get_client()
        if client is None:
            return {"nodes": [], "links": [], "error": "Neo4j client not available"}

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(client.get_evolution_tree(method_name))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Failed to fetch evolution tree for '{method_name}': {e}")
            return {"nodes": [], "links": [], "error": str(e)}

    def get_paper_graph_data(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取论文图谱数据 (同步版本).

        Args:
            arxiv_id: arXiv ID

        Returns:
            Dict with 'nodes' and 'relationships' lists, or empty dict on error
        """
        client = self._get_client()
        if client is None:
            return {"nodes": [], "relationships": [], "error": "Neo4j client not available"}

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(client.get_paper_graph(arxiv_id))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Failed to fetch paper graph for '{arxiv_id}': {e}")
            return {"nodes": [], "relationships": [], "error": str(e)}

    def close(self) -> None:
        """关闭 Neo4j 连接 (同步版本)."""
        if self._client is not None:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._client.close())
                loop.close()
            except Exception as e:
                logger.error(f"Failed to close Neo4j client: {e}")
            self._client = None


# 全局实例 (延迟初始化)
_graph_queries: Optional[SyncGraphQueries] = None


def get_sync_graph_queries() -> SyncGraphQueries:
    """获取同步图谱查询实例."""
    global _graph_queries
    if _graph_queries is None:
        _graph_queries = SyncGraphQueries()
    return _graph_queries
