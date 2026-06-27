# CLAUDE.md — civ-rag-pipeline

## What This Is
Production agentic RAG pipeline for Civilization 6 BBG game knowledge.
Python, LangGraph (create_react_agent), Pinecone hybrid search, Streamlit.

## Hard Rules
- Never read, display, modify, or reference .env or any secrets file
- Never run ingestion scripts (ingester.py) — Pinecone writes cost money
- Never run the Streamlit app — use tests and eval runner only

## Commands
- Run tests: `uv run pytest tests/ -v`
- Run eval: `uv run python -m evaluation.eval_runner`
- Lint: `uv run ruff check src/`

## Architecture (Post-V5 / current)
- src/agent/tools.py — 6 typed retrieval tools (search_units, search_leaders, etc.)
- src/agent/construct_agents.py — ReAct agent setup, PostgresSaver checkpointer (falls back to MemorySaver when DATABASE_URL is not set)
- src/retrieval/retriever.py — hybrid_query() with BM25 + dense, direct Pinecone client
- src/retrieval/version_extractor.py — cleans query, extracts version (chain, not agent)
- src/response_generator.py — calls agent, returns tuple[str, list[str]] (response + ToolMessage strings)
- evaluation/ — RAG triad judges (context relevance, groundedness, answer relevance)
- models/bm25_values.json — fitted BM25 encoder, do not delete or refit

## Key Conventions
- All hardcoded values live in config.py — never hardcode K, ALPHA, model names inline
- format_docs() lives in src/utils.py — don't duplicate it
- BM25Encoder loaded via two-step: BM25Encoder() then .load() — not constructor arg
- Single-section tools use {"section": {"$eq": value}}; multi-section tools (techs_and_civics, buildings_and_improvements) use {"section": {"$in": [...]}}
- search_general uses filter=None, not {"section": {"$eq": None}} — that's a Pinecone bug

## Current Status
V5 is complete and the eval pipeline is working end-to-end. Post-V5 infra work (Jun 25) added PostgresSaver + Docker Compose — no pipeline stage changes. No active work items.

## What's Intentionally Not Here
- Scraper details (rarely touched)
- Streamlit UI (stable, don't change)
- Version enum (self-documenting)