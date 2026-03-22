---
name: Workflow-Oriented AI Agent Design
description: "When to Use
When the task requires multiple specialized steps.
When intermediate results determine later actions.
When agents need structured hand-off instead of free-form chat.
When bounded retries, state tracking, and failure handling are required."
---

Skill: Workflow-Oriented AI Agent Design

Purpose
To design multi-agent AI systems as explicit, stateful workflows where specialized agents handle planning, generation, evaluation, and storage in a controlled pipeline.

When to Use
When the task requires multiple specialized steps.
When intermediate results determine later actions.
When agents need structured hand-off instead of free-form chat.
When bounded retries, state tracking, and failure handling are required.

Procedure
1. Define specialized agents with clear inputs/outputs.
2. Model the system as workflow nodes, not open-ended conversation.
3. Use explicit shared state to track progress, retries, and results.
4. Add guardrails for invalid outputs, weak evidence, and retry limits.
5. Use reviewer/evaluator agents to decide pass, retry, or fail.

Patterns
- Planner → Generator → Evaluator
- Extractor → Planner → Generator → Reviewer → Storage
- Router → Specialist Agent → Reviewer

State
Track:
- current_step
- intermediate_outputs
- retry_count
- final_status

Constraints
- no infinite loops
- bounded retries only
- structured outputs only
- failures must be visible
- preserve hand-off clarity

Expected Output
A robust workflow-based multi-agent system with clear responsibilities, safe retries, and explicit state transitions.