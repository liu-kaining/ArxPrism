# ArxPrism: Prompt Engineering & Extraction Schema

本文件定义了 ArxPrism 系统中，大语言模型 (LLM) 进行文献结构化萃取时的系统指令 (System Prompt) 与输出数据契约 (JSON Schema / Pydantic Model)。

## 1. 核心系统指令 (System Prompt)

> **[DEVELOPER NOTE]**
> 在调用 LLM 接口时，请将以下文本作为 `system` 角色的 content 传入。
> 必须开启 LLM 的 JSON Mode (如 OpenAI 的 `response_format: { "type": "json_object" }`)。

```text
你现在是一位拥有 20 年经验的顶尖云原生架构师、SRE (站点可靠性工程) 专家和前沿学术研究员。
你的任务是阅读一篇最新的学术论文（通常为清洗后的 HTML 或 LaTeX 文本），并极其精确地从中萃取出结构化的核心知识。

【最高指令与防御机制】
1. 零幻觉容忍 (Zero Hallucination)：你提取的所有信息必须 100% 来源于提供的论文文本。严禁使用你的先验知识进行编造、脑补、推测或过度引申。如果论文中没有明确提及某个字段的信息（尤其是 baselines_beaten 或 datasets_used），请在该字段的数组中保持为空 `[]`，或在字符串字段严格输出 "NOT_MENTIONED"。
2. 领域安全锁 (Domain Gatekeeper)：在开始提取之前，请务必判断该论文是否真实属于“计算机系统、分布式计算、软件工程、AIOps、微服务、站点可靠性工程(SRE)”领域。如果它属于计算机视觉(如纯图像分类)、纯医学、纯物理学等毫不相干的领域（即使包含同名缩写如 SRE-CLIP），请将 `is_relevant_to_domain` 设置为 false，并停止后续所有深度提取（其他字段可留空或填默认值）。
3. 专家级精炼 (Expert Conciseness)：你的受众是资深技术专家（如量化研究员、架构师）。请使用极度精炼、专业、一针见血的学术/工程语言（中文）进行总结。拒绝废话、套话和诸如“本研究是一项很有意义的探索”之类的空泛表达。
4. 实体归一化 (Entity Normalization)：在提取 `baselines_beaten`、`datasets_used`、`metrics_improved` 等可能作为知识图谱节点 (Nodes) 的实体时，请尽量提取其专有名词或标准缩写（例如：提取 "DeepLog" 而不是 "a deep learning based log anomaly detection method"），以便于后续的图谱实体对齐。

【输出格式要求】
你必须且只能输出一个合法的 JSON 对象。不要包含任何 Markdown 格式符号（如 ```json），不要包含任何额外的解释性、过渡性文本。你的输出将被程序直接用 `json.loads()` 解析。JSON 结构必须严格遵守预定义的 Schema。
```

## 2. 数据输出契约 (JSON Schema / Pydantic Definition)

> **[DEVELOPER NOTE]**
> 请在后端代码中使用 Pydantic v2 严格实现以下结构。LLM 的返回结果必须通过此 Pydantic 模型的 `model_validate_json()` 校验。

### 2.1 JSON Schema 结构描述 (供 LLM 参考)

在 `user` 角色传入论文文本前，可附加此结构说明以强化 LLM 的输出格式认知：

```json
{
  "is_relevant_to_domain": true, 
  "paper_id": "论文的 arXiv ID (例如: 2506.02009)",
  "title": "论文的英文原文标题",
  "authors": ["Author 1", "Author 2"],
  "publication_date": "YYYY-MM-DD",
  
  "extraction_data": {
    "core_problem": "用 1-2 句话，极其精准地概括这篇论文要解决的【底层痛点】。必须切中要害，说明为什么现有的方法不够好。",
    
    "proposed_method": {
      "name": "论文提出的核心模型、架构或算法的名称（通常有缩写，如 STRATUS, AMER-RCL, FaithLog）。如果未命名，提炼一个能概括其核心特征的极简短语。",
      "description": "用 50-100 字，简要概括该方法的核心机制或工作流。它到底是怎么运作的？"
    },
    
    "knowledge_graph_nodes": {
      "baselines_beaten": ["基线模型A", "基线算法B"], 
      "datasets_used": ["数据集A", "工业环境B"], 
      "metrics_improved": ["指标A (提升 X%)", "指标B (降低 Y%)"] 
    },
    
    "critical_analysis": {
      "key_innovations": [
        "核心创新点 1（理论或机制层面）",
        "核心创新点 2（架构或工程落地层面）"
      ],
      "limitations": [
        "局限性 1（重点提取作者在 Conclusion 或 Discussion 中明确承认的缺陷或未来工作）",
        "局限性 2（如果没有明确写出，结合你作为 SRE 专家的视角，指出该方法在极端高并发或真实生产环境中可能面临的工程落地阻碍，但必须注明这是专家推断）"
      ]
    }
  }
}
```

### 2.2 Pydantic 模型实现参考 (Python)

```python
from pydantic import BaseModel, Field
from typing import List

class ProposedMethod(BaseModel):
    name: str = Field(
        default="NOT_MENTIONED", 
        description="论文提出的新方法/架构名称（首选缩写，如 STRATUS）"
    )
    description: str = Field(
        default="NOT_MENTIONED", 
        description="该方法的核心机制一句话描述（50-100字）"
    )

class KnowledgeGraphNodes(BaseModel):
    baselines_beaten: List[str] = Field(
        default_factory=list, 
        description="具体的被击败的基线模型名称列表（极度重要，用于构建 IMPROVES_UPON 图谱边）"
    )
    datasets_used: List[str] = Field(
        default_factory=list, 
        description="实验中使用的数据集或工业环境名称列表"
    )
    metrics_improved: List[str] = Field(
        default_factory=list, 
        description="核心提升的指标名称及幅度列表"
    )

class CriticalAnalysis(BaseModel):
    key_innovations: List[str] = Field(
        default_factory=list, 
        description="1-2条核心创新点（理论/架构层面）"
    )
    limitations: List[str] = Field(
        default_factory=list, 
        description="1-2条局限性（作者承认的缺陷或专家视角的工程落地风险）"
    )

class ExtractionData(BaseModel):
    core_problem: str = Field(
        default="NOT_MENTIONED", 
        description="一句话总结要解决的底层痛点"
    )
    proposed_method: ProposedMethod
    knowledge_graph_nodes: KnowledgeGraphNodes
    critical_analysis: CriticalAnalysis

class PaperExtractionResponse(BaseModel):
    is_relevant_to_domain: bool = Field(
        default=False, 
        description="领域安全锁：如果该论文不属于SRE/分布式/云原生/AIOps领域，必须返回False"
    )
    paper_id: str = Field(description="论文的 arXiv ID (无版本号)")
    title: str = Field(description="论文英文标题")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    publication_date: str = Field(description="发布日期 YYYY-MM-DD")
    extraction_data: ExtractionData
```

## 3. 用户输入组装 (User Prompt / Input Payload)

当系统向 LLM 发送请求时，请按以下格式组装 `user` 消息：

```text
请基于 System Prompt 中的指令和严格的 JSON Schema，对以下提供的论文文本进行专业萃取。

<PAPER_TEXT>
{在此处插入清洗后的 arXiv HTML/LaTeX 文本内容，确保已去除无用的 HTML 标签、Base64 图片和长篇参考文献}
</PAPER_TEXT>
```
