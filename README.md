# RAG Pipeline — Civilization 6 Domain

A RAG-based chatbot that answers questions about the Better Game Balance (BBG) mod for Civilization VI. Ask it about unit stats, leader abilities, balance changes across versions, wonders, policies, and more : with full awareness of which BBG version introduced or changed something. For extra fun, ask for opinions.

🟢 **Live app:** [civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app](https://civ-chatbot-9vnbxfeptmdajugzgdzemr.streamlit.app/) *(password required)*

---

## How it works

1. **Scraping** : BeautifulSoup scrapers pull data from the BBG patch notes pages across 4 versions (`v7.1` through `v7.4`, plus `base_game`), covering units, leaders, buildings, wonders, policies, great people, changelogs, and more.
2. **Ingestion** : Scraped entries are embedded with OpenAI's `text-embedding-3-small` model and upserted into a Pinecone cloud vector database.
3. **Retrieval** : At query time, a version extractor (Claude) parses the user's question to determine which BBG version they're asking about and which section of data is most relevant. The retriever then performs a filtered similarity search.
4. **Generation** : Retrieved documents are passed to Claude along with the original question to generate a response.
5. **UI** : A Streamlit app serves the chatbot with session-based conversation history.

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
│   └── ingester.py     # Embeds scraped data and upserts into Pinecone
├── retrieval/
│   └── retriever.py    # Version- and section-aware similarity search
├── chains/
│   ├── version_extractor.py    # Parses version and section from query
│   ├── rag_pipeline.py         # Wires extractor → retriever
│   └── response_generator.py  # Final LLM call with retrieved context
├── schema.py           # UnifiedEntry and ParsedInput data models
├── config.py           # Version and Section enums
└── secrets.py          # Reads from st.secrets (cloud) or .env (local)
app.py                  # Streamlit UI
```

---

## Querying

The chatbot understands version-specific and cross-version questions:

| Query | Behaviour |
|---|---|
| "What does the Eagle Warrior do?" | Searches BBG v7.4 (latest) |
| "What did the Knight cost in v7.1?" | Filters to v7.1 |
| "Which versions have the Eagle Warrior?" | Searches across all versions |
| "What are the ranged unit promotions?" | Targets the promotions section |

---

## Re-ingestion

`ingester.py` is an admin-only local script. If you modify any scraper or the `generate_embedding_text()` method in `schema.py`, re-run the ingester to push updated vectors to Pinecone:

```bash
python -m src.ingestion.ingester
```

Before re-ingesting, clear the Pinecone index manually (via the Pinecone console or API) to avoid stale or duplicate vectors.

---

## Running tests

```bash
pytest
```

---

## BBG versions covered

`7.1`, `7.2`, `7.3`, `7.4`

---

## Limitations

- **Base game reference data** (promotion trees, vanilla unit stats) is not included — the chatbot covers BBG balance changes only. For base game lookups, refer to the [Civilization Wiki](https://civilization.fandom.com/wiki/Civilization_VI).
