import os
from dotenv import load_dotenv

load_dotenv()


_MISSING = object()


def get_secret(key: str, default=_MISSING) -> str:
    """
    Load a secret from Streamlit secrets if available (Streamlit Cloud),
    otherwise fall back to environment variables / .env (local dev).

    Pass `default` to make a secret optional; without it, a missing key raises.
    The st.secrets -> os.environ -> raise order matters and must not be
    shortcut to os.environ.get(): Streamlit Cloud has no environment variables,
    only st.secrets, so a plain env lookup would silently miss values that are
    set in production (e.g. API_BASE_URL defaulting to localhost).
    """
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        value = os.environ.get(key)
        if value is None:
            if default is _MISSING:
                raise EnvironmentError(f"Missing secret: {key}")
            return default
        return value
