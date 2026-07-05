# RAG Pipeline — Civilization 6 Domain

A production-grade, agentic RAG system that answers questions about the Better Game Balance (BBG) mod for Civilization VI — unit stats, leader abilities, balance changes across versions, wonders, policies, and more — with full awareness of which BBG version introduced or changed something. It evolved from a single-call extractor on a local vector store into a ReAct agent with hybrid retrieval and cross-session memory, with every major change measured against a RAG triad evaluation harness rather than judged by eye (see Architecture evolution below for the full, commit-dated decision history).

🟢 **Live app:** [civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app](https://civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app/) *(password required)*

Live demo requires password due to API costs — screenshots at the bottom.

---

## How it works

1. **Scraping**: BeautifulSoup scrapers pull data from the BBG patch notes pages across all supported versions (`v7.1` through `v7.5`, plus `base_game`), covering units, leaders, buildings, wonders, policies, great people, changelogs, and more.
2. **Ingestion**: Scraped entries are embedded with OpenAI's `text-embedding-3-small` model (dense vectors) and encoded with a fitted BM25 encoder (sparse vectors). Both are upserted together into a Pinecone cloud vector database per record, in batches with structured JSON logging and per-batch error handling so a single failure doesn't kill the run.
3. **Query parsing**: At query time, a Claude-powered Query Parser cleans the user's question (fixing typos, removing explicit version references) and extracts the target BBG version. Version context is injected into the agent's input for use in tool calls.
4. **Agentic retrieval**: A ReAct agent receives the cleaned query and reasons at runtime about which search tools to call. Six tools cover the main content sections (units, leaders, great people, techs & civics, buildings & improvements, and a general catch-all). Each tool issues a hybrid query combining dense semantic search and BM25 sparse keyword search — the dense and sparse vectors are alpha-weighted (`ALPHA = 0.5`) and combined in a single Pinecone hybrid query — with version and section metadata filters applied per call. The agent can call multiple tools in sequence when a question spans sections.
5. **Generation**: The agent synthesizes retrieved results into a response grounded in the source data.
6. **Memory**: Conversation state is persisted across turns and container restarts via a `PostgresSaver` checkpointer backed by a Postgres database (Docker Compose). Each Streamlit session gets its own `thread_id` so context carries through a session; a new session starts fresh. (`thread_id` persistence across sessions via cookie or query param is the noted next step.)
7. **Evaluation**: Every architecture change is measured against a RAG triad eval harness — context relevance (did retrieval surface the right chunks?), groundedness (is the response supported by those chunks?), and answer relevance (does it answer the question?) — three parallel LLM-as-judge evaluators scored against a fixed question set.
8. **UI**: A Streamlit app serves the chatbot with per-session thread tracking, a sidebar with an About section and example questions.

---

## Architecture evolution

Each change was driven by a specific, measured failure in the state before it — not a rewrite for its own sake. The work fell into four phases: an **April baseline** (Foundation), a **June 1–5 hardening sprint** (Hardening), a **June 6–13 agentic experiment** (Agentic), and a **June 25 – July 4 operations phase** (Ops: containerization and persistent memory, then a measured model swap). The diagram tracks five pipeline stages across those phases: gray means a stage carried over unchanged, blue means a deliberate architecture decision.

![Architecture evolution](docs/civ_rag_evolution.png)

Click through any cell below for the full reasoning behind that decision — what problem it solved, what alternative was rejected, what the eval measured, and the commit that shipped it. The mechanics in each entry are verified against the actual diffs:

| Phase | Parse & route | Retrieve | Generate | Eval | Memory & deploy |
|---|---|---|---|---|---|
| **Foundation** · Apr | [Extractor — 1 LLM call](docs/architecture.md#extractor-one-combined-llm-call) | [1 section, dense only](docs/architecture.md#1-section-dense-only) | [Persona — Montezuma](docs/architecture.md#persona-the-montezuma-voice) | [Reference eval](docs/architecture.md#reference-eval-faithfulness-and-relevance-vs-ideal-answers) | — |
| **Hardening** · Jun 1–5 | [2 chains](docs/architecture.md#2-chains-splitting-parser-and-router) | [Multi-section, hybrid (α-weighted)](docs/architecture.md#multi-section-retrieval-with-hybrid-search) | [No persona](docs/architecture.md#persona-removed-the-controlled-experiment) | [RAG triad, hardened](docs/architecture.md#rag-triad-context-relevance-groundedness-answer-relevance) | — |
| **Agentic** · Jun 6–13 | [Parser only](docs/architecture.md#parser-only-router-deleted-for-the-react-agent) | [ReAct agent, 6 tools + memory](docs/architecture.md#react-agent-with-6-tools-and-cross-session-memory) | [No persona](docs/architecture.md#persona-removed-the-controlled-experiment) | [Eval rewired](docs/architecture.md#eval-rewired-toolmessage-extraction-plus-structured-logging) | [MemorySaver](docs/architecture.md#react-agent-with-6-tools-and-cross-session-memory) |
| **Ops** · Jun 25 – Jul 4 | ← same | ← same | [Sonnet 4.6 — measured swap](docs/architecture.md#prior-override-investigation-the-measured-model-swap) | ← same | [PostgresSaver + Docker Compose](docs/architecture.md#persistent-memory-and-containerization-postgressaver--docker-compose) |

**Eval scores by phase** (mechanics are commit-verified; score numbers are from recorded eval runs):

| Phase | Eval approach | Questions | Scores |
|---|---|---|---|
| Foundation | Reference-based (Faithfulness + Relevance vs ideal answers) | 20 baseline → 18 final | F 2.20 / R 2.40 → R 2.89 after routing fix; 5 → 0 retrieval failures |
| Hardening | RAG triad (CR / G / AR), hardened — AR vs ideal answer | 15 | CR 3.0 / G 2.80 / AR 2.93 |
| Agentic | RAG triad, rewired for agent (ToolMessage extraction) | 15 | CR 3.0 / G 2.73 / AR 2.80 |
| Ops | RAG triad, same harness; Jul 4 model swap to Sonnet 4.6 | 15 | CR 3.00 / G 2.93 / AR 2.93 |

*Foundation's Faithfulness/Relevance scores aren't directly comparable to the triad scores — they measure against ideal answers rather than retrieved chunks. The metric change is itself part of the story: a shift from "is the output good?" to "which stage failed and why?"*

Full write-up — every rejected alternative, the eval delta, and the commit behind each decision — lives in [`docs/architecture.md`](docs/architecture.md).

---

## Model choice

The agent model is Claude Sonnet 4.6, selected by measurement rather than default. Haiku 4.5 exhibited a training-data override failure (confidently wrong answers with the correct chunk present in tool output) that prompting measurably could not fix. Sonnet was validated with grounding probes built on facts where this corpus diverges from vanilla Civ 6 values (12 of 12 grounded, even where the model's raw prior is confidently wrong) and with the RAG triad scores in the table above. The tradeoff is cost: Sonnet is 3x Haiku per token. The full investigation, including the revert that was considered and superseded by measurement, is in [`docs/architecture.md`](docs/architecture.md#prior-override-investigation-the-measured-model-swap); the probe scripts are in `evaluation/`.

---

## Project structure

```
Dockerfile                  # Single-container image (uv, lockfile-first layer caching)
docker-compose.yml          # Two services: app + db (postgres:16), named volume for persistence
src/
├── scraping/           # One scraper per BBG data section
│   ├── scrape_orchestrator.py  # Runs all scrapers
│   ├── scrape_units.py
│   ├── scrape_leaders.py
│   ├── scrape_changelogs.py
│   └── ...
├── ingestion/
│   └── ingester.py     # Embeds scraped data, fits BM25 encoder, upserts into Pinecone
├── retrieval/
│   ├── retriever.py        # hybrid_query — dense + sparse search via Pinecone
│   └── version_extractor.py  # Query Parser: cleans query, extracts version
├── agent/
│   ├── tools.py             # Six search tools wrapping hybrid_query with section filters
│   └── construct_agents.py  # ReAct agent construction with PostgresSaver checkpointer (falls back to MemorySaver when DATABASE_URL is not set)
├── schema.py             # UnifiedEntry, ParsedQuery
├── config.py             # Version/Section enums, model names, retrieval constants
├── logging_config.py     # Structlog configuration — shared logger for structured JSON output
├── utils.py              # format_docs helper
├── secrets.py            # Reads from st.secrets (cloud) or .env (local)
└── response_generator.py # Pipeline entry point — query parsing + agent invocation
evaluation/              # RAG triad eval pipeline
├── eval_runner.py              # Runs RAG triad eval across question set
├── schema.py                   # PartialJudgment and Judgment types
├── context_relevance_judge.py  # Did retrieval surface the right chunks?
├── grounding.py                # Is the response supported by retrieved chunks?
└── answer_relevance.py         # Does the response answer the question?
models/
└── bm25_values.json    # Fitted BM25 encoder — generated at ingestion time
app.py                  # Streamlit UI
```

---

## Querying

The chatbot understands version-specific, cross-version, and multi-section questions:

| Query | Behaviour |
|---|---|
| "What does the Eagle Warrior do?" | Searches BBG v7.5 (latest) |
| "What did the Knight cost in v7.1?" | Filters to v7.1 |
| "Which versions have the Eagle Warrior?" | Searches across all versions |
| "Which civilization has the Ice Hockey Rink?" | Agent calls both improvements and leaders tools |
| "What is her unique unit?" | Memory resolves prior context — no need to restate |

---

## Re-ingestion

`ingester.py` is an admin-only local script. If you modify any scraper, the `generate_embedding_text()` method in `schema.py`, or add a new BBG version to the `Version` enum, re-run the ingester to push updated vectors to Pinecone:

```bash
uv run python -m src.ingestion.ingester
```

The ingester upserts by ID (entry hash), so re-running is additive — existing vectors are overwritten only if the content hash changes, and new entries are added. You do not need to clear the Pinecone index manually before re-ingesting.

The ingester also re-fits the BM25 encoder on the full corpus and overwrites `models/bm25_values.json`. Commit the updated file after re-ingesting.

**To add a new BBG version:** add the new version as the first entry in the `Version` enum in `config.py`. The scraper and ingester pick it up automatically on next run.

---

## Deployment

The app and its Postgres memory store run as two Docker Compose services:

```bash
# Requires Docker Desktop (or Docker Engine + Compose plugin)
# Copy .env.example to .env and fill in keys before running
docker compose up
```

The `app` service waits for the `db` healthcheck (`pg_isready`) to pass before starting. Conversation memory is written to a named Postgres volume (`pgdata`) and survives `docker compose restart` — it is only dropped with `docker compose down -v`.

**Environment variables** (injected at runtime, never baked into the image — API keys via `env_file: .env`, `DATABASE_URL` set in the Compose `environment:` block for the local stack):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API (query parsing, generation, eval judges) |
| `OPENAI_API_KEY` | Embedding model (`text-embedding-3-small`) |
| `PINECONE_API_KEY` | Vector database |
| `PINECONE_INDEX_NAME_V2` | Pinecone index name for the hybrid (dense + sparse) index |
| `DATABASE_URL` | Postgres connection string — e.g. `postgresql://civ:civ@db:5432/civ` |
| `APP_PASSWORD` | Password gate for the Streamlit UI |

Secrets are excluded from the image via `.dockerignore`. To run outside Docker (local dev without Postgres), omit `DATABASE_URL` and the app falls back to an in-memory `MemorySaver` checkpointer automatically.

---

## Running tests

```bash
uv run pytest
```

---

## BBG versions covered

`base_game`, `7.1`, `7.2`, `7.3`, `7.4`, `7.5`

---

## Limitations

- **Base game reference data** (promotion trees, vanilla unit stats) is not included — the chatbot covers BBG balance changes only. For base game lookups, refer to the [Civilization Wiki](https://civilization.fandom.com/wiki/Civilization_VI).
- **Session memory only**: each Streamlit session generates a fresh `thread_id`, so a returning user starts a new conversation rather than resuming a prior one. Persisting `thread_id` across sessions via cookie or query param is the noted next step.

---

## Screenshots

**Version-specific retrieval** — unit stats pulled from the v7.5 corpus:

<img alt="Warak'aq stats retrieved for version 7.5" src="docs/grounded_answer.png" />

**Multi-section retrieval** — one question spanning the leaders and improvements sections:

<img alt="Egypt's leaders and unique improvement answered in one query" src="docs/memory_a.png" />

**Conversation memory** — the follow-up resolves "her" from the previous turn:

<img alt="Follow-up question resolving 'her unique unit' via conversation memory" src="docs/memory_b.png" />

**Grounded over prior** — the Warrior's cost is 20 in this corpus (vanilla says 40); the answer comes from the retrieved chunks, not training data:

<img alt="Eagle Warrior identified correctly and Warrior cost answered from the corpus" src="docs/eagle_warrior.png" />
