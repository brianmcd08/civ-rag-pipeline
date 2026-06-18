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
6. **Memory**: Conversation state is persisted across turns via a `MemorySaver` checkpointer, enabling context-aware follow-up questions without re-stating the subject.
7. **Evaluation**: Every architecture change is measured against a RAG triad eval harness — context relevance (did retrieval surface the right chunks?), groundedness (is the response supported by those chunks?), and answer relevance (does it answer the question?) — three parallel LLM-as-judge evaluators scored against a fixed question set.
8. **UI**: A Streamlit app serves the chatbot with per-session thread tracking, a sidebar with an About section and example questions.

---

## Architecture evolution

Each change was driven by a specific, measured failure in the state before it — not a rewrite for its own sake. The "V1–V5" labels below are a retrospective narrative grouping rather than tagged releases: checked against the commit history, the work was really an **April baseline** (V1) and a focused **June 1–12 hardening sprint** (V2–V5). The diagram tracks four pipeline stages across those versions: gray means a stage carried over unchanged, blue means a deliberate architecture decision, and amber marks the one known regression (the eval breaking when the pipeline went agentic) before it was fixed in the next version.

![Architecture evolution V1 to V5](docs/civ_rag_evolution.png)

Click through any cell below for the full reasoning behind that decision — what problem it solved, what alternative was rejected, what the eval measured, and the commit that shipped it. The mechanics in each entry are verified against the actual diffs:

| Version | Parse & route | Retrieve | Generate | Eval |
|---|---|---|---|---|
| **V1** · Apr | [Extractor — 1 LLM call](docs/architecture.md#extractor-one-combined-llm-call) | [1 section, dense only](docs/architecture.md#1-section-dense-only) | [Persona — Montezuma](docs/architecture.md#persona-the-montezuma-voice) | [Reference eval](docs/architecture.md#reference-eval-faithfulness-and-relevance-vs-ideal-answers) |
| **V2** · Jun 1 | [2 chains](docs/architecture.md#2-chains-splitting-parser-and-router) | [Multi-section, hybrid (α-weighted)](docs/architecture.md#multi-section-retrieval-with-hybrid-search) | [Persona — Montezuma](docs/architecture.md#persona-the-montezuma-voice) | [RAG triad](docs/architecture.md#rag-triad-context-relevance-groundedness-answer-relevance) |
| **V3** · Jun 2–5 | [2 chains](docs/architecture.md#2-chains-splitting-parser-and-router) | [Multi-section, hybrid (α-weighted)](docs/architecture.md#multi-section-retrieval-with-hybrid-search) | [No persona](docs/architecture.md#persona-removed-the-controlled-experiment) | [Triad hardened](docs/architecture.md#hardening-the-triad-eval-set-cleanup-and-the-answer-relevance-fix) |
| **V4** · Jun 6 | [Parser only](docs/architecture.md#parser-only-router-deleted-for-the-react-agent) | [ReAct agent, 6 tools+memory](docs/architecture.md#react-agent-with-6-tools-and-cross-session-memory) | [No persona](docs/architecture.md#persona-removed-the-controlled-experiment) | [Eval broken](docs/architecture.md#the-eval-breaks-what-going-agentic-costs-you) |
| **V5** · Jun 12 | [Parser only](docs/architecture.md#parser-only-router-deleted-for-the-react-agent) | [ReAct agent, 6 tools+memory](docs/architecture.md#react-agent-with-6-tools-and-cross-session-memory) | [No persona](docs/architecture.md#persona-removed-the-controlled-experiment) | [Eval rewired](docs/architecture.md#eval-rewired-toolmessage-extraction-plus-structured-logging) |

**Eval scores across versions** (mechanics are commit-verified; these score numbers are from recorded eval runs):

| Version | Eval approach | Questions | Scores |
|---|---|---|---|
| V1 | Reference-based (Faithfulness + Relevance vs ideal answers) | 18 | F 2.20 / R 2.30 baseline → R 2.89 after a routing fix; 5 → 0 retrieval failures |
| V2 | RAG triad (CR / G / AR), parallel judges — AR judged vs the query | 17 | CR 2.94 / G 2.65 / AR 2.88 |
| V3 | RAG triad, hardened (AR switched to vs ideal answer) | 15 | CR 3.0 / G 2.80 / AR 2.93 |
| V4 | RAG triad | 15 | CR 3.0 / G 2.73 / AR 2.80 |
| V5 | RAG triad, rewired for the agent | 15 | Same architecture as V4 — eval runner now works end-to-end |

*V1's Faithfulness/Relevance scores aren't directly comparable to V2–V5's triad scores — they measure against ideal answers rather than retrieved chunks. The metric change is itself part of the story: a shift from "is the output good?" to "which stage failed and why?"*

Full write-up — every rejected alternative, the eval delta, and the commit behind each decision — lives in [`docs/architecture.md`](docs/architecture.md).

---

## Project structure

```
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
│   └── query_parser.py     # Query Parser: cleans query, extracts version
├── agent/
│   ├── tools.py             # Six search tools wrapping hybrid_query with section filters
│   └── construct_agents.py  # ReAct agent construction with MemorySaver checkpointer
├── schema.py             # UnifiedEntry, ParsedQuery
├── config.py             # Version/Section enums, model names, retrieval constants
├── logging_config.py     # Structlog configuration — shared logger for structured JSON output
├── utils.py              # format_docs helper
└── secrets.py            # Reads from st.secrets (cloud) or .env (local)
evaluation/              # RAG triad eval pipeline
├── eval_runner.py              # Runs RAG triad eval across question set
├── schema.py                   # PartialJudgment and Judgment types
├── context_relevance_judge.py  # Did retrieval surface the right chunks?
├── grounding.py                # Is the response supported by retrieved chunks?
└── answer_relevance.py         # Does the response answer the question?
models/
└── bm25_values.json    # Fitted BM25 encoder — generated at ingestion time
response_generator.py   # Pipeline entry point — query parsing + agent invocation
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

---

## Screenshots

<img width="1085" height="868" alt="Screenshot_2026-05-23_15-37-06" src="https://github.com/user-attachments/assets/d40e23b9-1152-4552-a3f3-6884cdfa25bf" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-38-05" src="https://github.com/user-attachments/assets/1e0ae9ae-d229-46f5-afbb-e2f9fe214490" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-39-37" src="https://github.com/user-attachments/assets/27dca6db-9405-4bc0-962a-8b8a7d56fa40" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-40-46" src="https://github.com/user-attachments/assets/8bb8a639-531c-45cf-841d-080c7bf1fe0a" />
