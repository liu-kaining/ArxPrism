#### 1. 数据库交互规范 (Neo4j Cypher Rules)
* **绝对禁止 `CREATE` 泛滥**：所有节点的插入必须使用 `MERGE`，以 `arxiv_id`（对于论文）或 `name`（对于方法/数据集）作为唯一合并键。
* **示例强制约束**：
    * *错误写法*：`CREATE (p:Paper {id: $id})`
    * *正确写法*：`MERGE (p:Paper {arxiv_id: $id}) ON CREATE SET p.title = $title, p.published_date = $date`
* **边（关系）的幂等性**：使用 `MERGE (a)-[r:IMPROVES_UPON]->(b)`，避免多次运行脚本产生重复连线。

#### 2. 数据流与错误处理 (Data Flow & Error Handling)
* **解析失败熔断**：如果在解析 arXiv HTML 时遇到 `requests.exceptions.Timeout` 或解析出的文本长度小于 500 字符（说明可能是无效页面或反爬拦截），必须记录 `logger.error` 并**跳过该篇，绝不能中断整个 Batch 任务**。
* **LLM 响应验证**：调用大模型后，必须使用 `PaperExtraction.model_validate_json(response_string)` 进行解析。如果抛出 `ValidationError`，捕获异常并实施指数退避重试（Exponential Backoff，最大 3 次）。

#### 3. 爬虫与 API 速率限制 (Rate Limiting)
* **arXiv API 规则**：请求之间强制增加 `time.sleep(3)`。遵守官方君子协定。
* **LLM API 并发**：由于结构化抽取极度消耗 Token，必须在 Celery 任务中控制并发数（Concurrency），或者使用 `asyncio.Semaphore` 限制同时发往 OpenAI/Gemini 的请求量（例如最多同时 5 个），防止触发 `429 Too Many Requests` 导致大面积失败。

#### 4. 核心数据结构精化 (Data Models Details)
* 在 `ARCHITECTURE.md` 中我们定义了大致的 Pydantic 模型。在这里要明确字段约束。
    * 例如：`published_date` 必须验证是否符合 `YYYY-MM-DD` 格式。
    * 例如：`is_relevant_to_domain` 必须提供默认值 `False`（防御性设计，宁可漏杀，不可错放无效数据污染图谱）。
