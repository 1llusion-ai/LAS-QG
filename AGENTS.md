# AGENTS.md

## Repository Purpose

This repository is a lightweight demo for low-altitude safety question generation.

The goal is to validate the end-to-end workflow:
document -> cleaning -> KG extraction -> question generation -> evaluation.

This repository is not intended to be a full production system yet.

***

## How to Work in This Repository

When adding or modifying code, always optimize for:

1. runnable local demo
2. clear modular structure
3. easy future extension
4. minimal unnecessary complexity

Prefer explicit implementations over framework-heavy abstractions.

***

## What Matters Most

The most important parts of this project are:

- document parsing and cleaning
- lightweight KG extraction with LLM
- Neo4j knowledge graph storage with vector search
- LangGraph Agent for question generation
- difficulty-aware question generation with multi-hop reasoning
- question evaluation
- bounded workflow fallback

These parts should remain easy to inspect and modify.

***

## What to Avoid

Do not:

- redesign the whole stack
- introduce heavy backend frameworks
- introduce distributed systems
- turn the app into a chat-first system
- add authentication or account systems
- add complex deployment infrastructure
- hide core logic behind excessive wrappers

***

## Expected Project Shape

This project should stay close to this shape:

```
src/
├── core/           # 核心基础设施
│   ├── config.py   # 配置管理
│   ├── llm.py      # LLM 客户端
│   └── neo4j_client.py  # Neo4j 客户端
│
├── agents/         # Agent 框架
│   ├── state.py    # Agent State
│   ├── tools.py    # Agent Tools
│   ├── prompts.py  # Prompts
│   └── question_agent.py  # 主 Agent (LangGraph)
│
├── pipeline/       # 数据处理流水线
│   ├── parser.py   # 文档解析
│   ├── cleaner.py  # 文本清洗
│   ├── chunker.py  # 文本分块
│   └── extractor.py # KG 抽取
│
└── schemas/        # 数据模型
    └── types.py    # Pydantic 模型
```

Tech stack:
- Streamlit for UI
- LangGraph for Agent orchestration
- Neo4j for KG storage + vector search + BM25
- Pydantic schemas for structured data
- local files for uploads and outputs

***

## Implementation Preference

When there is multiple valid ways to implement something:

- choose the simpler one
- choose the one with fewer moving parts
- choose the one that is easier to debug
- choose the one that preserves future extensibility

***

## Workflow Behavior

The workflow must:

- be explicit
- be bounded
- return structured status
- never hang
- never retry forever

Failures should be visible and understandable.

***

## File Organization Principle

Keep business logic out of UI files.
Keep storage logic out of workflow files.
Keep parsing logic separate from KG logic.
Keep prompts centralized in `agents/prompts.py`.
Keep schemas explicit in `schemas/types.py`.

***

## Knowledge Graph Architecture

### Neo4j Schema

```
Node Types:
- Chunk: chunk_key, chunk_id, doc_title, article, source_text, embedding
- Entity: name

Relationship Types:
- MENTIONS: Chunk -> Entity (原文引用实体)
- RELATION: Entity -> Entity (实体关系: relation_text, doc_title, article, chunk_id)
```

### KG Retrieval Flow

```
用户查询
    ↓
LLM embedding (query)
    ↓
Neo4j Vector Index search (Chunk.embedding)
    ↓
定位最相关的 Chunk
    ↓
通过 MENTIONS 边扩展到 Entity
    ↓
通过 RELATION 边扩展多跳子图
    ↓
返回子图用于问题生成
```

### Search Methods

| 方法 | 实现 | 用途 |
|------|------|------|
| 向量搜索 | `db.index.vector.queryNodes` | 语义相似度搜索 |
| BM25 搜索 | `db.index.fulltext.queryNodes` | 关键词相关性搜索 |

### Key Files

| File | Purpose |
|------|---------|
| `src/core/neo4j_client.py` | Neo4j CRUD + vector search + BM25 |
| `src/pipeline/extractor.py` | LLM extraction prompt + parser |
| `src/agents/question_agent.py` | LangGraph Agent for question generation |
| `src/agents/tools.py` | Agent tools |
| `src/agents/prompts.py` | All prompts centralized |

***

## Agent Architecture

### Question Agent (LangGraph)

```
用户请求
    ↓
Agent Node (LLM 决策)
    ↓
Tool Node (执行工具)
    ↓
Router (检查问题数量)
    ↓
继续/结束
```

### Agent Tools

| Tool | Input | Output |
|------|-------|--------|
| `retrieve_chunks` | query, mode, top_k | 相关 chunk 列表 |
| `retrieve_subgraph` | chunk_key, hops | 局部子图 |
| `generate_questions` | subgraph, question_type, difficulty | 生成的问题 |
| `evaluate_questions` | question, requirements | 评估结果 |

### Agent State

```python
class QuestionAgentState(TypedDict):
    user_query: str
    current_step: AgentStep
    chunks: list[dict]
    subgraph: dict
    questions: list[dict]
    current_question: Optional[dict]
    evaluation: Optional[dict]
    difficulty: str
    question_type: str
    num_questions: int
    error: Optional[str]
    messages: Annotated[list, add_messages]
    iteration_count: int
    max_iterations: int
```

### Default Settings

| 参数 | 默认值 |
|------|--------|
| 难度 | hard |
| 题目数量 | 1 |
| 题目类型 | choice |

### Difficulty & Hops Mapping

| 难度 | Hops 跳数 | 说明 |
|------|-----------|------|
| easy | 1 | 简单关系 |
| medium | 2 | 中等复杂度 |
| hard | 3 | 复杂多跳推理 |

***

## Extension Guidance

Future versions may later add:

- richer KG selection with sub-graph expansion
- better difficulty control
- stronger evaluation
- improved question bank storage
- API layer

Current code should not block those future upgrades.
