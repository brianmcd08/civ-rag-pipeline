import streamlit as st
import uuid

from src.response_generator import generate_response
from src.config import HISTORY_LIMIT

st.title("Civilization 6 Chatbot")


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

st.write("What would you like to know about Civ 6 BBG?")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("You got a question for Monte?"):
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
