# CLAUDE.md — civ-rag-pipeline

## What This Is
Production agentic RAG pipeline for Civilization 6 BBG game knowledge.
Python, LangChain create_agent on LangGraph, Pinecone hybrid search, FastAPI, Streamlit.

## Hard Rules
- Never read, display, modify, or reference .env or any secrets file
- Never run ingestion scripts (ingester.py) — they write to the live Pinecone index
- Never run the Streamlit app — use tests and eval runner only

## Commands
- Run tests: `uv run --all-extras pytest`
- Run eval: `uv run --extra eval python -m evaluation.eval_runner` (costs money on every run; --rejudge re-scores saved answers without regenerating)
- Lint: `uv run ruff check src/`
- Base dependencies are empty by design, so every uv command must name an extra.

## Architecture
- src/agent/tools.py — 6 typed retrieval tools (search_units, search_leaders, etc.)
- src/agent/construct_agents.py — ReAct agent setup, Postgres-only checkpointer (build_checkpointer() raises when DATABASE_URL is unset or unreachable; there is no MemorySaver fallback, callers that need none pass checkpointer=None)
- src/retrieval/retriever.py — hybrid_query() with BM25 + dense, direct Pinecone client
- src/retrieval/version_extractor.py — cleans query, extracts version (chain, not agent)
- src/response_generator.py — calls agent, returns tuple[str, list[str]] (response + ToolMessage strings)
- src/api.py — FastAPI service (GET /health, POST /warm, POST /query) + Mangum handler for Lambda
- src/mcp_server.py — MCP server over the same six tools, stdio transport only, nothing deployed
- infra/ — Terraform for the AWS deploy (ECR, IAM, Lambda, API Gateway) + deploy.sh
- evaluation/ — RAG triad judges (context relevance, groundedness, answer relevance)
- models/bm25_values.json — fitted BM25 encoder, do not delete or refit

## Key Conventions
- All hardcoded values live in config.py — never hardcode K, ALPHA, model names inline
- format_docs() lives in src/utils.py — don't duplicate it
- BM25Encoder loaded via two-step: BM25Encoder() then .load() — not constructor arg
- Single-section tools use {"section": {"$eq": value}}; multi-section tools (techs_and_civics, buildings_and_improvements) use {"section": {"$in": [...]}}
- search_general uses filter=None, not {"section": {"$eq": None}} — that's a Pinecone bug

## Current Status
Current surfaces: Streamlit client, FastAPI service (src/api.py), a container-image Lambda behind API Gateway with inference on Bedrock (Terraform in infra/), and a local-only MCP server (src/mcp_server.py). The eval is the RAG triad over a 20-question set with a --rejudge pass. docs/architecture.md is the source of truth for all of this; update it first and this file after.

## What's Intentionally Not Here
- Scraper details (rarely touched)
- Streamlit UI (stable, don't change)
- Version enum (self-documenting)