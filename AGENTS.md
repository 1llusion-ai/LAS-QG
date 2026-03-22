# AGENT.md

## Repository Purpose

This repository is a lightweight demo for low-altitude safety question generation.

The goal is to validate the end-to-end workflow:
document -> cleaning -> KG extraction -> planning -> generation -> evaluation -> question bank.

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
- lightweight KG extraction
- question planning
- difficulty-aware question generation
- question evaluation
- bounded workflow fallback
- local question bank storage

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

- Streamlit for UI
- LangGraph for orchestration
- SQLite for storage
- networkx for KG
- Pydantic schemas for structured data
- local files for uploads and outputs

***

## Implementation Preference

When there are multiple valid ways to implement something:

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
Keep prompts centralized.
Keep schemas explicit.

***

## Extension Guidance

Future versions may later add:

- richer KG selection
- better difficulty control
- stronger evaluation
- improved question bank retrieval
- API layer

Current code should not block those future upgrades.
