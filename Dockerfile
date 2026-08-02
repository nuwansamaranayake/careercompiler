# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# git is required: aignite-groundwork resolves from a git+https URL (see pyproject.toml)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# NOTE: aignite-groundwork is a sibling editable dependency in local dev
# (pip install -e ../groundwork). In CI / image builds it resolves from the
# published wheel or a git ref; see .github/workflows/ci.yml.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip

COPY . .
RUN pip install .

# The entailment gate's runtime. The CPU wheel index is pinned HERE and in CI, never in
# pyproject.toml: a plain `pip install torch` on linux resolves the CUDA build, which is how
# four apps in this estate reached 5.6-5.8 GB images before ~20 GB was reclaimed by removing
# them. Verified after build: torch reports +cpu and torch.version.cuda is None.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      "torch==2.13.0" "transformers==5.14.1" \
 && rm -rf /usr/local/lib/python3.12/site-packages/torch/test \
           /usr/local/lib/python3.12/site-packages/torch/include

# Bake the pinned NLI checkpoint into the image. It is never downloaded at request time: the
# gate's availability must not depend on Hugging Face being reachable from a box that serves
# a live revenue product. Pinned by revision digest, not by tag (DECISIONS.md 001).
ENV HF_HOME=/opt/hf \
    NLI_MODEL=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli \
    NLI_MODEL_REVISION=6f5cf0a2b59cabb106aca4c287eed12e357e90eb
RUN python -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification as M;\
import os; mid=os.environ['NLI_MODEL']; rev=os.environ['NLI_MODEL_REVISION'];\
AutoTokenizer.from_pretrained(mid, revision=rev);\
M.from_pretrained(mid, revision=rev)" \
 && python -c "\
import torch; assert torch.version.cuda is None, 'CUDA torch leaked into the image'; \
print('torch', torch.__version__)"

# Build-time facts for the root page. Baked from build args so the deployed page can state
# what is actually running; absent values render as "unknown", never as a placeholder.
ARG APP_VERSION=unreleased
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
ENV APP_VERSION=$APP_VERSION GIT_SHA=$GIT_SHA BUILD_TIME=$BUILD_TIME

EXPOSE 8000
# Migrate, assert the expected table count (Standard 4), then serve.
CMD ["sh", "-c", "alembic upgrade head && python scripts/check_migrations.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
