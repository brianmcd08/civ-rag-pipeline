# RAG Pipeline — Civilization 6 Domain

A RAG-based chatbot that answers questions about the Better Game Balance (BBG) mod for Civilization VI. Ask it about unit stats, leader abilities, balance changes across versions, wonders, policies, and more — with full awareness of which BBG version introduced or changed something. For extra fun, ask for opinions.

🟢 **Live app:** [civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app](https://civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app/) *(password required)*

Live demo requires password due to API costs — screenshots at the bottom.

---

## How it works

1. **Scraping** : BeautifulSoup scrapers pull data from the BBG patch notes pages across all supported versions (`v7.1` through `v7.5`, plus `base_game`), covering units, leaders, buildings, wonders, policies, great people, changelogs, and more.
2. **Ingestion** : Scraped entries are embedded with OpenAI's `text-embedding-3-small` model (dense vectors) and encoded with a fitted BM25 encoder (sparse vectors). Both are upserted together into a Pinecone cloud vector database per record.
3. **Extraction** : At query time, a two-agent pipeline (Claude) processes the user's question. The Query Parser cleans the query and extracts the target BBG version. The Section Router classifies which section(s) of data the question targets — returning a list to support multi-section queries.
4. **Retrieval** : A LangGraph supervisor fans out to parallel retrieval nodes — one per section — and merges the results. Each node issues a hybrid query combining dense semantic search and BM25 sparse keyword search, with version and section metadata filters applied per call.
5. **Generation** : Retrieved documents are passed to Claude along with the original question to generate a response.
6. **UI** : A Streamlit app serves the chatbot with session-based conversation history.

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
│   └── retrieval.py    # LangGraph supervisor + hybrid retrieval nodes
├── chains/
│   ├── query_parser.py         # Agent 1: cleans query, extracts version
│   ├── section_router.py       # Agent 2: routes to one or more sections
│   └── response_generator.py  # Final LLM call with retrieved context
├── schema.py           # UnifiedEntry, ParsedQuery, RoutingDecision, RetrieverState
├── config.py           # Version and Section enums
└── secrets.py          # Reads from st.secrets (cloud) or .env (local)
evaluation/             # RAG triad eval pipeline
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
| "Which civilization has the Ice Hockey Rink?" | Searches improvements + leaders in parallel |

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
- **Version number claims** — the model occasionally states version numbers (e.g., "available since v7.1") that are not present in the retrieved source documents. This is a known limitation of the Montezuma persona prompt and is documented as a v3 investigation item.

---

## Screenshots ##

<img width="1085" height="868" alt="Screenshot_2026-05-23_15-37-06" src="https://github.com/user-attachments/assets/d40e23b9-1152-4552-a3f3-6884cdfa25bf" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-38-05" src="https://github.com/user-attachments/assets/1e0ae9ae-d229-46f5-afbb-e2f9fe214490" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-39-37" src="https://github.com/user-attachments/assets/77dca6db-9405-4bc0-962a-8b8a7d56fa40" />
<img width="1085" height="868" alt="Screenshot_2026-05-23_15-40-46" src="https://github.com/user-attachments/assets/8bb8a639-531c-45cf-841d-080c7bf1fe0a" />

---
