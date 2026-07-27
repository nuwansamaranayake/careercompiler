"""contracts.md is enforced, not aspirational (Doctrine Rule 6): every implemented
method+path row must be served, and every served operation must have a contract row.
CI runs this with the rest of the suite, so the file cannot drift from the OpenAPI spec."""
import re
from pathlib import Path

from app.main import app

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts.md"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
# Served by FastAPI outside the OpenAPI paths object (the docs UI and the schema itself).
DOC_ROUTES = {("GET", "/docs"), ("GET", "/openapi.json")}


def _norm(path: str) -> str:
    # Path-parameter *names* ({id} vs {cid}) are not part of the wire contract.
    return re.sub(r"\{[^}]+\}", "{}", path)


def _contract_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in CONTRACTS.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[1] in METHODS:
            rows.append((cells[1], _norm(cells[2].strip("`")), cells[3]))
    return rows


def _served_ops() -> set[tuple[str, str]]:
    return {(method.upper(), _norm(path))
            for path, methods in app.openapi()["paths"].items()
            for method in methods}


def test_every_implemented_contract_row_is_served():
    served = _served_ops() | {(m, _norm(p)) for m, p in DOC_ROUTES}
    implemented = [(m, p) for m, p, status in _contract_rows() if status == "implemented"]
    assert implemented, "no implemented rows parsed from contracts.md"
    missing = [row for row in implemented if row not in served]
    assert not missing, f"contracts.md rows not in the served OpenAPI spec: {missing}"


def test_every_served_operation_has_a_contract_row():
    documented = {(m, p) for m, p, _ in _contract_rows()}
    undocumented = [op for op in _served_ops() if op not in documented]
    assert not undocumented, f"served operations missing from contracts.md: {undocumented}"
