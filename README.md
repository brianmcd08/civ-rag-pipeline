# RAG Pipeline — Civilization 6 Domain

A RAG-based chatbot that answers questions about the Better Game Balance (BBG) mod for Civilization VI. Ask it about unit stats, leader abilities, balance changes across versions, wonders, policies, and more — with full awareness of which BBG version introduced or changed something.

🟢 **Live app:** [civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app](https://civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app/) *(password required)*

Live demo requires password due to API costs — screenshots at the bottom.

---

## How it works

1. **Scraping** : BeautifulSoup scrapers pull data from the BBG patch notes pages across all supported versions (`v7.1` through `v7.5`, plus `base_game`), covering units, leaders, buildings, wonders, policies, great people, changelogs, and more.
2. **Ingestion** : Scraped entries are embedded with OpenAI's `text-embedding-3-small` model (dense vectors) and encoded with a fitted BM25 encoder (sparse vectors). Both are upserted together into a Pinecone cloud vector database per record.
3. **Query parsing** : At query time, a Claude-powered Query Parser cleans the user's question (fixing typos, removing explicit version references) and extracts the target BBG version. Version context is injected into the agent's input for use in tool calls.
4. **Agentic retrieval** : A ReAct agent receives the cleaned query and reasons at runtime about which search tools to call. Six tools cover the main content sections (units, leaders, great people, techs & civics, buildings & improvements, and a general catch-all). Each tool issues a hybrid query combining dense semantic search and BM25 sparse keyword search, with version and section metadata filters applied per call. The agent can call multiple tools in sequence when a question spans sections.
5. **Generation** : The agent synthesizes retrieved results into a response grounded in the source data.
6. **Memory** : Conversation state is persisted across turns via a `MemorySaver` checkpointer, enabling context-aware follow-up questions without re-stating the subject.
7. **UI** : A Streamlit app serves the chatbot with per-session thread tracking.

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
│   └── version_extractor.py  # Query Parser: cleans query, extracts version
├── agent/
│   ├── tools.py            # Six search tools wrapping hybrid_query with section filters
│   └── construct_agents.py # ReAct agent construction with MemorySaver checkpointer
├── schema.py           # UnifiedEntry, ParsedQuery, RetrieverState
├── config.py           # Version/Section enums, model names, retrieval constants
├── utils.py            # format_docs helper
└── secrets.py          # Reads from st.secrets (cloud) or .env (local)
evaluation/             # RAG triad eval pipeline
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
pytest
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
