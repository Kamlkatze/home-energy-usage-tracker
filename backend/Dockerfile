FROM python:3.13.15-slim AS builder

RUN pip install uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen

FROM python:3.13.15-slim

# postgresql-client provides pg_dump/psql for the backup/restore feature.
# Debian trixie ships client v17 which is >= the postgres:16 server
# (pg_dump must never be older than the server version).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

EXPOSE 8000

CMD ["/bin/sh", "-c", "/opt/venv/bin/python -m alembic upgrade head && exec /opt/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]