import streamlit as st
import uuid

from src.response_generator import generate_response
from src.config import HISTORY_LIMIT

st.title("Civilization 6 BBG Assistant")


# --- Password gate ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("Enter password to continue:", type="password")
        if password:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()


check_password()
# --- End password gate ---

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
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        prior_messages = st.session_state.messages[-(HISTORY_LIMIT + 1) : -1]
        answer = generate_response(
            prompt, prior_messages, st.session_state["thread_id"]
        )

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.markdown(answer)
