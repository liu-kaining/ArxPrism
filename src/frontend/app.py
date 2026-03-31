"""
ArxPrism Streamlit Frontend

交互式前端界面，用于演示 ArxPrism 论文萃取流水线。
通过 HTTP 请求与 API 服务通信。

Layout:
- 左侧边栏: 论文抓取控制
- 右侧主界面: 进化树可视化

Usage:
    streamlit run src/frontend/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit 执行脚本时，sys.path 通常只包含脚本目录（src/frontend），
# 这会导致 `import src...` 失败。这里显式把项目根目录加入 sys.path。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import requests
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

from src.core.config import settings

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="ArxPrism - 学术知识图谱萃取",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# API Configuration
# =============================================================================

# Docker 网络中 API 服务地址
API_BASE_URL = "http://api:8000"


def get_api_url(path: str) -> str:
    """获取完整的 API URL."""
    return f"{API_BASE_URL}{path}"


def check_api_health() -> bool:
    """检查 API 是否可用."""
    try:
        response = requests.get(
            get_api_url("/health"),
            timeout=5
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def trigger_pipeline(query: str, max_results: int) -> dict:
    """
    触发论文萃取流水线.

    Args:
        query: arXiv 搜索查询
        max_results: 最大论文数量

    Returns:
        API 响应 JSON
    """
    try:
        response = requests.post(
            get_api_url("/api/v1/pipeline/trigger"),
            json={
                "topic_query": query,
                "max_results": max_results
            },
            timeout=60
        )
        if response.status_code in (200, 202):
            return response.json()
        else:
            return {"error": f"API 返回错误: {response.status_code}", "detail": response.text}
    except requests.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}


def get_evolution_tree(method_name: str) -> dict:
    """
    获取方法进化树数据.

    Args:
        method_name: 方法名称

    Returns:
        API 响应 JSON，包含 nodes 和 links
    """
    try:
        response = requests.get(
            get_api_url("/api/v1/graph/evolution"),
            params={"method_name": method_name},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {"error": f"未找到方法 '{method_name}'"}
        else:
            return {"error": f"API 返回错误: {response.status_code}"}
    except requests.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}


def search_papers(query: str, limit: int = 20, offset: int = 0) -> dict:
    """按主题/关键词检索已入库论文列表."""
    try:
        response = requests.get(
            get_api_url("/api/v1/papers"),
            params={"query": query, "limit": limit, "offset": offset},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"API 返回错误: {response.status_code}", "detail": response.text}
    except requests.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}


def render_paper_graph(nodes: list, relationships: list) -> bool:
    """渲染论文一跳邻域图谱."""
    if not nodes:
        return False
    try:
        graph_nodes = []
        node_ids = set()

        def _color(labels: list[str]) -> str:
            if "Paper" in labels:
                return "#ff6b6b"  # paper
            if "Method" in labels:
                return "#4ecdc4"
            if "Author" in labels:
                return "#45b7d1"
            if "Dataset" in labels:
                return "#f7b731"
            if "Metric" in labels:
                return "#a55eea"
            if "Innovation" in labels or "Limitation" in labels:
                return "#778ca3"
            return "#95a5a6"

        for n in nodes:
            nid = str(n.get("id", ""))
            labels = n.get("labels", []) or []
            props = n.get("properties", {}) or {}
            label = props.get("original_name") or props.get("title") or nid
            graph_nodes.append(
                Node(
                    id=nid,
                    label=str(label)[:48],
                    size=28 if "Paper" in labels else 20,
                    color=_color(labels),
                    font={"size": 14 if "Paper" in labels else 12},
                )
            )
            node_ids.add(nid)

        graph_edges = []
        for r in relationships:
            s = str(r.get("source_id", ""))
            t = str(r.get("target_id", ""))
            if s in node_ids and t in node_ids:
                graph_edges.append(
                    Edge(
                        source=s,
                        target=t,
                        label=str(r.get("type", "")),
                        type="CURVE_SMOOTH",
                        color="#8b949e",
                        width=2,
                    )
                )

        config = Config(
            width=900,
            height=520,
            directed=True,
            physics=True,
            hierarchical=False,
            node_spacing=100,
            level_separation=150,
            freeze=False,
            drag_nodes=True,
            zoom=True,
        )
        agraph(nodes=graph_nodes, edges=graph_edges, config=config)
        return True
    except Exception as e:
        st.error(f"论文图谱渲染失败: {e}")
        return False

def apply_theme_css(dark_mode: bool) -> None:
    """Apply minimal, modern theme CSS (light by default)."""
    if dark_mode:
        base_bg = "#0b1220"
        panel_bg = "#0f1a2b"
        border = "rgba(255,255,255,0.10)"
        text = "rgba(255,255,255,0.92)"
        muted = "rgba(255,255,255,0.70)"
        brand = "#7c9cff"
        primary = "#4f7cff"
        primary_hover = "#3f6cff"
        metric = "#9db4ff"
        graph_edge = "rgba(255,255,255,0.32)"
    else:
        base_bg = "#f6f8fc"
        panel_bg = "#ffffff"
        border = "rgba(15,23,42,0.12)"
        text = "rgba(15,23,42,0.92)"
        muted = "rgba(15,23,42,0.62)"
        brand = "#335dff"
        primary = "#2f5aff"
        primary_hover = "#244cf0"
        metric = "#1e40ff"
        graph_edge = "rgba(15,23,42,0.22)"

    st.markdown(
        f"""
<style>
  /* Page background */
  .stApp {{
    background: {base_bg};
    color: {text};
  }}

  /* Sidebar */
  [data-testid="stSidebar"] {{
    background: {panel_bg};
    border-right: 1px solid {border};
  }}

  /* Typography */
  h1, h2, h3, h4, h5, h6 {{
    color: {brand} !important;
    letter-spacing: -0.02em;
  }}
  .stMarkdown, .stText {{
    color: {text} !important;
  }}
  .stCaption, [data-testid="stCaptionContainer"] {{
    color: {muted} !important;
  }}

  /* Buttons */
  .stButton > button {{
    background: {primary};
    color: white;
    border: 1px solid rgba(255,255,255,0.0);
    border-radius: 10px;
    padding: 0.55rem 0.95rem;
    font-weight: 650;
    box-shadow: 0 6px 20px rgba(0,0,0,0.10);
  }}
  .stButton > button:hover {{
    background: {primary_hover};
  }}

  /* Inputs */
  [data-testid="stTextInputRoot"], [data-testid="stNumberInputRoot"] {{
    background: {panel_bg};
    border-radius: 12px;
  }}

  /* Metric */
  [data-testid="stMetricValue"] {{
    color: {metric} !important;
    font-size: 1.85rem !important;
    font-weight: 750 !important;
  }}

  /* Expander */
  .streamlit-expanderHeader {{
    background: {panel_bg};
    border: 1px solid {border};
    border-radius: 12px;
  }}

  /* Links */
  a {{
    color: {brand} !important;
  }}

  /* Progress bar */
  .stProgress > div > div > div > div {{
    background: {primary};
  }}

  /* Graph edge color (streamlit-agraph) */
  .vis-network .vis-edge .vis-label {{
    color: {muted};
  }}
</style>
""",
        unsafe_allow_html=True,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def render_evolution_graph(nodes: list, links: list) -> bool:
    """
    使用 streamlit-agraph 渲染进化树.

    Args:
        nodes: 节点列表
        links: 边列表

    Returns:
        True if rendering succeeded, False otherwise
    """
    if not nodes:
        return False

    try:
        # 构建节点
        graph_nodes = []
        node_ids = set()

        for node in nodes:
            node_id = str(node.get("id", ""))
            name = node.get("name", node.get("id", ""))
            generation = node.get("generation", 0)

            # 根据代数设置节点颜色
            if generation == 0:
                color = "#ff6b6b"  # 红色 - 目标方法
            elif generation < 0:
                color = "#4ecdc4"  # 青色 - 祖先
            else:
                color = "#45b7d1"  # 蓝色 - 后代

            graph_nodes.append(Node(
                id=node_id,
                label=name,
                size=25 if generation == 0 else 20,
                color=color,
                font={"size": 14 if generation == 0 else 12}
            ))
            node_ids.add(node_id)

        # 构建边
        graph_edges = []
        for link in links:
            source = str(link.get("source", ""))
            target = str(link.get("target", ""))

            # 只添加两端节点都存在的边
            if source in node_ids and target in node_ids:
                graph_edges.append(Edge(
                    source=source,
                    target=target,
                    label="IMPROVES_UPON",
                    type="CURVE_SMOOTH",
                    color="#8b949e",
                    width=2
                ))

        # 配置图
        config = Config(
            width=900,
            height=600,
            directed=True,
            physics=True,
            hierarchical=False,
            node_spacing=100,
            level_separation=150,
            color_lemaps=True,
            tooltip={"node": [], "edge": []},
            freeze=False,
            drag_nodes=True,
            drag_edges=True,
            zoom=True,
        )

        # 渲染
        agraph(nodes=graph_nodes, edges=graph_edges, config=config)
        return True

    except Exception as e:
        st.error(f"图渲染失败: {e}")
        return False


def init_session_state():
    """初始化 Streamlit 会话状态."""
    if "pipeline_run" not in st.session_state:
        st.session_state.pipeline_run = False
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


# =============================================================================
# Main Application
# =============================================================================

def main():
    """主应用入口."""

    # 初始化会话状态
    init_session_state()

    # Theme (light by default)
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False
    apply_theme_css(st.session_state.dark_mode)

    # =============================================================================
    # Header
    # =============================================================================

    st.title("🔮 ArxPrism")
    st.markdown("### 学术知识图谱萃取流水线")
    st.markdown("---")

    # =============================================================================
    # Left Sidebar - Pipeline Control
    # =============================================================================

    with st.sidebar:
        st.header("📡 论文抓取控制")

        st.toggle("🌗 深色模式", key="dark_mode")
        st.caption("默认浅色，更适合白天与截图展示")
        st.markdown("---")

        # 输入框
        query = st.text_input(
            "🔍 Topic Query",
            value="site reliability engineering",
            help="arXiv 搜索查询"
        )

        # 滑块
        max_results = st.slider(
            "📄 抓取数量",
            min_value=1,
            max_value=10,
            value=3,
            help="最多抓取论文数量"
        )

        st.markdown("---")

        # API 连接状态
        st.caption("🔌 API 连接状态")
        api_healthy = check_api_health()
        if api_healthy:
            st.success("✅ API 已连接")
        else:
            st.error("❌ API 未连接")
            st.caption("请确保 docker-compose 已启动")

        st.markdown("---")

        # 启动按钮
        if st.button("🚀 启动 ArxPrism 雷达", use_container_width=True, disabled=not api_healthy):
            if not query.strip():
                st.sidebar.error("⚠️ 请输入搜索查询")
            else:
                with st.spinner("正在处理..."):
                    progress_bar = st.progress(0)
                    progress_text = st.empty()

                    # 更新进度
                    progress_bar.progress(0.3)
                    progress_text.text("正在触发流水线...")

                    result = trigger_pipeline(query, max_results)

                    progress_bar.progress(0.8)
                    progress_text.text("等待任务执行...")

                    # 模拟等待进度
                    import time
                    for i in range(3):
                        time.sleep(0.5)
                        progress_bar.progress(0.8 + i * 0.05)

                    progress_bar.progress(1.0)
                    progress_text.text("完成!")

                    # 显示结果
                    if "error" in result:
                        st.sidebar.error(f"❌ 触发失败: {result['error']}")
                    else:
                        data = result.get("data", {})
                        status = data.get("status", "unknown")
                        task_count = data.get("task_count", 0)

                        st.sidebar.success(f"✅ 流水线已触发!")
                        st.sidebar.info(f"状态: {status}")
                        st.sidebar.info(f"任务数: {task_count}")

                        # 更新会话状态
                        st.session_state.pipeline_run = True
                        st.session_state.last_result = result

                    progress_bar.empty()
                    progress_text.empty()

        st.markdown("---")
        st.caption("ArxPrism v0.1.0")

    tabs = st.tabs(["🔎 主题检索（论文）", "🌳 技术进化树（方法）"])

    with tabs[0]:
        st.header("🔎 主题检索（论文）")
        st.caption("这是你要的主路径：按 SRE 主题/关键词检索已入库论文，并查看论文详情图谱。")

        q = st.text_input("关键词 / 主题", value="sre", help="会在 title / core_problem / method 中匹配")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            limit = st.selectbox("返回数量", [10, 20, 50, 100], index=1)
        with c2:
            do_search = st.button("搜索论文", use_container_width=True)

        if do_search:
            with st.spinner("检索中..."):
                result = search_papers(q, limit=limit, offset=0)
            if "error" in result:
                st.error(f"❌ 检索失败: {result['error']}")
            else:
                papers = result.get("data", {}).get("papers", []) or []
                st.success(f"✅ 找到 {len(papers)} 篇")
                st.dataframe(papers, use_container_width=True)

                arxiv_ids = [p.get("arxiv_id") for p in papers if p.get("arxiv_id")]
                if arxiv_ids:
                    selected = st.selectbox("选择一篇论文查看图谱", arxiv_ids)
                    if st.button("打开论文图谱", use_container_width=False):
                        with st.spinner("加载论文图谱..."):
                            graph = requests.get(get_api_url(f"/api/v1/graph/paper/{selected}"), timeout=30).json()
                        if graph.get("code") != 200:
                            st.error(f"❌ 获取失败: {graph.get('message', graph)}")
                        else:
                            data = graph.get("data", {})
                            nodes = data.get("nodes", [])
                            rels = data.get("relationships", [])
                            st.metric("节点数", len(nodes))
                            st.metric("关系数", len(rels))
                            render_paper_graph(nodes, rels)

    with tabs[1]:
        col1, col2 = st.columns([3, 1])

        with col1:
            st.header("🌳 技术进化树（方法）")
            method_query = st.text_input(
                "输入 Method 名称查询进化树",
                placeholder="例如: RAFT, WAFT, FlowFormer",
                help="输入方法名称查找其 IMPROVES_UPON 技术谱系",
                key="method_query_input",
            )
            query_button = st.button("查询进化树", use_container_width=False)

        with col2:
            st.markdown("### 📖 说明")
            st.info(
                "进化树用于查看 **方法之间** 的 IMPROVES_UPON 关系。\n\n"
                "如果你要按 SRE 主题查论文，请切到左侧的「主题检索（论文）」标签页。"
            )

        st.markdown("---")

        if query_button and method_query.strip():
            with st.spinner(f"正在查询 '{method_query}' 的进化树..."):
                result = get_evolution_tree(method_query.strip())

            if "error" in result:
                st.error(f"❌ 查询失败: {result['error']}")
            elif result.get("code") != 200:
                st.error(f"❌ API 错误: {result.get('message', 'Unknown error')}")
            else:
                data = result.get("data", {})
                nodes = data.get("nodes", [])
                links = data.get("links", [])
                if not nodes:
                    st.warning(f"⚠️ 未找到方法 '{method_query}' 的进化树")
                else:
                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                    with stat_col1:
                        st.metric("总节点数", len(nodes))
                    with stat_col2:
                        ancestors = sum(1 for n in nodes if n.get("generation", 0) < 0)
                        st.metric("祖先节点", ancestors)
                    with stat_col3:
                        descendants = sum(1 for n in nodes if n.get("generation", 0) > 0)
                        st.metric("后代节点", descendants)
                    st.markdown("---")
                    render_evolution_graph(nodes, links)
        elif query_button and not method_query.strip():
            st.warning("⚠️ 请输入方法名称")


if __name__ == "__main__":
    main()
