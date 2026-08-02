"""Isolate the suite from whatever `.env` sits in the working directory.

pydantic-settings loads `.env` at import, so a developer's local file (smoke token, real
API key) silently changes what the tests exercise: with a token set, every unauthenticated
request 401s and the suite measures an environment nobody intended. Same class as
FAIL-0008 — the test environment must be pinned, not inherited.
"""
import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    monkeypatch.setattr(settings, "smoke_test_token", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
