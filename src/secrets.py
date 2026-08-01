import os
from typing import overload

from dotenv import load_dotenv

load_dotenv()

# Distinct from every real value, including None, so "caller passed nothing"
# is distinguishable from "caller explicitly wants None back".
_MISSING = object()


@overload
def get_secret(key: str) -> str: ...
@overload
def get_secret[T](key: str, default: T) -> str | T: ...


def get_secret(key: str, default: object = _MISSING) -> object:
    """
    Load a secret from Streamlit secrets if available (Streamlit Cloud),
    otherwise fall back to environment variables / .env (local dev).

    Pass `default` to make a secret optional; without it, a missing key raises.
    The st.secrets -> os.environ -> raise order matters and must not be
    shortcut to os.environ.get(): Streamlit Cloud has no environment variables,
    only st.secrets, so a plain env lookup would silently miss values that are
    set in production (e.g. API_BASE_URL defaulting to localhost).

    The overloads above are what callers see. Without them this would have to
    return `object`, and all seven existing call sites -- which assign into
    os.environ, call .encode(), or pass the value to Pinecone -- would need a
    cast. With them, get_secret("X") is str and get_secret("X", None) is
    str | None.
    """
    try:
        import streamlit as st

        return st.secrets[key]
    except Exception:
        value = os.environ.get(key)
        if value is None:
            if default is _MISSING:
                raise OSError(f"Missing secret: {key}") from None
            return default
        return value
