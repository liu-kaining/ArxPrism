# ArxPrism Code Review Checklist & Reflection Guide

> **[ATTENTION AI AGENT]** > 在你完成任何一个模块（Python 文件或函数）的编写或修改后，必须严格对照本清单进行**自我反思 (Self-Review)**。
> 在你向人类开发者汇报“代码已完成”之前，必须在输出中逐条说明你是如何满足以下规范的。如果发现不满足，请立即自行修改代码。

## 1. 数据库安全与幂等性 (Database & Idempotency) - [致命级别]
- [ ] **拒绝裸写 CREATE**：Neo4j 的 Cypher 语句中，是否使用了 `MERGE` 代替 `CREATE` 来保证多次运行不会产生重复节点/边？
- [ ] **防 Cypher 注入**：是否 100% 使用了参数化查询（Parameterized Queries），而不是使用 Python 的 f-string 拼接变量？
- [ ] **唯一约束**：在处理论文时，是否以 `arxiv_id` 作为唯一标识符？在处理方法/数据集时，是否以 `name` 进行了统一转小写/去首尾空格的归一化处理？

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
