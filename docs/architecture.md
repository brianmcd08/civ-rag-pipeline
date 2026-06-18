# Architecture: V1 → V5

This is the decision log behind the civ-rag-pipeline's five architecture versions: what problem forced each change, what alternative was considered and rejected, and what the evaluation harness measured before and after. The companion diagram and quick-reference table are in the [main README](../README.md).

![Architecture evolution V1 to V5](civ_rag_evolution.png)

**Eval scores across versions:**

| Version | Eval approach | Questions | Scores |
|---|---|---|---|
| V1 | Reference-based (Faithfulness + Relevance vs ideal answers) | 18 | F 2.20 / R 2.30 baseline → R 2.89 after a routing fix; 5 → 0 retrieval failures |
| V2 | RAG triad (CR / G / AR), parallel judges | 17 | CR 2.94 / G 2.65 / AR 2.88 |
| V3 | RAG triad, hardened (AR switched to reference-based) | 15 | CR 3.0 / G 2.80 / AR 2.93 |
| V4 | RAG triad | 15 | CR 3.0 / G 2.73 / AR 2.80 |
| V5 | RAG triad, rewired for the agent | 15 | Same architecture as V4 — eval runner now works end-to-end |

*V1's scores aren't directly comparable to V2–V5's — they measure against ideal answers rather than retrieved chunks. The metric change is itself part of the story: a shift from "is the output good?" to "which stage failed and why?"*

## Contents

- [Extractor: one combined LLM call](#extractor-one-combined-llm-call)
- [1 section, dense only](#1-section-dense-only)
- [Persona: the Montezuma voice](#persona-the-montezuma-voice)
- [Reference eval: faithfulness and relevance vs ideal answers](#reference-eval-faithfulness-and-relevance-vs-ideal-answers)
- [2 chains: splitting parser and router](#2-chains-splitting-parser-and-router)
- [Multi-section retrieval with hybrid search and RRF](#multi-section-retrieval-with-hybrid-search-and-rrf)
- [RAG triad: context relevance, groundedness, answer relevance](#rag-triad-context-relevance-groundedness-answer-relevance)
- [Persona removed: the controlled experiment](#persona-removed-the-controlled-experiment)
- [Hardening the triad: eval set cleanup and the answer relevance fix](#hardening-the-triad-eval-set-cleanup-and-the-answer-relevance-fix)
- [Parser only: router deleted for the ReAct agent](#parser-only-router-deleted-for-the-react-agent)
- [ReAct agent with 6 tools and cross-session memory](#react-agent-with-6-tools-and-cross-session-memory)
- [The eval breaks: what going agentic costs you](#the-eval-breaks-what-going-agentic-costs-you)
- [Eval rewired: ToolMessage extraction plus structured logging](#eval-rewired-toolmessage-extraction-plus-structured-logging)

---

## Extractor: one combined LLM call

*(V1)*

V1 used a single `version_extractor` chain that cleaned the query, extracted the target BBG version, and routed to a content section — all in one LLM call and one prompt. It was the fastest way to ship a working pipeline and prove the retrieval concept end to end before investing in a more elaborate parsing architecture.

**What it cost:** combining three responsibilities into one call meant a failure in one (e.g. section routing) was indistinguishable from a failure in another, and hard to diagnose. Missing few-shot examples caused two specific misroutes — see [reference eval](#reference-eval-faithfulness-and-relevance-vs-ideal-answers) below — which is what eventually motivated splitting the extractor into two chains in V2.

## 1 section, dense only

*(V1)*

Retrieval matched the query against a single inferred content section using dense embedding similarity only. When no section could be inferred, the pipeline fell back to an unfiltered search across all sections (excluding the 17,000-entry `names` section) at k=40.

**What it cost:** multi-section questions — "which civilization has the Ice Hockey Rink?" needs both `improvements` and `leaders` — returned answers, but degraded ones, because the unfiltered fallback let large sections dominate the similarity ranking and bury the correct chunks. This was the single largest functional gap V2 addressed.

## Persona: the Montezuma voice

*(V1, V2)*

Responses were generated in a Montezuma persona for tone and flavor.

**What it cost:** the persona encouraged the model to add color beyond what the retrieved chunks supported — fabricated version numbers and, in one case, a mod name that doesn't exist. This was confirmed, not assumed: removing the persona in V3 and re-running the eval, rather than guessing and rewriting the prompt, moved groundedness from 2.65 to 3.0 with a one-line change. See [persona removed](#persona-removed-the-controlled-experiment).

## Reference eval: faithfulness and relevance vs ideal answers

*(V1)*

V1's eval scored generated responses against hand-written ideal answers on two metrics, Faithfulness and Relevance, using an LLM judge on a 1–3 scale across 18 questions. Baseline: Faithfulness 2.20, Relevance 2.30, with 5 complete retrieval failures (roughly a quarter of the set returning "I don't have information about that").

Root cause was missing few-shot routing examples in the extractor prompt — questions about the Migration Treaty were misrouting to `misc`, and questions about BBG Expanded were misrouting to `changelog`. Adding targeted examples for both eliminated all five failures and moved Relevance to 2.89.

**The limitation that motivated V2:** Faithfulness was framed as "does the answer stick to the source material," but mechanically it compared the response to the *ideal answer*, not the retrieved chunks — so it could score well even when the model was paraphrasing the ideal answer without being grounded in what was actually retrieved. A retrieval failure and a generation failure produced an identical low score, with no way to tell which stage to fix.

## 2 chains: splitting parser and router

*(V2, V3)*

The single extractor was split into two chains with separate responsibilities: a Query Parser that cleans the query and extracts the target version, and a Section Router that classifies which content section(s) the query targets — returning a *list*, not a single value, which is what made multi-section retrieval possible downstream.

**Rejected alternative:** keeping a single chain and just improving its prompt. Rejected because the underlying problem wasn't prompt quality — it was that two unrelated responsibilities shared one failure surface, where a routing fix could silently break version extraction and vice versa.

## Multi-section retrieval with hybrid search and RRF

*(V2, V3)*

Two changes shipped together, bundled with a required full re-ingestion: a LangGraph supervisor that fans out to one retrieval call per routed section in parallel (using the `Send` API and a reducer to merge results), and hybrid BM25 sparse + dense retrieval, merged with Reciprocal Rank Fusion.

**Why hybrid:** dense embeddings can miss exact game terminology — "Eagle Warrior" or "Ancestral Hall" — when the embedding drifts toward a semantically related but wrong concept. BM25 catches exact terms; dense catches paraphrased or conceptual queries. They fail in opposite directions, so both run and get merged.

**Why RRF over combining raw scores:** dense similarity scores (~0.87) and BM25 scores (~14.3) are on incompatible scales — averaging them is meaningless. RRF merges by rank position only (`score = 1/(k + rank)`, k=60), so the scale mismatch doesn't matter.

**Why `dotproduct` over `cosine` on the Pinecone index:** cosine doesn't support hybrid sparse-dense search; the dense embeddings are L2-normalized by default, so dotproduct is mathematically equivalent to cosine on the dense side while also enabling sparse.

Measured impact: context relevance reached 2.94 — near-perfect, hybrid retrieval working as intended. See [RAG triad](#rag-triad-context-relevance-groundedness-answer-relevance) below for the full before/after.

## RAG triad: context relevance, groundedness, answer relevance

*(V2)*

V1's reference-based eval was replaced with three independent LLM-as-judge evaluators, run in parallel: Context Relevance (did retrieval surface the right chunks for this query?), Groundedness (is every claim in the response supported by those chunks?), and Answer Relevance (does the response address the question asked?). Groundedness specifically replaced Faithfulness, comparing against the *retrieved chunks* rather than an ideal answer — the fix for V1's blind spot.

Baseline scores (17 questions): CR 2.94 / G 2.65 / AR 2.88. High context relevance paired with low groundedness pointed directly at generation — specifically the persona — as the source of the remaining failures, rather than retrieval. That diagnostic precision is the entire value of the triad over a single blended score.

## Persona removed: the controlled experiment

*(V3, V4, V5)*

The Montezuma persona was a *hypothesis* for the groundedness failures, not an assumed cause. Rather than rewriting the prompt speculatively, the persona was removed, the eval was re-run, and groundedness was compared directly: 2.65 → 3.0, from a one-line system prompt change. Two remaining groundedness failures were a source-data conflict (two document versions describing the same ability differently) and a cross-version fabrication issue — the latter a known architectural limitation, not something a prompt change can fix.

## Hardening the triad: eval set cleanup and the answer relevance fix

*(V3)*

Two further fixes shipped alongside the persona removal. First, the Answer Relevance judge had no domain context and defaulted to real-world knowledge as its baseline — it penalized "Who is Alan Turing?" for not mentioning codebreaking, which is irrelevant in a Civ 6 context. Fix: switch that one judge to compare against an ideal answer instead of the bare query, and reword the question to scope it to game mechanics.

Second, the eval set itself had structural problems independent of the judges: questions with multiple valid answers (dropped), an ideal answer narrower than the game mechanic it described (reworded), and a genuine source-data discrepancy isolated by querying the vector store directly rather than assumed to be a generation error.

Final scores (15 cleaned questions): CR 3.0 / G 2.80 / AR 2.93.

## Parser only: router deleted for the ReAct agent

*(V4, V5)*

The Section Router chain was deleted entirely. The remaining Query Parser still cleans the query and extracts the version, but section routing is now handled implicitly by the ReAct agent choosing which tools to call.

## ReAct agent with 6 tools and cross-session memory

*(V4, V5)*

The deterministic LangGraph supervisor was replaced with a `create_react_agent` selecting from six typed tools, each wrapping the hybrid retrieval function with a section filter: units, leaders, great people, techs & civics, buildings & improvements, and a general catch-all. The agent reasons at runtime from each tool's description rather than following a pre-classified route.

**Rejected alternative:** keep improving the deterministic router's classification examples. Rejected because deterministic routing has a hard ceiling — it only handles query patterns someone thought to write an example for. An agent that reasons at runtime doesn't have that ceiling.

**What it cost:** less predictability and a runaway-cost risk, bounded with a per-turn recursion limit, a per-tool retrieval cap, and a per-chunk content size limit.

The agent's state management also made cross-session memory a small addition rather than a rewrite: a `MemorySaver` checkpointer keyed by `thread_id` persists conversation state across turns and sessions — a different memory mechanism, and a different scope, than the V2 supervisor's reducer, which only accumulated results *within* a single query.

## The eval breaks: what going agentic costs you

*(V4)*

Going agentic broke the eval pipeline, and that's a deliberate inclusion in this log rather than a detail to gloss over. The ReAct agent consumes retrieved documents inside its own reasoning loop — they're never surfaced as a return value — so `generate_response` returned only a string, and the Context Relevance and Groundedness judges had nothing to score.

Re-measured scores on the V4 architecture once the eval was restored (see next entry): CR 3.0 / G 2.73 / AR 2.80 — close to V3, with the small dip expected since V3's gains included a carefully cleaned eval set and persona removal already baked in.

## Eval rewired: ToolMessage extraction plus structured logging

*(V5)*

Two changes. First, the eval pipeline was rewired around `ToolMessage` objects in the agent's message history — they hold the exact string each tool returned, which is precisely what the LLM saw and the correct input for a groundedness check. `generate_response` now returns the response and those chunks as a tuple, and a fresh `thread_id` is generated per eval question to prevent memory bleeding across questions in the same eval run.

Second, the ingester gained structured JSON logging (consistent fields per log line: batch number, size, sections, versions, status, error type) and per-batch error handling, so a single Pinecone timeout no longer kills the entire ingestion run. In production, those logs would ship to a log aggregator — filtering by `status=error` and grouping by `error_type` separates a data-quality problem (failures concentrated in one section) from a connectivity problem (failures scattered across batches).
