"""Streamlit frontend. A thin HTTP client of the FastAPI backend.

This module must NOT import the pipeline (src.config, src.response_generator,
langchain, psycopg). After the consolidation the `serve` extra installs only
streamlit + httpx + dotenv, so those packages are not in this image and the
frontend holds no model or database credentials at all.
"""

import uuid

import streamlit as st

from src.api_client import ApiClient, ApiError
from src.constants import HISTORY_LIMIT
from src.secrets import get_secret

st.title("Civilization 6 BBG Assistant")


# --- Password gate ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("Enter password to continue:", type="password")
        if password:
            if password == get_secret("APP_PASSWORD"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()


check_password()
# --- End password gate ---


@st.cache_resource
def get_client() -> ApiClient:
    """One shared client per process. httpx.Client is thread-safe.

    Built lazily inside the function rather than at module scope so a missing
    secret surfaces as st.error + st.stop() rather than a stack trace on the
    login screen.
    """
    return ApiClient(
        base_url=get_secret("API_BASE_URL", None),
        api_key=get_secret("API_SHARED_SECRET", None),
    )


try:
    client = get_client()
except Exception as e:
    st.error(f"The app cannot reach its backend: {e}")
    st.stop()

# Wake the backend once per session, AFTER the password gate so anonymous
# visitors cannot drive Lambda invocations against a 1 rps throttle. The flag
# is set even on failure, so a down backend costs one failed ping per session
# rather than one per rerun. session_state rather than @st.cache_resource
# because Lambda goes cold within minutes, and a process-wide cache would skip
# the warm-up for exactly the sessions that need it.
# NOTE: /warm does not exist until Step 7, so this 404s until then. warm() is
# best-effort and never raises, so that is a no-op.
if not st.session_state.get("warmed"):
    with st.spinner("Waking the backend..."):
        client.warm()
    st.session_state["warmed"] = True

with st.sidebar:
    st.header("About")
    st.write(
        "Ask about BBG (Better Balance Game) mod balance changes, unit stats, "
        "leader abilities, wonders, policies, and more. Versions include 7.1 through 7.5."
    )
    st.header("Try asking")
    st.markdown("""
- What does the Eagle Warrior do?
- Which civilization has the Ice Hockey Rink?
- What changed for cavalry units in v7.4?
- When was Austria introduced?
- What is the Oligarchy policy card?
""")

st.write(
    "Ask anything about Civ 6 BBG including units, leaders, balance changes, wonders, and more."
)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about units, leaders, balance changes, or wonders..."):
    # Captured BEFORE appending the user turn, which is what lets the except
    # branch below pop it cleanly. It also turns the old
    # [-(HISTORY_LIMIT + 1):-1] slice into a plain [-HISTORY_LIMIT:].
    prior_messages = st.session_state.messages[-HISTORY_LIMIT:]

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                answer, _ = client.query(prompt, prior_messages, st.session_state["thread_id"])
        except ApiError as e:
            # Drop the dangling user turn so a retry does not send it twice.
            st.session_state.messages.pop()
            st.error(str(e))
        else:
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.markdown(answer)
