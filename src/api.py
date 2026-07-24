from mangum import Mangum
from secrets import compare_digest
from typing import Literal

from pydantic import BaseModel
from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from contextlib import asynccontextmanager
from src.agent.construct_agents import build_checkpointer, build_agent
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
    # startup
    checkpointer, pool = build_checkpointer()
    try:
        app.state.agent = build_agent(checkpointer)
    except Exception:
        # Startup is aborting before yield, so the shutdown branch below
        # would never run; close the just-opened pool instead of leaking it,
        # then let the failure propagate so the app still refuses to start.
        if pool is not None:
            pool.close()
        raise

    yield

    # shutdown
    if pool is not None:
        pool.close()


app = FastAPI(lifespan=lifespan)


# Deliberately left open: it costs a Lambda invoke but no Bedrock tokens, and
# it is the "yes, this is really running" proof that can be handed out without
# handing out the key.
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_api_key)],
)
def query(req: QueryRequest, request: Request):
    answer, documents = generate_response(
        req.query,
        [m.model_dump() for m in req.history],
        req.thread_id,
        agent=request.app.state.agent,
    )
    return QueryResponse(response=answer, documents=documents)


handler = Mangum(app)
