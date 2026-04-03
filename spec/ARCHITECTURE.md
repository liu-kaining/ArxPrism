# 🔮 ArxPrism 核心架构与工程设计白皮书 (v1.0 MVP)

## 1. 总体架构与技术栈选型 (Architecture & Tech Stack)

本系统旨在构建一个高度自动化的学术图谱萃取流水线，目标是从 arXiv 抓取特定领域（MVP阶段为 SRE/云原生/微服务）的最新论文，利用大模型进行结构化降维，并沉淀为图数据库资产。

* **开发语言**: Python 3.11+
* **Web 框架**: FastAPI (要求全异步实现 `async/await`)
* **数据验证与序列化**: Pydantic v2 (极度重要，LLM 的输出必须经过 Pydantic 校验)
* **图数据库**: Neo4j (使用 `neo4j` 官方 Python 驱动，Cypher 查询)
* **任务调度与队列**: Celery + Redis (用于解耦爬虫、大模型请求和数据库写入)
* **大模型调用**: OpenAI SDK (配置 `response_format={ "type": "json_object" }` 强制 JSON 输出)
* **文献获取**: `arxiv` Python 包 + `BeautifulSoup4` (用于解析 HTML 版论文)

---

## 2. 核心系统模块 (Core Modules)

系统由三个松耦合的核心模块组成：

### 模块 A: `Radar` (增量数据雷达)
* **职责**: 定时扫源、去重、下载原始 HTML/LaTeX 文本。
* **幂等性要求**: 每篇抓取到的论文必须先以 `arxiv_id` 去 Neo4j 校验是否已存在。若存在则直接 `SKIP`。
* **清洗规则**: 剔除 HTML 中的 `<style>`, `<script>`, 参考文献列表（References）等无用标签，仅保留正文核心逻辑，控制 Token 消耗。

### 模块 B: `The Distiller` (大模型蒸馏器)
* **职责**: 执行 Prompt Engineering，将非结构化长文本蒸馏为严格的 Pydantic 模型。
* **重试机制**: 如果大模型返回的 JSON 无法被 Pydantic 解析，或者缺少必须字段，需自动重试（最大重试次数 = 3）。

### 模块 C: `RootNode Engine` (图谱构筑引擎)
* **职责**: 将蒸馏后的 JSON 数据转化为 Neo4j 的 Nodes 和 Edges。
* **事务要求**: 节点和边的插入必须是原子操作。
* **防幻觉指令**: **必须使用 `MERGE` 语句而非 `CREATE`**，确保重复运行脚本不会产生多余的节点。

---

## 3. 图数据库模型设计 (Neo4j Graph Schema)

Claude Code 必须严格按照以下实体和关系构建 Cypher 语句。

### 节点 (Nodes)
1.  `Paper` (论文): `{ arxiv_id: String (Unique Index), title: String, published_date: Date, url: String, core_problem: String }`
2.  `Author` (作者): `{ name: String (Unique Index) }`
3.  `Method` (方法/模型): `{ name: String (Unique Index), description: String }`
4.  `Dataset` (数据集): `{ name: String (Unique Index) }`
5.  `Metric` (评估指标): `{ name: String (Unique Index) }`
6.  `Innovation` (创新点): `{ content: String }`
7.  `Limitation` (局限性): `{ content: String }`

### 边 (Relationships / Edges)
1.  `(Paper)-[:WRITTEN_BY]->(Author)`
2.  `(Paper)-[:PROPOSES]->(Method)`
3.  `(Paper)-[:EVALUATED_ON]->(Dataset)`
4.  `(Paper)-[:MEASURES]->(Metric)`（历史数据；v2 萃取不再写入 Metric 节点，指标记在 IMPROVES_UPON 边属性上）
5.  `(Paper)-[:HAS_INNOVATION]->(Innovation)`
6.  `(Paper)-[:HAS_LIMITATION]->(Limitation)`
7.  **`(Method)-[:IMPROVES_UPON]->(Method)`** —— **[核心边]**：由 JSON `knowledge_graph_nodes.comparisons` 展开；边上可含 `dataset`、`metrics_improvement`、`discovered_at`，用于构建技术进化树与实验上下文。

---

## 4. 大模型输出数据契约 (Pydantic Schema)

请让 Claude 基于以下结构定义 Pydantic Model，这将作为 LLM 的输出契约：

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ExperimentComparison(BaseModel):
    baseline_method: str = Field(description="基线方法名称")
    dataset: str = Field(description="数据集或环境")
    metrics_improvement: str = Field(description="指标变化，如 F1 +5%")

class KnowledgeGraphNodes(BaseModel):
    comparisons: List[ExperimentComparison] = Field(description="对比实验列表")

class CriticalAnalysis(BaseModel):
    key_innovations: List[str] = Field(description="1-2条核心创新点")
    limitations: List[str] = Field(description="1-2条局限性或工程落地风险")

class ProposedMethod(BaseModel):
    name: str = Field(description="论文提出的新方法/架构名称")
    description: str = Field(description="该方法的核心机制一句话描述")

class PaperExtraction(BaseModel):
    is_relevant_to_domain: bool = Field(description="如果该论文不属于SRE/分布式/云原生领域，必须返回false")
    reasoning_process: str = Field(description="思维链：实验部分与对比关系的推理")
    core_problem: str = Field(description="一句话总结要解决的底层痛点")
    proposed_method: ProposedMethod
    knowledge_graph_nodes: KnowledgeGraphNodes
    critical_analysis: CriticalAnalysis
```

---

## 5. API 接口定义 (FastAPI Endpoints)

所有接口响应均需包裹在统一的 `{ "code": 200, "message": "success", "data": {} }` 结构中。

### 1. 触发流水线
* **`POST /api/v1/pipeline/trigger`**
* **Payload**: `{ "topic_query": "all:\"site reliability engineering\" OR all:\"microservices root cause\"", "max_results": 10 }`
* **Action**: 将抓取任务丢入 Celery 队列，立即返回 HTTP 202 Accepted 及 `task_id`。

### 2. 查询单篇论文详情图谱
* **`GET /api/v1/graph/paper/{arxiv_id}`**
* **Action**: 返回该论文的所有第一层相邻节点（作者、方法、数据集、局限性）。

### 3. 构建技术进化树 (Evolution Tree) 👑
* **`GET /api/v1/graph/evolution?method_name={name}`**
* **Action**: 寻找指定 Method 节点，顺着 `[:IMPROVES_UPON]` 关系，使用 Cypher 向前溯源 3 层（祖先），向后延展 3 层（后代）。
* **Response**: 返回 D3.js 或 ECharts 格式的 Graph Node/Link 数组。

---

## 6. 给 Claude Code 的系统级纪律指令 (System Directives for AI Agent)

> **[ATTENTION CLAUDE]** 如果你在阅读这份文档以生成代码，请严格遵守以下工程纪律：
> 1. **配置分离**：严禁在代码中硬编码 (Hardcode) OpenAI API Key 或 Neo4j 账号密码。必须使用 `.env` 文件和 `pydantic-settings` 统一管理环境变量。
> 2. **防御性编程**：在解析 arXiv HTML 遇到 `AttributeError` 或大模型 API 超时时，必须捕获异常，将状态写入日志，并允许脚本继续处理下一篇，**绝对不能因为单篇失败导致整个进程崩溃**。
> 3. **Cypher 注入防范**：在将 LLM 提取的内容拼接进 Neo4j 查询时，必须使用参数化查询（Parameterized Queries），防止特殊字符（如单引号）导致 Cypher 语法错误。
> 4. **模块化构建**：请先按顺序实现并测试：数据库连接(DB) -> 数据验证(Pydantic) -> 提示词与大模型调用(LLM) -> 抓取逻辑(Radar) -> 异步任务(Celery) -> Web接口(FastAPI)。

