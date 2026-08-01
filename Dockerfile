### Multi-stage: one file, two runnable surfaces, selected by Compose `target:`.
#
# Both targets share `base`, so the uv install and the pyproject/uv.lock copy
# build once and cache. Each target then installs only its own extra and gets
# its own CMD, which is what keeps the frontend image from carrying the
# pipeline stack once Step 5 drops serve-core from the `serve` extra.
#
# NOTE: `api` is intentionally LAST, so a plain `docker build .` with no
# --target produces the backend. Compose pins both services explicitly with
# `target:` rather than relying on that ordering.
#
# Dockerfile.lambda is deliberately NOT merged into this file: different base
# (the AWS Lambda Python image), installs with `uv pip install --target`
# instead of `uv sync`, and bakes NLTK corpora. Both consume the same uv.lock,
# so package VERSIONS cannot drift between them; only the install layout does.

FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./


### Streamlit frontend.
FROM base AS app

# serve extra only: excludes the ingest/eval stack. Still pulls serve-core
# until Step 5, so this image is temporarily fatter than its end state.
RUN uv sync --frozen --no-dev --extra serve

COPY . .

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]


### FastAPI backend.
FROM base AS api

RUN uv sync --frozen --no-dev --extra api

COPY . .

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.api:app", \
     "--host", "0.0.0.0", "--port", "8000"]
