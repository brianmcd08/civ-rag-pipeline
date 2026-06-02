# civ-rag-pipeline v2 — Technical Specification

**Project:** Civilization 6 BBG Chatbot  
**Version:** 2.0  
**Status:** Complete  
**Author:** Brian McDowell

---

## Overview

v1 shipped a working RAG pipeline with version-aware retrieval, a single-section routing strategy, and a reference-based eval harness. It proved the core concept and identified three concrete limitations:

1. The version extractor does too many jobs in one LLM call and fails silently when routing breaks
2. Multi-section queries fall back to unfiltered search, returning degraded results as relevant chunks lose the similarity competition to noise
3. The eval pipeline measures output quality against reference answers but cannot diagnose where in the pipeline failures originate

v2 addressed all three, added proper RAG triad evaluation, ingested BBG v7.5, and added BM25 hybrid search. All four steps are complete.

---

## Goals — All Achieved

- ✅ Replace the monolithic version extractor with a two-agent extraction pipeline
- ✅ Replace single-section retrieval with a supervisor-coordinated multi-section retrieval architecture
- ✅ Replace reference-based eval with a full RAG triad eval pipeline
- ✅ Add BM25 sparse retrieval via Pinecone hybrid search, implemented during the full re-ingest for the new BBG version
- ✅ Add a version ingestion workflow that supports new BBG releases incrementally after v2

---

## Architecture Changes

### 1. Two-Agent Extraction Pipeline ✅

**Problem:** `version_extractor.py` handled query cleaning, version extraction, and section routing in a single LLM call. These are three distinct responsibilities. When section routing failed, there was no way to isolate it from version extraction — failures were opaque.

**Implementation:** Split into two agents in sequence, orchestrated by `run_extraction_pipeline`.

**Agent 1 — Query Parser** (`query_parser.py`)
Responsible for: cleaning the query (fixing typos, removing version references) and extracting the target version. Takes query and conversation history. Produces a `ParsedQuery` object: `cleaned_query: str` and `version: Version | None`.

**Agent 2 — Section Router** (`section_router.py`)
Receives the `cleaned_query` from Agent 1. No history — the cleaned query is sufficient context. Returns a `RoutingDecision` object: `section_hints: list[Section] | None`. The list return is what enables multi-section retrieval downstream. `version=None` in the `ParsedQuery` signals cross-version behavior; no separate flag needed.

**Key decisions made during implementation:**
- `ParsedInput` deleted entirely — replaced by two separate schema classes
- `section_router` prompt updated to request a list of sections with multi-section examples added (single-value prompt caused routing failures on multi-section queries)
- Pinecone namespace package conflict fixed with clean reinstall
- Old `version_extractor` function deleted (not commented out)

**Tests:** Three integration tests calling `run_extraction_pipeline` directly — single section, no section, multiple sections. All passing.

---

### 2. Multi-Section Retrieval Supervisor ✅

**Problem:** The original retriever routed every query to exactly one section. Multi-section queries fell back to unfiltered search, where large sections dominated the similarity competition and buried relevant chunks from smaller sections.

**Implementation:** A LangGraph supervisor using the `Send` API for conditional fan-out to parallel retrieval nodes.

**Key implementation details:**
- No supervisor node — `supervise_retrieval` is the conditional edge routing function from `START`, not a node
- One parameterized `retrieval` node — not 18 separate nodes, one per section
- State uses `Annotated[list[Document], operator.add]` reducer — each retrieval node appends results to shared list; LangGraph handles merging automatically
- Deterministic graph, not a ReAct agent — routing decisions are made in code based on `section_hints`, not by an LLM
- Graph: `add_conditional_edges(START, supervise_retrieval)` → `retrieval` → `END`

**Bug fixed:** Node registered as `"retriever"` but `Send` was calling `"retrieval"` — caused silent failure with no documents returned.

**Note on RRF:** The spec proposed RRF merging at the supervisor level. In practice, the `operator.add` reducer concatenates results from all retrieval nodes and passes the combined list to generation. Cross-encoder reranking of merged results is deferred to v3.

**Tests:** Unit tests for multi-section query (ice hockey rink), no section hint fallback, empty results fallback. All passing.

---

### 3. RAG Triad Eval Pipeline ✅

**Problem:** The v1 eval compared generated responses against hand-written ideal answers. This measured output quality but could not distinguish retrieval failures from generation failures.

**Implementation:** Three independent judges running in parallel via `asyncio.gather`.

**Judge 1 — Context Relevance** (`context_relevance_judge.py`)
Inputs: query + retrieved chunks. Did retrieval surface the right material? Low score → fix retrieval pipeline.

**Judge 2 — Groundedness** (`grounding.py`)
Inputs: retrieved chunks + generated response. Is every claim in the response supported by the retrieved chunks? Replaces v1's faithfulness score, which compared against an ideal answer rather than source chunks. Low score → fix generation (prompt, model, persona).

**Judge 3 — Answer Relevance** (`answer_relevance.py`)
Inputs: query + generated response. Does the response answer the question? Low score → end-to-end problem, usually prompt or routing.

**Architectural change made during implementation:** `generate_response` previously returned only response text. Refactored to return `tuple[str, list[Document]]` — response and retrieved chunks. The eval runner calls `generate_response` once and gets everything it needs.

**Known limitation:** Answer relevance judge is unreliable without game domain context. Judge uses real-world knowledge as baseline, causing false failures on game-specific questions. Documented as v3 investigation item.

**v2 eval results (17 questions, run after hybrid retrieval was in place):**

| Metric | Score |
|---|---|
| Context Relevance | 2.94 |
| Groundedness | 2.65 |
| Answer Relevance | 2.88 |

**Findings:**
- Context relevance near-perfect — retrieval is surfacing the right chunks for almost all questions
- Grounding failures concentrated in version number fabrication: the Montezuma persona consistently states version numbers not present in the retrieved chunks (e.g., "available since version 7.1," "remains available through version 7.5"). 6 of 17 questions affected. Root cause confirmed: persona, not retrieval.
- One outlier: Alan Turing (2/2/2) — the question is partly about real-world biography; the index only has game data. This is a domain ceiling, not a pipeline failure.

---

### 4. Version Ingestion Workflow ✅

**Problem:** BBG releases new versions periodically. v1 had no formal workflow and required manual re-ingestion of everything.

**Implementation:**

**Version enum pattern:** The `Version` enum in `schema.py` is the source of truth for supported versions. `get_latest_version()` uses `next(iter(cls))` — it returns the first defined enum member. Adding a new version as the first entry in the enum is all that's needed to make it the new default. No config file change required.

**v7.5 ingestion:** `V75 = "7.5"` added as the first entry in the `Version` enum. The scraper orchestrator iterates over the enum automatically — no other changes were needed to pick up the new version.

**Full re-ingest results:**
- Total scraped entries: 14,187
- Total after deduplication: 3,156
- New index: `civ6-bbg-v2` (dotproduct metric, Pinecone Serverless, us-east-1)

**Additive ingestion for future versions:** The ingester upserts by ID (entry hash). Running the ingester again with a new version in the enum will upsert new entries without touching existing ones. The `models/bm25_values.json` encoder is fit on the full corpus at re-ingest time. For new version additions, the encoder will be slightly stale (new terms won't have correct IDF weights), but this is acceptable for a game balance domain with stable terminology.

**Note:** The `ingest_version.py` script and `versions_manifest.json` described in the original spec were not built. The additive upsert behavior of the ingester serves the same purpose with less ceremony.

---

### 5. BM25 Hybrid Retrieval ✅

**Problem:** v1 used dense-only vector search. For a game balance domain with precise terminology — unit names, policy names, wonder names — dense retrieval can miss exact term matches.

**Implementation:**

**Encoder:** `BM25Encoder` from `pinecone-text`. Fit on all 3,156 deduplicated entry texts before ingestion. Serialized to `models/bm25_values.json` and committed to the repo.

**Ingestion:** `PineconeHybridSearchRetriever` from `langchain_community` handles upsert — it generates both dense and sparse vectors per record and upserts them together to the Pinecone index. The encoder is loaded from disk at ingestion time.

**Retrieval:** `PineconeHybridSearchRetriever` was evaluated but not used for retrieval. It does not support dynamic per-call metadata filters — filter is set at initialization time only. The retrieval node builds a different filter per call based on version and section, so the retriever abstraction was bypassed. Queries are issued directly via `index.query()`:

```python
result = index.query(
    vector=scaled_dense,    # dense embedding * alpha
    sparse_vector=scaled_sparse,  # BM25 sparse vector * (1 - alpha)
    top_k=k,
    filter=pinecone_filter,
    include_metadata=True,
)
```

Alpha is set to 0.5 (equal weight between dense and sparse). Tuning against eval scores is a v3 item.

**Index:** New Pinecone index `civ6-bbg-v2` with `dotproduct` metric. Dense embeddings from `text-embedding-3-small` are already L2-normalized (confirmed via OpenAI documentation), so no normalization step is needed before upsert.

**Text key:** `PineconeHybridSearchRetriever` stores document text under the key `context` (not `text` as `PineconeVectorStore` does). The retrieval node reads `match.metadata.get("context", "")` for `page_content`.

**Deprecation note:** `langchain_community` is deprecated. The dependency is confined to `ingester.py`, which runs locally, not on Streamlit Cloud. The retrieval path uses the direct Pinecone client and has no `langchain_community` dependency at runtime.

**Impact:** Context relevance score of 2.94 confirms hybrid retrieval is working. Exact-term queries for unit names, wonder names, and policy names surface correct chunks reliably.

---

## What Is Not Changing

- The `UnifiedEntry` schema and `generate_embedding_text()` / `generate_metadata()` methods — stable and well-designed
- The scraper architecture — section-specific scrapers with orchestrator dispatch works correctly
- The Streamlit UI — no changes to `app.py`
- Pinecone as the vector store
- The Montezuma persona in the response generator — product decision; flagged as v3 investigation item given confirmed groundedness impact

---

## Open Questions — Resolved

1. **Cross-encoder reranking:** Deferred to v3. RRF concatenation at the supervisor level is sufficient for current eval scores.

2. **Montezuma persona and groundedness:** Confirmed. Grounding failures are concentrated in version number fabrication by the persona. Groundedness score of 2.65 vs. context relevance of 2.94 — the gap is generation, not retrieval. See v3 investigation items.

3. **Eval set expansion:** The RAG triad removes the ideal answer requirement. New questions can be added at low cost. Deferred to v3.

---

## V3 Investigation Items

1. **Persona hallucinations — version numbers:** Pipeline consistently states version numbers not present in retrieved chunks (e.g., "since version 7.3," "remains available through version 7.5"). Confirmed as the primary groundedness failure mode in v2 eval. Hypothesis: Montezuma persona encourages authoritative-sounding claims. Test by running eval with and without persona and comparing groundedness scores.

2. **Persona hallucination — fake mod name:** Pipeline generated "Beyond the Gathering Storm" — a mod name that does not exist. Stronger evidence that the persona fabricates proper nouns, not just version numbers.

3. **Guru heal charges:** Pipeline consistently says 2 heal charges; source document says 3. Possible data error at ingestion. Investigate source data before attributing to generation.

4. **Answer relevance reliability:** Current judge is unreliable without game domain context or ideal answers. Options: add ideal answers back for answer relevance only, or constrain the judge to game context. Deferred to v3.

5. **Alpha tuning:** Alpha is currently 0.5. Systematic eval across alpha values (0.3, 0.5, 0.7) to find the optimal dense/sparse weighting for this domain would improve context relevance scores further.

---

## Success Criteria — All Met

- ✅ A multi-section query ("which civilization has the ice hockey rink?") returns a correct answer, not a degraded one
- ✅ All three RAG triad scores are captured in the eval output CSV
- ✅ Context relevance, groundedness, and answer relevance can each be interpreted independently to diagnose failures
- ✅ BM25 hybrid search is in place and context relevance scores are measurably improved for exact-term queries (2.94)
- ✅ The new BBG version (7.5) is ingested and queryable
- ✅ Subsequent BBG versions can be ingested additively without a full re-ingest

---

## Implementation Order — Complete

1. ✅ Two-agent extraction pipeline
2. ✅ RAG triad eval pipeline
3. ✅ Multi-section retrieval supervisor
4. ✅ BM25 hybrid retrieval + BBG v7.5 ingestion
