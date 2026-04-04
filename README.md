# ArxPrism

从 arXiv 论文中自动抽取结构化知识并写入 **Neo4j** 的学术知识图谱流水线，配套 **Next.js** 控制台、**Celery** 异步任务与 **Supabase** 账号体系（JWT + 配额）。

## 能力概览

| 模块 | 说明 |
|------|------|
| 论文管线 | HTML 优先全文 → PDF 兜底 → 摘要兜底；标题+摘要 **LLM 分诊** 后再拉全文 |
| 萃取 | OpenAI 兼容 Chat API + JSON Schema（Pydantic 校验，含字段长度硬顶）；多模型路由（分诊 / 萃取 / 实体对齐）与 Embeddings |
| 图模型 | `Paper`、`Method`、`Task`、`Dataset`、`Author`；**`EVOLVED_FROM`**（技术血脉，带 reason）与 **`IMPROVES_UPON`**（实验对比，带 dataset / metrics） |
| 前端 | 论文检索与详情、指挥台式图谱、**架构演进视图**（`EVOLVED_FROM` 瀑布布局 + 边悬停展示演进原因）；**未登录访问受保护页面会重定向 `/login`** |
| 任务 | 创建 / 列表 / 详情 / 暂停 / 恢复 / 取消 / 重试；可选 Celery Worker |
| 安全与成本 | 写类 API 需 **Bearer JWT**；任务与 legacy `pipeline/trigger` 扣 **Supabase 配额**（配额逻辑在 `src/api/deps_quota.py`）；正文进入 LLM 前有长度截断 |

## 环境要求

- Docker / Docker Compose（推荐一键栈）
- 可访问的 **OpenAI 兼容** LLM 与 Embeddings
- **生产环境**：Supabase 项目（Auth + `profiles` + RPC 配额等，见 `spec/supabase_schema.sql`）

## 快速开始

### 1. 配置

```bash
cp .env.example .env
```

**必填（至少能跑萃取）**

- `LLM_API_KEY`、`LLM_BASE_URL`（如 `https://api.openai.com/v1`）
- 可选：`LLM_TRIAGE_MODEL`、`LLM_EXTRACTOR_MODEL`、`LLM_RESOLUTION_MODEL`、`LLM_EMBEDDING_*`、`LLM_MAX_TOKENS`

**生产 / 多用户 API**

- `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`SUPABASE_JWT_SECRET`
- `NEXT_PUBLIC_SUPABASE_URL`、`NEXT_PUBLIC_SUPABASE_ANON_KEY`（前端）
- `AUTH_DISABLED=false`（**切勿在生产设为 true**）
- **`ENVIRONMENT=production`**：关闭 FastAPI **`/docs`**、**`/redoc`**（开发环境设为 `development` 可开启）
- **`CORS_ORIGINS`**：逗号分隔的浏览器 Origin 列表（须包含前端实际访问地址，**不要使用 `*`**；与 `allow_credentials` 兼容）

**运维**

- `ADMIN_RESET_TOKEN`：保护管理端危险操作（如清空数据）

完整说明见 `.env.example` 内注释。

### 2. 启动

```bash
docker compose up -d --build
# 或: docker-compose up -d --build
```

Compose 中 API 服务会传入 `ENVIRONMENT`、`CORS_ORIGINS`、`LLM_MAX_TOKENS` 等，请与根目录 `.env` 保持一致。

### 3. 访问

| 服务 | 默认地址 |
|------|-----------|
| 前端 | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI / ReDoc | 仅当 **`ENVIRONMENT=development`** 时：`/docs`、`/redoc` |
| Neo4j Browser | http://localhost:7474 |

## 前端路由与登录

Next.js **`middleware.ts`** 会在无 Supabase session 时，将访问 **`/tasks`、`/papers`、`/evolution`、`/admin`、`/graph`**（含子路径）的请求重定向到 **`/login?next=…`**。首页、`/login`、`/auth/*` 等不受此规则拦截。

## 项目结构（节选）

```
ArxPrism/
├── src/
│   ├── main.py              # FastAPI：CORS、按 environment 开关文档
│   ├── api/
│   │   ├── deps_quota.py    # 任务 / pipeline 共用配额（与 router 解耦）
│   │   ├── routes.py        # pipeline、papers、graph …
│   │   ├── task_routes.py
│   │   └── …
│   ├── core/config.py       # Settings：environment、cors_origins、LLM_* …
│   ├── database/neo4j_client.py
│   ├── models/              # Pydantic 契约
│   ├── services/
│   └── worker/tasks.py      # Celery
├── frontend/
│   └── middleware.ts        # 受保护路由 → 登录
├── spec/
├── docker-compose.yml
├── Dockerfile
└── Dockerfile.frontend
```

## 鉴权与 API 约定

- 绝大多数 **`/api/v1/**`** 需要：`Authorization: Bearer <Supabase JWT>`
- 公开接口示例：`GET /health`、`GET /`
- 管理接口：`/api/v1/admin/*`（管理员 JWT 或 `X-ArxPrism-Admin-Token`，见代码）

常用端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/tasks` | 创建抓取任务（扣配额） |
| GET | `/api/v1/tasks` | 任务列表 |
| GET | `/api/v1/tasks/{id}` | 任务详情 |
| POST | `/api/v1/tasks/{id}/pause` 等 | 暂停 / 恢复 / 取消 / 重试 |
| POST | `/api/v1/arxiv/preview-search` | arXiv 元数据预览 |
| POST | `/api/v1/pipeline/trigger` | Legacy 流水线（配额与 `max_results` 有封顶，优先用任务 API） |
| GET | `/api/v1/papers` | 论文列表 / 检索 |
| GET | `/api/v1/papers/{arxiv_id}` | 论文详情 |
| GET | `/api/v1/graph/paper/{arxiv_id}` | 单篇论文邻域子图 |
| GET | `/api/v1/graph/evolution` | 方法进化树（`method_name`） |

## 本地开发（无 Docker 或混合）

**后端**（仓库根目录）：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ENVIRONMENT=development
export CORS_ORIGINS=http://localhost:3000
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

**Celery Worker**（可选）：

```bash
celery -A src.worker.tasks worker --loglevel=info
```

## 技术栈

- **后端**：FastAPI、Celery、Pydantic v2、httpx、Neo4j Python Driver
- **数据**：Neo4j 5.x、Redis
- **前端**：Next.js、React、Tailwind CSS、Zustand、React Flow
- **身份与配额**：Supabase Auth + PostgreSQL（profiles / RPC）

## 许可证

见仓库根目录 `LICENSE`。
