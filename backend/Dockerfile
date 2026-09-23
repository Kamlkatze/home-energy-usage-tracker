FROM python:3.13.15-slim AS builder

RUN pip install uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen

FROM python:3.13.15-slim

WORKDIR /app

COPY --from=builder /app/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

EXPOSE 8000

CMD ["/bin/sh", "-c", "/opt/venv/bin/python -m alembic upgrade head && exec /opt/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]