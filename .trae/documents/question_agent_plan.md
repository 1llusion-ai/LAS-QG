# Agent 部分实现计划

## 概述

基于 LangGraph 实现一个智能 Agent，负责理解用户需求、决定下一步动作、调用工具。Agent 将使用 ReAct 模式（Reasoning + Acting），通过 state、tools 和路由来协调问题生成流程。

## 架构设计

```
用户请求
    ↓
Agent (理解需求 + 决策)
    ↓
Tool 调用 (retrieve_chunks / retrieve_subgraph / generate_questions / evaluate_questions)
    ↓
路由决策
    ↓
继续/结束
```

## 文件结构

```
src/agents/
├── __init__.py              # 更新导出
├── planning_agent.py        # 现有文件，保持不变
├── extraction_agent.py      # 现有文件，保持不变
├── question_agent.py        # 新建：主 Agent 实现
├── tools.py                 # 新建：四个 Tool 定义
└── state.py                 # 新建：Agent State 定义
```

## 实现步骤

### 步骤 1：定义 Agent State

**文件**: `src/agents/state.py`

定义 `QuestionAgentState`，包含：
- `user_query`: 用户原始请求
- `current_step`: 当前步骤 (retrieve/generate/evaluate/complete)
- `chunks`: 检索到的 chunks
- `subgraph`: 检索到的子图
- `questions`: 生成的问题列表
- `evaluation`: 评估结果
- `difficulty`: 难度级别
- `question_type`: 题型
- `error`: 错误信息
- `messages`: 对话历史（用于 LLM 决策）

### 步骤 2：定义四个 Tools

**文件**: `src/agents/tools.py`

#### Tool 1: `retrieve_chunks`
- **输入**: query (str), mode (str: "vector" | "keyword")
- **输出**: 相关 chunk 列表
- **实现**: 调用 `Neo4jClient.similarity_search()` 或关键词搜索

#### Tool 2: `retrieve_subgraph`
- **输入**: chunk_key (str) 或 entity_names (list[str])
- **输出**: 局部子图（entities + relations）
- **实现**: 调用 `Neo4jClient.expand_subgraph()` 或实体扩展查询

#### Tool 3: `generate_questions`
- **输入**: context (str), question_type (str), difficulty (str)
- **输出**: 生成的问题
- **实现**: 调用 LLM 生成问题，基于检索到的上下文

#### Tool 4: `evaluate_questions`
- **输入**: question (GeneratedQuestion), requirements (dict)
- **输出**: 评估结果（is_approved, issues, suggested_action）
- **实现**: 调用 LLM 评估问题质量

### 步骤 3：实现主 Agent

**文件**: `src/agents/question_agent.py`

使用 LangGraph 构建 Agent Graph：

```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
```

**节点设计**:
1. `agent_node`: LLM 决策节点，决定调用哪个 tool
2. `tool_node`: 执行 tool 调用
3. `should_continue`: 路由函数，决定是否继续

**流程**:
```
START → agent_node → tool_node → agent_node → ... → END
                      ↓
              (条件路由)
```

### 步骤 4：定义路由逻辑

路由函数根据 state 决定下一步：
- 如果 `current_step == "complete"` → 结束
- 如果 `error` 存在 → 结束并返回错误
- 否则 → 继续调用 agent_node

### 步骤 5：集成现有模块

- 复用 `Neo4jClient` 进行向量搜索和子图扩展
- 复用 `BaseLLM` 进行 LLM 调用
- 复用 `GeneratedQuestion`、`QuestionEvaluation` 等数据类型

## 详细实现

### 1. Agent State 定义

```python
from typing import TypedDict, Optional, Annotated
from langchain_core.messages import BaseMessage

class QuestionAgentState(TypedDict):
    user_query: str
    current_step: str
    chunks: list[dict]
    subgraph: dict
    questions: list[dict]
    evaluation: Optional[dict]
    difficulty: str
    question_type: str
    error: Optional[str]
    messages: Annotated[list[BaseMessage], "add_messages"]
    iteration_count: int
```

### 2. Tools 定义

每个 Tool 使用 `@tool` 装饰器：

```python
from langchain_core.tools import tool

@tool
def retrieve_chunks(query: str, mode: str = "vector") -> list[dict]:
    """检索相关文档块"""
    ...

@tool
def retrieve_subgraph(chunk_key: str = None, entity_names: list[str] = None) -> dict:
    """检索局部子图"""
    ...

@tool
def generate_questions(context: str, question_type: str, difficulty: str) -> dict:
    """生成问题"""
    ...

@tool
def evaluate_questions(question: dict, requirements: dict) -> dict:
    """评估问题质量"""
    ...
```

### 3. Agent Graph 构建

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage

def create_question_agent(llm, neo4j_client):
    tools = [
        retrieve_chunks,
        retrieve_subgraph,
        generate_questions,
        evaluate_questions,
    ]
    
    llm_with_tools = llm.bind_tools(tools)
    
    def agent_node(state: QuestionAgentState) -> QuestionAgentState:
        # LLM 决策
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
    
    def should_continue(state: QuestionAgentState) -> str:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END
    
    workflow = StateGraph(QuestionAgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

### 4. System Prompt

Agent 的系统提示词：

```
你是一个低空安全题库生成助手。你的任务是：
1. 理解用户的问题生成需求
2. 使用可用工具检索相关知识和上下文
3. 生成符合要求的问题
4. 评估问题质量

可用工具：
- retrieve_chunks: 检索相关文档块
- retrieve_subgraph: 检索知识图谱子图
- generate_questions: 生成问题
- evaluate_questions: 评估问题质量

工作流程：
1. 首先使用 retrieve_chunks 检索相关内容
2. 使用 retrieve_subgraph 获取知识图谱上下文
3. 使用 generate_questions 生成问题
4. 使用 evaluate_questions 评估问题
5. 如果评估不通过，可以重新生成或调整

请根据用户需求，逐步调用工具完成任务。
```

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/agents/state.py` | 新建 | Agent State 定义 |
| `src/agents/tools.py` | 新建 | 四个 Tool 实现 |
| `src/agents/question_agent.py` | 新建 | 主 Agent 实现 |
| `src/agents/__init__.py` | 修改 | 更新导出 |

## 依赖

- `langgraph` - 已在 requirements.txt
- `langchain-core` - 已在 requirements.txt
- 现有模块：`neo4j_client`, `llm_client`, `schemas/types`

## 测试计划

1. 单元测试每个 Tool
2. 测试 Agent 状态流转
3. 测试完整问题生成流程
4. 测试错误处理和边界情况

## 注意事项

1. 保持与现有 workflow 的兼容性
2. 避免重复实现已有功能
3. 确保错误处理完善
4. 保持代码简洁，避免过度抽象
