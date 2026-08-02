"""contracts.md is enforced, not aspirational (Doctrine Rule 6).

The table is derived from the served OpenAPI schema, never from the router source: router
decorators are pre-prefix declarations, so the source shows paths a client cannot call.
Enforcement is literal — path parameter spellings included — because the previous, normalised
comparison let `{id}` drift from the served `{cid}` while staying green. Four assertions:
every implemented row is served exactly, every served operation has an implemented row, every
planned row is NOT served yet (so implementing a route forces its row to flip), and nothing
marked out-of-schema leaks into the schema.
"""
from pathlib import Path

from app.main import app

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts.md"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
# Served by FastAPI, or deliberately excluded from the schema (the front door). Documented
# in the table for humans, excluded from the schema comparison by their status marker.
OUT_OF_SCHEMA = "implemented (not in schema)"


def _rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in CONTRACTS.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[1] in METHODS:
            rows.append((cells[1], cells[2].strip("`"), cells[3]))
    return rows


def _served() -> set[tuple[str, str]]:
    return {(method.upper(), path)
            for path, methods in app.openapi()["paths"].items()
            for method in methods}


def test_every_implemented_contract_row_is_served_literally():
    served = _served()
    implemented = [(m, p) for m, p, status in _rows() if status == "implemented"]
    assert implemented, "no implemented rows parsed from contracts.md"
    missing = [row for row in implemented if row not in served]
    assert not missing, (
        f"contracts.md rows not served exactly as written: {missing}. The table derives "
        "from /openapi.json — copy the served path, parameter names included, never the "
        "router source.")


def test_every_served_operation_has_an_implemented_row():
    implemented = {(m, p) for m, p, status in _rows() if status == "implemented"}
    undocumented = [op for op in _served() if op not in implemented]
    assert not undocumented, f"served operations missing from contracts.md: {undocumented}"


def test_planned_rows_are_not_served_yet():
    """A planned row that is actually served means the contract was not updated when the
    code landed. Implementing a route must flip its row to `implemented`."""
    served = _served()
    stale = [(m, p) for m, p, status in _rows()
             if status.startswith("planned") and (m, p) in served]
    assert not stale, f"these rows are served but still marked planned: {stale}"


def test_out_of_schema_rows_are_genuinely_out_of_schema():
    """The front door and the docs UI are documented for humans but must not appear in the
    schema; no gate may enumerate the front door from openapi.json, which only holds if it
    stays out."""
    served = _served()
    leaked = [(m, p) for m, p, status in _rows()
              if status == OUT_OF_SCHEMA and (m, p) in served]
    assert not leaked, f"rows marked out-of-schema are in the schema: {leaked}"


def test_every_served_business_path_carries_the_mount_prefix():
    """The prefix is applied at mount. A served path without it would mean the router was
    mounted bare, which is the drift this file exists to catch."""
    bad = [p for _, p in _served() if not (p.startswith("/api/v1/") or p == "/health")]
    assert not bad, f"served paths outside /api/v1 (or /health): {bad}"
