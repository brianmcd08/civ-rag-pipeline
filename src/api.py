from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from mangum import Mangum
from pydantic import BaseModel

from src.agent.construct_agents import close_agent, get_agent
from src.config import API_KEY_HEADER_NAME
from src.response_generator import generate_response
from src.secrets import get_secret

# Loaded at import so a misconfigured deployment refuses to start rather than
# coming up with an open /query. Same fail-fast posture as the checkpointer
# pool. Only the api surface imports this module, so Streamlit and the eval
# runner are unaffected.
API_SHARED_SECRET = get_secret("API_SHARED_SECRET")

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def require_api_key(provided: str | None = Security(api_key_header)) -> None:
    """
    Gate the expensive route. /query is public on the internet and every call
    spends Bedrock tokens, so this is the only control that prevents cost
    rather than reporting it after the fact — budget alerts and anomaly
    detection both lag by hours to a day.

    Compared as bytes with compare_digest: constant-time, and encoding first
    avoids the TypeError compare_digest raises on non-ASCII str input, which
    would otherwise turn a junk header into a 500.
    """
    if provided is None or not compare_digest(
        provided.encode("utf-8"), API_SHARED_SECRET.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


class Message(BaseModel):
    # Only the roles LangChain's message conversion accepts downstream;
    # anything else would surface as a 500 inside query_parser instead of
    # a clean 422 here.
    role: Literal["user", "assistant", "system"]
    content: str


class QueryRequest(BaseModel):
    query: str
    history: list[Message] = []
    thread_id: str


class QueryResponse(BaseModel):
    response: str
    documents: list[str]


@asynccontextmanager
async def lifespan(app):
    """Shutdown only. Construction happens in get_agent(), not here.

    The startup half used to build the checkpointer and agent and stash them on
    app.state. That was correct for a long-lived uvicorn and wrong for Lambda:
    Mangum runs the lifespan per INVOCATION, not per container, so every single
    request opened a ConnectionPool, ran PostgresSaver.setup(), built the agent,
    and closed the pool again. Verified two ways in 2026-07-24 — Mangum's
    adapter wraps each request's HTTPCycle in a LifespanCycle under the default
    lifespan="auto", and CloudWatch logged "PostgresSaver is ready" on every
    invocation including six consecutive warm /health calls.

    Moving construction into the lazy get_agent() singleton fixes that AND
    collapses the two construction paths this refactor exists to remove: every
    surface (Streamlit's client, uvicorn, Lambda) now builds the agent exactly
    one way. The handler below sets lifespan="off" so Mangum stops running this
    at all; Lambda destroys the execution environment wholesale, so there is
    nothing to clean up there anyway.

    What remains is for local runs: a Ctrl-C'd uvicorn should release its Neon
    connections rather than leave them to server-side timeout.
    """
    yield
    close_agent()


app = FastAPI(lifespan=lifespan)


# Deliberately left open, and now genuinely dependency-free: with construction
# out of the lifespan this touches nothing but the event loop, which is what a
# liveness probe should be. The tradeoff is that pinging it no longer wakes Neon
# or builds the agent, so it is no longer a warm-up. That is what /warm is for.
@app.get("/health")
def health():
    return {"status": "ok"}


# Key-gated even though it spends no model tokens, because it does open a Neon
# connection and run setup(). Left open it would let an anonymous caller drive
# database wake-ups against a 1 rps throttle.
@app.post("/warm", dependencies=[Depends(require_api_key)])
def warm():
    get_agent()
    return {"status": "warm"}


@app.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_api_key)],
)
def query(req: QueryRequest):
    answer, documents = generate_response(
        req.query,
        [m.model_dump() for m in req.history],
        req.thread_id,
        agent=get_agent(),
    )
    return QueryResponse(response=answer, documents=documents)


# lifespan="off" is the half of this change that actually saves the work. Without
# it Mangum would keep running the (now shutdown-only) lifespan per invocation,
# which would call close_agent() after every request and throw away the very
# singleton this step exists to reuse.
handler = Mangum(app, lifespan="off")
