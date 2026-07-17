# DARE Attribution API — minimal image for demo hosting (HF Spaces, Docker SDK).
# Build context is the dare-vng repo root; only dare/ + pyproject.toml are
# COPYed in (see .dockerignore) — no runs/, data/, or .env ever enter the image.
FROM python:3.11-slim

WORKDIR /app

# CPU-only torch wheel first, in its own layer: the default PyPI wheel bundles
# unused CUDA libs and is several times larger. Installed before
# requirements-api.txt so later installs see it already satisfied and don't
# pull the CUDA build back in from the default index.
RUN pip install --no-cache-dir torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# context_cite/utils.py calls nltk.download("punkt_tab") at import time.
# Baking it in at build time means a cold container start doesn't depend on
# nltk's download server being reachable.
RUN python -c "import nltk; nltk.download('punkt_tab')"

COPY dare/ ./dare/
COPY pyproject.toml .

ENV PYTHONUNBUFFERED=1
# HF Spaces' Docker SDK convention — must match app_port in the Space's
# README.md front-matter.
EXPOSE 7860

CMD ["uvicorn", "dare.api:app", "--host", "0.0.0.0", "--port", "7860"]
