from typing import Literal

from pydantic import BaseModel
from fastapi import FastAPI, Request

from contextlib import asynccontextmanager
from src.agent.construct_agents import build_checkpointer, build_agent
from src.response_generator import generate_response


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    answer, documents = generate_response(
        req.query,
        [m.model_dump() for m in req.history],
        req.thread_id,
        agent=request.app.state.agent,
    )
    return QueryResponse(response=answer, documents=documents)
