# Wolf Trading OS — Phase 1 application image (dashboard + CLI).
# Analytics only: this image contains no broker connectivity and no order
# capability (see AGENTS.md rule 13).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Migrations + alembic config are needed at runtime (database-upgrade).
COPY alembic.ini ./
COPY migrations ./migrations

# Non-root runtime user.
RUN useradd --create-home --uid 1000 wolf
USER wolf

EXPOSE 8501

ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Default command: run migrations then serve the dashboard.
CMD ["sh", "-c", "wolf-trading-os database-upgrade && wolf-trading-os run-dashboard"]
