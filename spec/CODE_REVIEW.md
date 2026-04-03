# ArxPrism Code Review Checklist & Reflection Guide

> **[ATTENTION AI AGENT]**  
> 1. 在你完成**任意一次**代码编写或修改后，必须严格对照下方 **§1–§5** 进行**自我反思 (Self-Review)**。  
> 2. 在向人类汇报「已完成」之前，必须在对话中**逐条说明**如何满足清单；不满足则先改代码再汇报。  
> 3. **每次合并/推送前**：在本文档 **§6 审查记录** 中**追加一条**新记录（日期、变更范围、§1–§5 勾选结论与备注）。不得省略；无记录则视为未做 Code Review。

## 6. 审查记录（每次变更后追加）

| 日期 (UTC+8) | 变更范围（路径或主题） | §1 | §2 | §3 | §4 | §5 | 备注 |
|--------------|------------------------|----|----|----|----|-----|------|
| 2026-04-03 | Pydantic `extraction_data` 可选；`arxiv_radar` 参考文献切除；Neo4j Author 键策略、`IMPROVES_UPON` 边属性；worker/run_local 空萃取防护；`api/__init__` 文档 | ✅ | ✅ | ✅ | ✅ | ✅ | 见下「2026-04-03 详表」 |
| 2026-04-04 | LLM 分诊 `TriageResponse`/`triage_paper`；Radar HTML-First；`ExtractionData.task_name` + Neo4j `Task`、`ADDRESSES`、`APPLIED_TO` | ✅ | ✅ | ✅ | ✅ | ✅ | 分诊失败 fail-open；Task 仍 MERGE+参数化 |
| 2026-04-04 | `get_paper_by_id` / `search_papers` 透出 `Task`；前端 `Paper` 类型增加 `task_name/tasks` | ✅ | ✅ | ✅ | ✅ | ✅ | `get_paper_graph` 已是 `(p)-[r]-(connected)`，Task 自动返回 |

### 2026-04-03 详表（对照 §1–§5）

- **§1 数据库安全与幂等性**  
  - 仍为 `MERGE` + 参数化 `$...`，未引入 f-string 拼 Cypher。  
  - Paper 以 `arxiv_id`；Method/Dataset/Metric/Baseline 等仍用 `_normalize_name` 后 `name`。  
  - **Author 有意例外**：合并键为 `strip().lower()`，**不**调用 `_normalize_name`，避免「Y. Li / Ying Li」被压成同一节点（`neo4j_client._upsert_transaction`）。  
  - `IMPROVES_UPON` 增加 `r.metrics` / `r.datasets`（列表经驱动参数传入，非字符串拼接）。

- **§2 裸机容错**  
  - 本次未改 `settings`/连接重试逻辑；既有 Neo4j 启动重试、Redis 容错仍有效。

- **§3 LLM 与 Pydantic**  
  - `PaperExtractionResponse.extraction_data` 可选后，不相关论文可省略该字段，避免无效重试。  
  - `llm_extractor` 仍 `model_validate_json`，并捕获 `ValidationError` / `JSONDecodeError`；worker 对「相关但无 `extraction_data`」显式失败并打日志。

- **§4 异步 I/O**  
  - 本次改动未在 `async` 路由中新增同步阻塞调用；Neo4j 仍走异步驱动。

- **§5 代码质量**  
  - 新增/修改路径使用类型注解（含 `Optional[ExtractionData]`）；关键分支有 `logger.info`/`warning`。

---

（以下 §1–§5 为**永久检查清单**，每次自检时逐项勾选。）

## 1. 数据库安全与幂等性 (Database & Idempotency) - [致命级别]
- [ ] **拒绝裸写 CREATE**：Neo4j 的 Cypher 语句中，是否使用了 `MERGE` 代替 `CREATE` 来保证多次运行不会产生重复节点/边？
- [ ] **防 Cypher 注入**：是否 100% 使用了参数化查询（Parameterized Queries），而不是使用 Python 的 f-string 拼接变量？
- [ ] **唯一约束**：在处理论文时，是否以 `arxiv_id` 作为唯一标识符？在处理方法/数据集时，是否以 `name` 进行了统一转小写/去首尾空格的归一化处理？
- [ ] **Author 节点（例外）**：`Author` 的合并键应为 **`strip().lower()`**，**勿**对作者名使用 `_normalize_name`（否则会抹掉空格与标点，把不同作者误合并）。若修改 Author 逻辑，须同步更新 §6 审查记录。

## 2. 裸机环境的优雅容错 (Graceful Degradation) - [环境适配]
- [ ] **配置解耦**：代码中绝对不能出现硬编码的 IP、端口或密码。必须通过 `pydantic-settings` 读取环境变量。
- [ ] **依赖服务重连**：考虑到本地裸机环境（如 Neo4j 或 Redis）可能未启动或网络波动，连接数据库的代码是否具有重试机制 (Retry) 或合理的超时时间 (Timeout)？
- [ ] **容灾降级**：如果 Redis 连不上，Celery 任务是否能回退为普通的同步函数调用（方便本地单步 Debug）？

## 3. 大模型与 Pydantic 契约 (LLM & Data Contracts)
- [ ] **模型校验**：LLM 返回的 JSON 字符串，是否立即传递给了 Pydantic 模型的 `model_validate_json()` 方法？
- [ ] **异常捕获**：解析 LLM 响应时，是否捕获了 `ValidationError` 和 `json.JSONDecodeError`？
- [ ] **重试机制**：如果 LLM 输出格式错乱，是否实现了局部重试（如最多重试 3 次），并在彻底失败时记录 `logger.error` 而**不阻断**主程序的运行？

## 4. 异步 I/O 与性能 (Async & Performance)
- [ ] **阻塞排查**：在 FastAPI 的 `async def` 路由中，是否混入了耗时的同步阻塞操作（如直接调用 `requests.get` 或同步的 Neo4j driver）？如果有，是否使用了 `asyncio` 兼容的库（如 `httpx` 或 `neo4j.AsyncGraphDatabase`），或使用线程池抛出？
- [ ] **API 速率限制**：在批量请求 arXiv 或 LLM API 时，是否加入了 `asyncio.sleep()` 或并发信号量（Semaphore）防止触发 429 Too Many Requests？

## 5. 代码质量与可维护性 (Code Quality)
- [ ] **Type Hints**：所有的函数入参和返回值是否都具备完整的 Python 类型注解（Type Hints）？
- [ ] **关键日志**：核心逻辑（抓取成功/失败、大模型调用耗时、写入 Neo4j 节点数）是否输出了清晰的 `logging.info` 或 `logging.error`？
