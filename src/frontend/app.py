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
            timeout=10
        )
        if response.status_code == 202:
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
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {"error": f"未找到方法 '{method_name}'"}
        else:
            return {"error": f"API 返回错误: {response.status_code}"}
    except requests.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}


# =============================================================================
# Custom CSS for Dark Mode
# =============================================================================

st.markdown("""
<style>
    /* Dark Mode Base */
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }

    /* Sidebar Dark Mode */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #58a6ff !important;
    }

    /* Text */
    .stText, .stMarkdown {
        color: #c9d1d9 !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: #238636;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }

    .stButton > button:hover {
        background-color: #2ea043;
    }

    /* Success/Info Boxes */
    .success-box {
        padding: 1rem;
        border-radius: 6px;
        background-color: #238636;
        color: white;
        margin: 0.5rem 0;
    }

    .info-box {
        padding: 1rem;
        border-radius: 6px;
        background-color: #1f6feb;
        color: white;
        margin: 0.5rem 0;
    }

    .warning-box {
        padding: 1rem;
        border-radius: 6px;
        background-color: #d29922;
        color: black;
        margin: 0.5rem 0;
    }

    .error-box {
        padding: 1rem;
        border-radius: 6px;
        background-color: #f85149;
        color: white;
        margin: 0.5rem 0;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #58a6ff !important;
        font-size: 2rem !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background-color: #161b22;
        border-radius: 6px;
    }

    /* Links */
    a {
        color: #58a6ff !important;
    }

    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #238636;
    }
</style>
""", unsafe_allow_html=True)


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

    # =============================================================================
    # Right Main Panel - Graph Visualization
    # =============================================================================

    col1, col2 = st.columns([3, 1])

    with col1:
        st.header("🌳 技术进化树")

        # 查询输入
        method_query = st.text_input(
            "🔍 输入 Method 名称查询进化树",
            placeholder="例如: STRATUS, DeepLog, AMER-RCL",
            help="输入方法名称查找其进化树",
            key="method_query_input"
        )

        # 查询按钮
        query_button = st.button("🔎 查询进化树", use_container_width=False)

    with col2:
        st.markdown("### 📖 使用说明")
        st.info("""
        1. 在左侧启动 ArxPrism 雷达抓取论文
        2. API 会将任务下发到 Celery Worker
        3. Worker 处理后会自动写入 Neo4j
        4. 在此输入方法名称查询其技术进化树
        5. 节点颜色:
           - 🔴 红色: 目标方法
           - 🟢 青色: 祖先 (该方法改进的方法)
           - 🔵 蓝色: 后代 (改进该方法的方法)
        6. 边表示 `IMPROVES_UPON` 关系
        """)

    st.markdown("---")

    # 执行查询
    if query_button and method_query.strip():
        with st.spinner(f"正在查询 '{method_query}' 的进化树..."):
            try:
                result = get_evolution_tree(method_query.strip())

                if "error" in result:
                    st.error(f"❌ 查询失败: {result['error']}")

                elif result.get("code") != 200:
                    st.error(f"❌ API 错误: {result.get('message', 'Unknown error')}")

                elif not result.get("data", {}).get("nodes"):
                    st.warning(f"⚠️ 未找到方法 '{method_query}' 的进化树")
                    st.info("💡 提示: 请确保已运行过流水线并成功写入数据")

                else:
                    # 显示统计
                    data = result["data"]
                    nodes = data.get("nodes", [])
                    links = data.get("links", [])

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

                    # 渲染图
                    if render_evolution_graph(nodes, links):
                        st.success("✅ 进化树渲染成功!")
                    else:
                        st.error("❌ 图渲染失败")

                    # 显示原始数据 (可折叠)
                    with st.expander("📋 原始数据"):
                        st.write("Nodes:")
                        st.json(nodes)
                        st.write("Links:")
                        st.json(links)

            except Exception as e:
                st.error(f"❌ 查询出错: {str(e)}")

    elif query_button and not method_query.strip():
        st.warning("⚠️ 请输入方法名称")

    else:
        # 默认显示
        st.info("👆 在上方输入方法名称并点击「查询进化树」")

        # 示例图展示
        st.markdown("### 📊 示例进化树")
        st.caption("等待数据加载后将显示实际进化树...")

        # 创建示例数据用于展示
        example_nodes = [
            {"id": "target", "name": "STRATUS", "generation": 0},
            {"id": "parent1", "name": "AMER-RCL", "generation": -1},
            {"id": "parent2", "name": "DeepLog", "generation": -2},
            {"id": "child1", "name": "STRATUS-2", "generation": 1},
            {"id": "child2", "name": "STRATUS-3", "generation": 1},
        ]
        example_links = [
            {"source": "parent1", "target": "target"},
            {"source": "parent2", "target": "parent1"},
            {"source": "target", "target": "child1"},
            {"source": "target", "target": "child2"},
        ]

        with st.expander("👀 预览示例进化树结构"):
            st.info("这是示例结构，实际数据将在查询后显示")
            render_evolution_graph(example_nodes, example_links)


if __name__ == "__main__":
    main()
