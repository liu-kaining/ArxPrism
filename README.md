# ArxPrism

🔮 **学术知识图谱萃取流水线** - 从 arXiv 论文中自动抽取结构化知识，构建学术知识图谱。

## 功能特性

- **📡 论文抓取**: 自动从 arXiv 抓取论文，支持领域预设优化搜索相关性
- **🧠 LLM 萃取**: 使用大语言模型从论文中提取结构化知识
- **📊 知识图谱**: 将萃取结果存入 Neo4j 图数据库
- **🌳 技术进化树**: 追溯方法之间的 IMPROVES_UPON 关系
- **⚙️ 任务管理**: 支持任务的创建、暂停、恢复、取消等操作

## 快速开始

### 1. 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入必要的配置
vim .env
```

必需配置：
- `LLM_API_KEY`: 你的 LLM API Key
- `LLM_BASE_URL`: LLM API 地址 (OpenAI 或兼容接口)

### 2. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 3. 访问应用

- **前端**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474

## 项目结构

```
ArxPrism/
├── src/                     # 后端 Python 代码
│   ├── api/                 # API 路由
│   ├── core/                # 配置管理
│   ├── database/            # Neo4j 客户端
│   ├── models/              # Pydantic 数据模型
│   ├── services/            # 业务逻辑服务
│   │   ├── arxiv_radar.py   # 论文抓取
│   │   ├── llm_extractor.py # LLM 萃取
│   │   └── task_manager.py  # 任务管理
│   └── worker/              # Celery 任务
│
├── frontend/                # Next.js 前端
│   └── src/
│       ├── app/              # 页面
│       │   ├── papers/      # 论文列表/详情
│       │   ├── graph/       # 知识图谱
│       │   ├── evolution/   # 进化树
│       │   └── tasks/       # 任务管理
│       └── components/      # React 组件
│
├── docker-compose.yml       # Docker 编排
└── Dockerfile.frontend       # 前端构建
```

## API 文档

### 任务管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/tasks` | 创建任务 |
| GET | `/api/v1/tasks` | 获取任务列表 |
| GET | `/api/v1/tasks/{id}` | 获取任务详情 |
| POST | `/api/v1/tasks/{id}/pause` | 暂停任务 |
| POST | `/api/v1/tasks/{id}/resume` | 恢复任务 |
| POST | `/api/v1/tasks/{id}/cancel` | 取消任务 |

### 论文与图谱

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/papers` | 搜索论文 |
| GET | `/api/v1/papers/{arxiv_id}` | 获取论文详情 |
| GET | `/api/v1/graph/paper/{arxiv_id}` | 获取论文图谱 |
| GET | `/api/v1/graph/evolution` | 获取方法进化树 |

## 领域预设

系统支持以下领域预设，可显著提高搜索相关性：

- **SRE**: 站点可靠性工程
- **AIOps**: 智能运维
- **Microservices**: 微服务架构
- **Distributed**: 分布式系统
- **CloudNative**: 云原生

## 本地开发

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn src.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 技术栈

- **后端**: FastAPI, Celery, Pydantic
- **数据库**: Neo4j, Redis
- **前端**: Next.js 14, React, TailwindCSS, Zustand
- **图谱可视化**: React Flow, D3.js
