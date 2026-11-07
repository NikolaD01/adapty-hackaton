# Backend image: FastAPI app + the Adapty CLI (C's activation calls it as a subprocess).
FROM node:20-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

# Pinned: CLAUDE.md §5 facts were verified on this version.
RUN npm install -g adapty@0.18.0 && npm cache clean --force

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADAPTY_CLI=adapty
RUN python3 -m venv $VIRTUAL_ENV

WORKDIR /app
# Dependencies first so code edits don't reinstall them.
COPY pyproject.toml ./
COPY feature_signal/__init__.py ./feature_signal/__init__.py
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .

# CLI login is stored here; compose mounts a named volume so it survives rebuilds.
RUN mkdir -p /home/node/.config/adapty /app/data && chown -R node:node /home/node/.config /app
USER node

EXPOSE 8000
CMD ["uvicorn", "feature_signal.main:app", "--host", "0.0.0.0", "--port", "8000"]
