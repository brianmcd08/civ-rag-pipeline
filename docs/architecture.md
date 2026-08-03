# Architecture

What this system is, why it is built this way, and what measurement caught along the way.

The evolution from V1 to V5 is not narrated here. Every design this replaced is in git history, and reconstructing it from a changelog embedded in the documentation helped nobody. What survives below is the current system and the decisions that shaped it, including the ones that were wrong first.

![Architecture evolution V1 to V5](civ_rag_evolution.png)

---

## The system today

A retrieval-augmented chatbot over the Better Balanced Game (BBG) mod documentation for Civilization VI, covering versions 7.1 through 7.5 plus the base game.

**A query flows through four stages.**

1. **Query parser.** A Claude call cleans the question (typos, explicit version references) and extracts the target BBG version. When no version is named it falls back to the latest.
2. **Agent.** A ReAct agent built with `create_agent` (LangChain's factory, returning a `langgraph.graph.state.CompiledStateGraph`) reasons at runtime about which retrieval tools to call. Six tools cover units, leaders, great people, techs and civics, buildings and improvements, and a general catch-all. It can call several in sequence when a question spans sections.
3. **Retrieval.** Each tool issues a hybrid query against Pinecone: a dense vector from `text-embedding-3-small` and a sparse BM25 vector, alpha-weighted and combined in one call. Version and section metadata filters apply per tool.
4. **Generation.** The agent synthesizes the retrieved chunks into a grounded answer.

**Retrieval mechanics worth stating precisely.** Fusion is **alpha-weighted, not reciprocal rank fusion** — the dense vector is scaled by `ALPHA` and the sparse by `1 - ALPHA`, then handed to Pinecone's native sparse-dense hybrid query. There is no rank constant anywhere in the code. This uses the raw Pinecone client rather than LangChain's `PineconeVectorStore`, because the wrapper cannot send a sparse vector. Pinecone requires a `dotproduct` index for hybrid search; that is a platform constraint, not a choice.

**Chunking is structure-based: one entity, one chunk, one vector.** Each scraped record becomes exactly one chunk. There is no fixed-size text splitter anywhere — no `RecursiveCharacterTextSplitter`, no `chunk_size` or `chunk_overlap` — because the source is already structured typed records rather than long-form prose, so the chunk boundary already falls on the semantic entity boundary. The honest gap: there is no length guard, so an unusually long entry would hit `text-embedding-3-small`'s ~8191-token ceiling rather than degrade gracefully. Source records are naturally short, so it has not happened.

**Version filtering works by list membership.** Ingestion groups entries by content hash and stores each chunk **once**, tagged with every version sharing that content: `bbg_version: ["7.3","7.4","7.5"]`. Queries send a single scalar `$eq`, which Pinecone matches against a list field by membership, so one filter value correctly returns every chunk valid in that version. Point-in-time questions work; "when was X introduced" works by omitting the filter and taking the earliest version. **What is not supported is a version range or contrast** ("what changed between 7.1 and 7.5"), because the query side can only send one value. That is a query-side limit, not a storage one, so the fix is to emit multiple versions and fan out, the way section routing already does.

**Memory** is a `PostgresSaver` checkpointer keyed by `thread_id`, backed by Neon managed Postgres. It is **Postgres or nothing**: an unset or unreachable `DATABASE_URL` raises and the service refuses to start. Callers that genuinely need no persistence — the test suite and the eval runner, both single-turn — inject `checkpointer=None` rather than relying on a fallback. Each session gets a fresh `thread_id`, so context carries within a session but a returning user starts blank; persisting `thread_id` to a cookie is the known next step.

**Evaluation** is the RAG triad, three independent LLM-as-judge scorers over a fixed 15-question set. Context relevance grades whether retrieval surfaced enough to fully answer (partial scores 2, complete scores 3, so it measures sufficiency rather than topicality), groundedness grades whether the response is supported by the retrieved chunks, and answer relevance grades the response against an ideal answer.

| Metric | Score |
|---|---|
| Context relevance | 3.00 |
| Groundedness | 2.73–2.93 |
| Answer relevance | 2.93 |

Groundedness is a **range, not a point**: generation is not temperature-pinned, so re-running the same eval at n=15 moves it within that band. Any single number quoted for it is an artifact of one run.

**Deployment: one production path.**

```
Streamlit Cloud  →  API Gateway  →  Lambda  →  Neon + Bedrock
```

The Streamlit app is a thin HTTP client. It holds `APP_PASSWORD`, `API_SHARED_SECRET` and `API_BASE_URL`, and has no model or database credentials and no `psycopg` in its image. The FastAPI service behind it exposes `GET /health` (open, dependency-free), `POST /warm` and `POST /query` (both key-gated). Local development mirrors the same topology through Docker Compose: `db` → `api` → `app`. Inference runs on Bedrock **only on the Lambda path**, via the global inference profile `global.anthropic.claude-sonnet-4-6`; Streamlit Cloud and local development use the direct Anthropic client, gated by `LLM_PROVIDER`. It is the same Sonnet 4.6 tier either way — only the transport differs, so this is not a migration to Bedrock.

**Constants** (`src/config.py`): `ALPHA = 0.5`, `K_SECTION = 5`, `K_GENERAL = 8`, `RECURSION_LIMIT = 25`, `K_INGEST = 25`. Three of those are 25 and they mean different things.

---

## Decisions

### Hybrid retrieval rather than dense-only

Dense embeddings miss exact game terminology — "Eagle Warrior," "Ancestral Hall" — when the embedding drifts toward a semantically related but wrong concept. BM25 catches exact terms, dense catches paraphrase. They fail in opposite directions, so both run. Alpha-weighting exists because cosine-style and BM25 scores live on incompatible scales and cannot simply be added; scaling each by a weight summing to 1 makes `ALPHA` a tunable dial between keyword precision and semantic recall.

**Cost:** `ALPHA` has sat at 0.5 since it was introduced and has never been tuned against the eval set for this corpus. That is an open measurement, not a defended default.

### An agent rather than a deterministic router

The pipeline previously classified each query to a content section, then retrieved. That has a hard ceiling: it only handles query patterns someone wrote a routing example for. An agent reasoning from tool descriptions has no such ceiling, and its state management made conversation memory a small addition rather than a rewrite.

**Cost:** less predictability and a runaway-cost risk, bounded with a per-turn recursion limit, a per-tool retrieval cap, and a per-chunk size limit. The recursion limit bit a real query — a multi-section question exhausted a limit of 10 and raised `GraphRecursionError`, because each tool call costs two graph super-steps, so 10 bought only about four tool calls. Raised to 25 and wrapped in a handler that returns a graceful message. **The ceiling is headroom; the catch is the actual guard.**

**Worth knowing:** the agentic build is not clearly better than the deterministic one it replaced. Measured on the same eval, groundedness lands at parity within run-to-run noise. The deterministic pipeline earns groundedness structurally, through constrained generation, rather than paying for model capability, and it remains the thing to A/B first under cost pressure. The agent won on flexibility, not on scores.

### The RAG triad rather than reference-based scoring

The original eval compared responses against hand-written ideal answers on faithfulness and relevance. Neither judge received the retrieved chunks, so the judge fell back on its own training data to decide whether a claim was "supported" — meaning **a hallucination that agreed with training data could score a 3.** It was measuring agreement with the model's priors, not RAG quality, and a retrieval failure and a generation failure produced the same low score with no signal about which stage broke.

Giving groundedness the chunks directly fixes both problems at once. Low groundedness with high context relevance points at generation; low context relevance points at retrieval. That localization is the entire value.

**A defect this document found in itself.** The three judges are fired with `asyncio.gather`, and for months they **executed sequentially**: each was an `async def` with no `await` inside, wrapping the synchronous `anthropic.Anthropic()` client, so every coroutine blocked the event loop for its full API call. Total judge time was the sum rather than the max, and nothing errored or warned — the structure of concurrency with none of it. It was caught by verifying this document against the code rather than by any test or metric, which is the point worth keeping: the failure mode is invisible to everything except reading the call. Fixed by swapping the three judge files to `AsyncAnthropic` with a real `await`.

### The checkpointer raises rather than falling back

There used to be an in-memory fallback when the database was unset or unreachable, and it was made observable with a log line on the degraded path. **Observability was the wrong fix.** A degraded deployment was still one that had stopped persisting anything while continuing to look healthy, and a log line is not a control on a portfolio app nobody monitors. Failing to start is correct for a service whose whole job is durable conversation state.

Demonstrated rather than assumed: against the same unreachable database, the old build fell back, logged, and served normally; the current build raises `PoolTimeout` after a bounded wait and logs `Application startup failed. Exiting.`

### Serverless, outside a VPC

A Lambda inside a VPC has no route to the internet without a NAT Gateway, which bills roughly $32/month before moving a byte, and it would be needed to reach Neon, Pinecone, OpenAI and Bedrock alike. Outside a VPC the function gets managed egress free. That single omission, plus an HTTP API (per-request) instead of an Application Load Balancer (~$16/month standing), is what holds this near zero. The account has **no free tier** — ruled ineligible at setup — so everything bills from the first dollar against a $10/month budget. Recurring cost is ECR storage, about $0.05/month per image, capped at three by lifecycle policy.

**Cold starts have two regimes, and the variable is image-cache state, not idle time.** First invocation after an image push has to fetch and unpack from ECR inside the init phase, which blows Lambda's hard 10s init cap and re-runs initialization inside the invoke — 21.6 to 24s. Once the image is cached, init runs 5.5–6.4s, and that number is **flat from five minutes of idle out to 16.3 hours**. Warm: `/health` around 51–141ms, `/query` around 9s, a follow-up on the same thread around 3s. Container-image Lambdas bill the init phase, so a 683ms request behind a 6.3s init is billed at 6,958ms. API Gateway caps its integration timeout at 30s, so only the post-push regime can return a 504 while the function runs to completion and stays warm. **The demo protocol is therefore to call `POST /warm` first, then `/query`.**

**Rejected: a scheduled warmer.** Pinging every five minutes would cost about $0.02/month in AWS terms and would largely eliminate cold starts. Rejected because the ping is what keeps Neon's compute awake, running the free plan's metered compute against a schedule instead of against real traffic. The AWS saving is real and the Neon cost is larger.

### One construction path on every surface

The agent and its pooled checkpointer are built once per process by a lazy singleton, and **every surface uses that path** — local uvicorn, Compose, and Lambda alike. On Lambda this required `handler = Mangum(app, lifespan="off")` and a shutdown-only lifespan, because Mangum runs an ASGI lifespan **per invocation, not per container**: left on, it would tear down the singleton after every request. Verified in CloudWatch: one log stream, one container, seven invocations, exactly one construction.

The pool runs `min_size=0` so an idle warm container parks no database connection and Neon's autosuspend still works. `check=ConnectionPool.check_connection` validates a connection on borrow, which matters *more* under reuse rather than less, because a container can be frozen and thawed with arbitrary time in between.

`POST /warm` exists because this change made `/health` genuinely dependency-free — correct for a liveness probe, and useless as a warm-up. It is key-gated: it spends no model tokens but does wake the database, and left open it would let anonymous callers drive that against a 1 rps throttle.

**Why the query handler is a plain `def`.** `generate_response` is blocking synchronous code. FastAPI runs `async def` handlers on the event loop, where blocking would freeze the server, but runs plain `def` handlers in a threadpool. So concurrent requests land on different threads, which is precisely why a connection *pool* is required rather than a single connection. Verified: five parallel requests that would take about 46s serialized completed in about 18.5s. Full async was rejected because the Lambda target is one request per container.

---

## What measurement caught that review didn't

These are five instances of one thing: **a green result that was not verifying what it appeared to verify.** Each was found by measuring rather than reasoning, and each changed a conclusion that had already been drawn and acted on.

### The eval passed two questions for the wrong reason

The agent was asked for the Aztec unique unit in BBG 7.5 and answered "Jaguar" — the Civ 5 unit. The eval set contained this exact shape twice, "name the unique unit for Cree" and "name the Gallic unique unit," and both passed.

They passed because **their priors happened to be corpus-correct.** Cree → Okihtcitaw and Gaul → Gaesatae match both vanilla Civ 6 and BBG, so the model's training data and the corpus agreed and no wrong answer ever surfaced. The one discriminating case, where a strong conflicting prior exists, was not in the set.

The judge scores across runs were 3, 3, 3, and **2** — so groundedness *did* catch it, once, on the Gaul row, stating the mechanism exactly: *"the documents do not explicitly name the unit 'Gaesata' — the name is not mentioned anywhere in the provided documents. The combat characteristics and other details are fully supported, but the unit name itself cannot be verified."* It missed the same failure three other times, including the most flagrant: in one run the model answered that the Cree unique unit is the **"Tracker"**, a name absent from the documents and not even correct, and groundedness called it fully grounded at 3.

**So the blind spot was not structural — it was aggregation.** Nothing about the judge's inputs prevented the catch; an ungrounded proper noun is detectable from chunks plus response alone. But one 3→2 in a 15-row set moves the mean by about 0.07, well inside run-to-run variance, so the single real detection read as noise. From the same row, the context relevance judge reasoned its way to the right conclusion and then contradicted itself in its own score: *"Wait — actually the documents do NOT explicitly name the unit, they only describe it as 'Gallic unique Ancient era unit that replaces the Warrior.'"* Score: 3. **Reasoning field right, score field wrong.** That is the sharpest available argument for reading judge reasoning instead of aggregating averages.

**The detector was also the wrong one.** Groundedness measures faithfulness, not correctness, and was never going to reliably catch a wrong *name*. Answer relevance is the reference-based judge, and it fired correctly with a 1 against "Tracker" on the same row where groundedness said 3.

**The fix is three parts and none have shipped.** Field- and entity-level grounding, so a response is penalized when the specifically requested entity is absent even if surrounding detail matches. Corpus-divergent eval cases, so a correct-looking prior can no longer mask a retrieval failure. And **online groundedness on live traffic**, which is the only one that does not require imagining the failure class first — an offline set can only contain failures someone already thought of, while online eval grades whatever users actually ask. Groundedness has to be the online detector because answer relevance needs a reference answer that novel queries do not have. It also repairs the inconsistency above: a judge that catches a failure one time in four is useless on one scored instance per run, but produces a legible cluster across dozens of real hits. **Volume converts an unreliable per-call judge into a reliable signal.** The cost is a second model call in the request path.

### The regression I announced a revert for was a one-line bug

The same Jaguar failure was diagnosed as a training prior overriding correct retrieval, and that diagnosis was published along with an announced intent to revert to the deterministic pipeline.

Tracing the query showed it routing to the wrong tool — `search_leaders`, not `search_units`. `search_leaders`'s docstring advertised "unique units," but unit records live in the units section, and the leaders chunk describes the unit's abilities without ever naming it. **The retrieved context genuinely never contained "Eagle Warrior."** The model filled the missing name from its prior. Where the corpus agreed with the prior the answer looked right; where it conflicted, the answer was visibly wrong. Same mechanism both times.

"Are you sure?" did not make the agent re-read anything. The parser rewrites the challenge back into the original question using conversation history, and the agent fires a **new** tool call against a different tool, retrieving a genuinely new chunk. Trace-confirmed: exactly one new tool message on the challenge turn. The correction came from new retrieval, not from re-attention.

The fix was one line — the docstring redirects unit queries to `search_units`. Before: 5 of 5 wrong on turn 1. After: 5 of 5 correct, no challenge needed. **Model-independent**, holding on both Haiku and Sonnet. The revert was never made and was not needed.

**The probe trap.** A more capable model misroutes identically and only "passes" the canonical probe because its prior happens to be corpus-correct. A right answer proves nothing when the prior and the corpus agree. This is why discriminating evaluation needs facts where the corpus deliberately **disagrees** with training data — which is exactly what the divergent stat probe was built on: BBG stat values diverge from vanilla (Eagle Warrior costs 32, not 65), and the raw model gets 0 of 12 right while the pipeline grounds 12 of 12. That probe is the clean evidence that retrieval overrides a confident prior when the right chunk is present, and it doubles as the control proving the Jaguar was a routing failure rather than a grounding one.

Three things had been conflated under one label: a tool-routing bug, the probe trap, and prior gap-filling. Untangling them took a traced re-investigation, not a better hypothesis.

### Three fixes that reported success and did nothing

**A dependency fix that was never read.** The live app started throwing `ModuleNotFoundError: No module named 'psycopg'`. A `requirements.txt` was added at the repo root and the app rebooted. Same error, unchanged. Streamlit Cloud resolves dependencies from whichever manifest it finds first in a fixed precedence order — `uv.lock` > `Pipfile` > `environment.yml` > `requirements.txt` > `pyproject.toml` — and this repo committed `uv.lock` at the root, so it always won. **`requirements.txt` was never read regardless of its contents**, and the reboot rebuilt from the same file it had been using all along. The fix was two actions, not one: `uv.lock` had to be **deleted from version control** and then gitignored, since gitignoring a tracked file changes nothing. The lockfile was removed from version control, not abandoned; it still exists locally and `uv` regenerates an ephemeral one on demand.

**A deploy that never deployed.** Streamlit Cloud's auto-deploy is not reliable. Three consecutive pushes produced no pull at all and production served stale code for five and a half hours, while the logs showed a perfectly convincing history. Related: **removing a secret does not trigger a redeploy either**, so a deletion looks safe because the running process keeps working — the reboot is what proves the app can *start* without it. And a merge alone is not enough, because the platform reads GitHub rather than a local branch. Every one of these presents as a working app, which is the whole problem.

**A deploy that reported no changes, from two opposite directions.** `variable "image_tag"` carried `default = "latest"`. Run by hand without `-var="image_tag=..."`, `terraform apply` fell back to that default, compared an unchanged `image_uri` string, found no diff and exited 0 while Lambda kept serving the previous image. The inverse is worse. Passing a tag that was never pushed fails `UpdateFunctionCode` with `InvalidParameterValueException`, and **Terraform writes the new `image_uri` into state anyway** — so state named an image that was not live, and the next plan would have compared the bad tag against itself, found no diff, and reported a genuine deploy as a no-op. Reached from the opposite direction, the identical end state. Both are closed by removing the default, which makes the variable required and forces every deploy through `deploy.sh`, and by a `data "aws_ecr_image"` read that fails during **plan** when the tag is absent from ECR, before anything reaches state. Worth noting what the first one hid in the meantime: a plan during the consolidation showed production running `40e6043-dirty-20260724141932`, an image built from an uncommitted working tree.

### Two failures whose cause was not what it looked like

**A stale connection that read as intermittent.** A pooled Neon connection went stale during an idle gap and the pool handed it out without validating it, so the **caller** ate the error; the pool logged "discarding closed connection" only afterward, replaced it, and the next query succeeded. That reporting order is why it presented as intermittent rather than as a broken database: the visible error lands on one user, and whoever investigates a minute later cannot reproduce it. Neon's free plan scales compute to zero after five minutes, which is fixed and not configurable, so any gap longer than that killed exactly the connection the pool was parking. `max_idle` would not have helped and is the plausible-looking wrong answer: it reaps only connections *above* `min_size`, and the one being killed was the one *at* it.

**A cold start blamed on the wrong thing.** Slow first requests were attributed to the database endpoint and to Neon being cold. Measurement showed the variable is **image-cache state** — flat latency from five minutes to 16.3 hours of idle rules out idle time entirely, and the 16.3-hour measurement came back at the *fast* end of the band.

### The fix that removed a guarantee, with nothing to show it had

Moving construction into a container-lifetime singleton required `min_size=0`, so an idle warm container would park no database connection. That worked. It also removed the fail-fast bound on a bad `DATABASE_URL` without any signal.

The guard had been `pool.open(wait=True, timeout=10)`. With nothing to pre-open, that call returns immediately, so the first operation actually needing a connection became `PostgresSaver.setup()` — which falls through to psycopg_pool's **default 30s borrow timeout**. Measured against a refused URL: `couldn't get a connection after 30.00 sec`. On Lambda that is a real regression rather than a cosmetic one, because API Gateway's integration timeout is a hard 30 seconds, so a misconfigured database would race the gateway and surface as an ambiguous 504 instead of a diagnosable 500.

The fix is one argument: `timeout=10` on the pool constructor, setting the default borrow timeout explicitly. Re-measured at 10s.

**What is worth taking from this one:** the change was correct, tested, and verified working, and it still broke something. It was caught only because the plan for the change carried an explicit instruction to re-check what fail-fasts afterward. A mechanism correction needs a sweep of everywhere the old mechanism was cited, not just the place it was found.

---

## Known gaps, stated plainly

- **Ingestion never deletes.** It inserts or overwrites by content hash, so additions and metadata-only edits are handled correctly, but the two operations requiring removal are not. A **replace** is the sharper failure: changed content lands under a new hash while the old vector persists with its original version list, so a version-filtered query can return **both** the old and new facts as context. A remove leaves an orphan. The fix is wipe-and-rebuild at this scale, ID-diff pruning at real scale.
- **No forward upgrade-path data in the corpus.** Every "what does X upgrade to" question is unanswerable from retrieval, and the model bridges the gap from base-game knowledge — producing an answer that is correct about the game and unfaithful to the sources. Harder to catch than a missing name, because every entity is present and grounded and only the *relation* between them is invented.
- **No caching anywhere.** Asking the same question twice re-runs the whole pipeline at full token cost and latency. The conversation checkpointer is not a cache; it carries multi-turn context but short-circuits no recomputation.
- **No reliability toolkit on the retrieval path.** No timeout, retry, or circuit breaker around the hybrid query or the six tools.
- **Single-user ceiling.** `max_size=5` against FastAPI's ~40-thread handler pool would starve under sustained concurrency; it is inert on Lambda, which gets one request per container.
- **Terraform state is a local file** with no remote backend, so no locking and no durability beyond one machine. Correct for one operator, wrong for two. Secrets live in Lambda environment variables and therefore also in plaintext in that state file; the production answer is Secrets Manager or SSM.
- **The deploy IAM user holds `IAMFullAccess`**, which means a credential that can grant itself anything. "Scoped deploy user" would overstate it.
