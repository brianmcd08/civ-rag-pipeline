FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
# Serve extra only: the deployed image excludes the ingest/eval/notebook stack.
RUN uv sync --frozen --no-dev --extra serve

COPY . .

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]