.PHONY: dev lint test smoke migrate eval format quality e2e guide

dev:
	uvicorn app.main:app --reload --host $(API_HOST) --port $(API_PORT)

lint:
	ruff check .

test:
	pytest

smoke:
	python scripts/smoke_test.py

migrate:
	alembic upgrade head
	python scripts/check_migrations.py

eval:
	python scripts/eval.py

format:
	ruff format .

# The single gate: lowest coverage of backend and frontend, floor 96, every check runs.
quality:
	python scripts/quality_gate.py

# Browser suite alone. Needs web/out built and the NLI weights under HF_HOME.
e2e:
	CC_E2E=1 pytest tests/e2e --no-cov

# Recapture the guide's screenshots, rebuild so the export carries them, print the PDF.
guide:
	cd web && npm run build
	python scripts/capture_guide.py
	cd web && npm run build
	python scripts/capture_guide.py --pdf-only
