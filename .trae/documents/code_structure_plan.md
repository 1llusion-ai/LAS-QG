# 代码结构重构计划

## 当前问题分析

```
src/
├── agents/              # Agent 相关
│   ├── planning_agent.py    # PlanningAgent + GenerationAgent
│   ├── extraction_agent.py  # ExtractionAgent + EvaluationAgent
│   ├── question_agent.py    # 主 Agent (LangGraph)
│   ├── state.py             # Agent State
│   └── tools.py             # Agent Tools
│
├── generation/          # 问题生成相关
│   ├── llm_client.py        # LLM 客户端
│   ├── prompts.py           # Prompts
│   └── generator.py         # 空实现
│
├── kg/                   # 知识图谱相关
│   ├── neo4j_client.py      # Neo4j 客户端
│   ├── rule_extractor.py    # 规则抽取
│   ├── kg_builder.py        # 未使用
│   └── txt_parser.py        # 未使用
│
├── workflow/             # 工作流相关
│   ├── orchestrator.py      # 被 Agent 替代
│   └── state.py             # 与 agents/state.py 重复
│
├── evaluation/           # 评估相关
│   └── evaluator.py         # 空实现
│
├── planning/             # 规划相关
│   └── planner.py           # 未使用
│
├── cleaner/              # 文本清洗
├── parsers/              # 文档解析
├── storage/              # 存储
└── schemas/              # 数据模型
```

**问题**:
1. 职责分散：LLM 客户端在 `generation/`，Neo4j 在 `kg/`
2. 重复代码：`workflow/state.py` 和 `agents/state.py`
3. 空实现：`generator.py`, `evaluator.py`, `planner.py`
4. 未使用：`kg_builder.py`, `txt_parser.py`

## 新的代码框架

```
src/
├── core/                      # 核心基础设施
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   ├── llm.py                 # LLM 客户端
│   └── neo4j_client.py        # Neo4j 客户端
│
├── agents/                    # Agent 框架
│   ├── __init__.py
│   ├── state.py               # Agent State
│   ├── tools.py               # Agent Tools
│   ├── prompts.py             # Agent Prompts
│   └── question_agent.py      # 主 Agent
│
├── schemas/                   # 数据模型
│   ├── __init__.py
│   └── types.py               # Pydantic 模型
│
├── pipeline/                  # 数据处理流水线
│   ├── __init__.py
│   ├── parser.py              # 文档解析
│   ├── cleaner.py             # 文本清洗
│   ├── chunker.py             # 文本分块
│   └── extractor.py           # KG 抽取
│
└── storage/                   # 存储层
    ├── __init__.py
    └── database.py            # SQLite
```

## 文件迁移清单

| 原文件 | 新文件 | 操作 |
|--------|--------|------|
| `config.py` | `core/config.py` | 移动 |
| `generation/llm_client.py` | `core/llm.py` | 移动 |
| `kg/neo4j_client.py` | `core/neo4j_client.py` | 移动 |
| `agents/state.py` | `agents/state.py` | 保持 |
| `agents/tools.py` | `agents/tools.py` | 保持 |
| `generation/prompts.py` | `agents/prompts.py` | 移动 |
| `agents/question_agent.py` | `agents/question_agent.py` | 保持 |
| `agents/planning_agent.py` | 删除 | 合并到 question_agent |
| `agents/extraction_agent.py` | 删除 | 合并到 pipeline/extractor |
| `parsers/document_parser.py` | `pipeline/parser.py` | 移动 |
| `cleaner/text_cleaner.py` | `pipeline/cleaner.py` | 移动 |
| `cleaner/text_chunker.py` | `pipeline/chunker.py` | 移动 |
| `kg/rule_extractor.py` | `pipeline/extractor.py` | 移动 |
| `kg/kg_builder.py` | 删除 | 未使用 |
| `kg/txt_parser.py` | 删除 | 未使用 |
| `workflow/orchestrator.py` | 删除 | 被 Agent 替代 |
| `workflow/state.py` | 删除 | 重复 |
| `generation/generator.py` | 删除 | 空实现 |
| `evaluation/evaluator.py` | 删除 | 空实现 |
| `planning/planner.py` | 删除 | 未使用 |

## 核心模块设计

### 1. `core/` - 基础设施

```python
# core/__init__.py
from src.core.config import get_config, AppConfig
from src.core.llm import get_llm, BaseLLM
from src.core.neo4j_client import get_neo4j_client, Neo4jClient

# core/config.py - 配置管理
class LLMConfig(BaseModel): ...
class AppConfig(BaseModel): ...
def get_config() -> AppConfig: ...

# core/llm.py - LLM 客户端
class BaseLLM(ABC): ...
class SiliconFlowClient(BaseLLM): ...
def get_llm(...) -> BaseLLM: ...

# core/neo4j_client.py - Neo4j 客户端
class Neo4jClient: ...
def get_neo4j_client(...) -> Neo4jClient: ...
```

### 2. `agents/` - Agent 框架

```python
# agents/__init__.py
from src.agents.state import QuestionAgentState, AgentStep
from src.agents.tools import get_all_tools
from src.agents.prompts import SYSTEM_PROMPT
from src.agents.question_agent import QuestionAgent, create_question_agent

# agents/state.py - 状态定义
class AgentStep(str, Enum): ...
class QuestionAgentState(TypedDict): ...

# agents/tools.py - 四个工具
@tool def retrieve_chunks(...): ...
@tool def retrieve_subgraph(...): ...
@tool def generate_questions(...): ...
@tool def evaluate_questions(...): ...

# agents/prompts.py - Prompts
SYSTEM_PROMPT = "..."
EXTRACTION_PROMPT = "..."
QUESTION_GENERATION_PROMPT = "..."
QUESTION_EVALUATION_PROMPT = "..."

# agents/question_agent.py - 主 Agent
class QuestionAgent:
    def __init__(self, llm, neo4j_client, max_iterations): ...
    def run(self, user_query, difficulty, question_type) -> dict: ...
```

### 3. `schemas/` - 数据模型

```python
# schemas/types.py
class DocumentStatus(str, Enum): ...
class DifficultyLevel(str, Enum): ...
class Document(BaseModel): ...
class DocumentChunk(BaseModel): ...
class Rule(BaseModel): ...
class RuleKnowledgeGraph(BaseModel): ...
class GeneratedQuestion(BaseModel): ...
class QuestionEvaluation(BaseModel): ...
class QuestionBankItem(BaseModel): ...
```

### 4. `pipeline/` - 数据处理流水线

```python
# pipeline/__init__.py
from src.pipeline.parser import parse_document
from src.pipeline.cleaner import clean_text
from src.pipeline.chunker import chunk_document
from src.pipeline.extractor import extract_rules

# pipeline/parser.py - 文档解析
def parse_document(file_path: str) -> Document: ...

# pipeline/cleaner.py - 文本清洗
def clean_text(content: str) -> str: ...

# pipeline/chunker.py - 文本分块
def chunk_document(document: Document) -> list[DocumentChunk]: ...

# pipeline/extractor.py - KG 抽取
def extract_rules(chunks: list[DocumentChunk], llm) -> RuleKnowledgeGraph: ...
```

### 5. `storage/` - 存储层

```python
# storage/database.py
class Database:
    def save_question(...): ...
    def get_questions(...): ...
```

## 使用示例

```python
# 简单使用 - Agent 生成问题
from src.agents import create_question_agent
from src.core import get_llm, get_neo4j_client

llm = get_llm()
neo4j = get_neo4j_client()
agent = create_question_agent(llm=llm, neo4j_client=neo4j)

result = agent.run(
    user_query="生成一道关于无人机飞行高度的选择题",
    difficulty="medium"
)

# Pipeline 使用 - 处理文档
from src.pipeline import parse_document, clean_text, chunk_document, extract_rules
from src.core import get_llm

doc = parse_document("document.docx")
cleaned = clean_text(doc.content)
chunks = chunk_document(doc)
rules = extract_rules(chunks, llm=get_llm())
```

## 实施步骤

### 第一阶段：创建新目录结构

1. 创建 `core/` 目录
2. 创建 `pipeline/` 目录

### 第二阶段：移动核心文件

1. 移动 `config.py` → `core/config.py`
2. 移动 `generation/llm_client.py` → `core/llm.py`
3. 移动 `kg/neo4j_client.py` → `core/neo4j_client.py`
4. 移动 `generation/prompts.py` → `agents/prompts.py`

### 第三阶段：移动 Pipeline 文件

1. 移动 `parsers/document_parser.py` → `pipeline/parser.py`
2. 移动 `cleaner/text_cleaner.py` → `pipeline/cleaner.py`
3. 移动 `cleaner/text_chunker.py` → `pipeline/chunker.py`
4. 移动 `kg/rule_extractor.py` → `pipeline/extractor.py`

### 第四阶段：清理冗余文件

1. 删除 `workflow/` 目录
2. 删除 `generation/` 目录（保留 llm.py 已移动）
3. 删除 `evaluation/` 目录
4. 删除 `planning/` 目录
5. 删除 `kg/kg_builder.py`, `kg/txt_parser.py`

### 第五阶段：更新导入

1. 更新所有 `__init__.py`
2. 更新 `app.py` 中的导入
3. 更新测试文件中的导入

## 优势

1. **职责清晰**: 每个目录有明确的单一职责
2. **依赖简单**: `agents` → `core` → `schemas`
3. **易于扩展**: 新增功能只需在对应目录添加
4. **易于测试**: 每个模块独立可测
5. **减少冗余**: 删除空实现和重复代码

## 最终结构

```
src/
├── core/           # 3 文件
│   ├── config.py
│   ├── llm.py
│   └── neo4j_client.py
│
├── agents/         # 5 文件
│   ├── state.py
│   ├── tools.py
│   ├── prompts.py
│   └── question_agent.py
│
├── schemas/        # 1 文件
│   └── types.py
│
├── pipeline/       # 4 文件
│   ├── parser.py
│   ├── cleaner.py
│   ├── chunker.py
│   └── extractor.py
│
└── storage/        # 1 文件
    └── database.py
```

总计：14 个核心文件，结构清晰，职责分明。
