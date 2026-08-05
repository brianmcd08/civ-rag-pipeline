"""HTTP client for the civ-rag API. The Streamlit frontend's only backend.

IMPORT RULE: this module may import `httpx`, `src.constants`, and
`src.secrets`. NOTHING ELSE FROM `src/`.

That restriction is the whole point of the module. After the consolidation,
the Streamlit surface installs only the `serve` extra (streamlit + httpx +
dotenv), so langchain, langgraph, psycopg, pinecone and openai are simply not
present in its image. Importing `src.config` here would also pull a live
`ChatAnthropic`/`ChatBedrockConverse` construction and require an API key the
frontend no longer holds. A verification gate asserts this rule holds by
checking `sys.modules` after import, so a stray import fails loudly.
"""

import httpx

from src.constants import API_KEY_HEADER_NAME

DEFAULT_BASE_URL = "http://localhost:8000"

# connect: a wrong base URL or a stopped local API should fail fast and
# actionably rather than hanging.
CONNECT_TIMEOUT = 5.0
# read: deliberately ABOVE API Gateway's hard 30s integration timeout so the
# gateway's 504 wins the race. A 504 names its own cause; a client-side
# ReadTimeout is ambiguous between a slow backend and a dead one.
READ_TIMEOUT = 35.0


class ApiError(Exception):
    """A user-facing failure. The message is already suitable for st.error()."""


class ApiClient:
    """Thin wrapper over the /query, /warm and /health routes.

    Holds one reusable httpx.Client. httpx.Client is thread-safe, so a single
    instance shared across Streamlit reruns (via @st.cache_resource) is correct
    and avoids reopening a TLS connection per question.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={API_KEY_HEADER_NAME: api_key} if api_key else {},
            timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT),
        )

    def warm(self) -> bool:
        """Best-effort wake-up. NEVER raises.

        Pokes the backend so the user's first real question doesn't pay for
        waking Neon from autosuspend plus building the agent, which together
        can exceed API Gateway's 30s ceiling. Returns whether it succeeded, for
        logging only; a failure here must not block the UI, since the query
        path reports its own errors with better context.
        """
        try:
            resp = self._client.post("/warm")
            return resp.status_code == httpx.codes.OK
        except Exception:
            return False

    def query(self, query: str, history: list[dict], thread_id: str) -> tuple[str, list[str]]:
        """Ask a question. Returns (answer, documents).

        No automatic retry. A retry on the cold path buys a second full Bedrock
        generation for a request the warm-up should already have prevented.
        """
        try:
            resp = self._client.post(
                "/query",
                json={"query": query, "history": history, "thread_id": thread_id},
            )
        except httpx.ConnectError as e:
            raise ApiError(
                f"Could not reach the API at {self._base_url}. "
                "If you're running locally, start it with "
                "`docker compose up api` or "
                "`uv run --extra api uvicorn src.api:app --port 8000`."
            ) from e
        except httpx.ReadTimeout as e:
            raise ApiError(
                f"The API did not respond within {READ_TIMEOUT:.0f}s. Please try again."
            ) from e
        except httpx.HTTPError as e:
            raise ApiError(f"Could not reach the API: {e}") from e

        if resp.status_code != httpx.codes.OK:
            raise ApiError(self._describe(resp))

        data = resp.json()
        return data["response"], data["documents"]

    @staticmethod
    def _describe(resp: httpx.Response) -> str:
        """Turn a failure status into a message that names the fix."""
        code = resp.status_code
        if code == httpx.codes.UNAUTHORIZED:
            return (
                "The API rejected the key (401). The frontend's "
                "API_SHARED_SECRET does not match the backend's."
            )
        if code == httpx.codes.TOO_MANY_REQUESTS:
            return (
                "Rate limited (429). The gateway allows about 1 request per "
                "second. Wait a moment and try again."
            )
        if code == httpx.codes.GATEWAY_TIMEOUT:
            return (
                "The backend timed out (504). This is normal on the first "
                "request after a deploy, while the container starts. "
                "Try again."
            )
        if code == httpx.codes.UNPROCESSABLE_ENTITY:
            try:
                return f"The API rejected the request (422): {resp.json()['detail']}"
            except Exception:
                return "The API rejected the request (422)."
        return f"The API returned an unexpected error ({code})."
