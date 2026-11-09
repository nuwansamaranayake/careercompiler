"""The standalone retention sweep: the cron job behind the 7-day deletion promise.

The deletion rules are portfolio-ops' and are tested there. What is tested here is this
script's own duty: call those rules with a working query, count what was deleted, write
one line per run, and exit nonzero when the sweep refuses or breaks, so a cron job that
stopped deleting cannot look like one that had nothing to delete.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "retention_sweep.py"
spec = importlib.util.spec_from_file_location("retention_sweep", SCRIPT)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

RULES = '''
class RetentionError(Exception):
    pass

def run_retention(app, query, execute, now=None, days=7):
    aged = [n for n in query("list").split("\\n") if n.startswith("demo-old")]
    if not aged:
        return {"aged_namespaces": 0, "deleted": 0, "remaining": 1}
    deleted = sum(execute(f"delete {n}") for n in aged)
    if deleted == 0:
        raise RetentionError(f"{app}: {len(aged)} aged namespace(s) but the delete removed 0 rows")
    return {"aged_namespaces": len(aged), "deleted": deleted, "remaining": 1}
'''


def _rules(tmp_path) -> Path:
    p = tmp_path / "retention.py"
    p.write_text(RULES, encoding="utf-8")
    return p


def _docker(namespaces: str, delete_answer: str = "DELETE 3", rc: int = 0):
    calls: list[list[str]] = []

    def run(argv, **kw):
        calls.append(argv)
        assert kw["timeout"] == 60, "every database call carries a timeout"
        out = namespaces if argv[-1] == "list" else delete_answer
        return SimpleNamespace(returncode=rc, stdout=out + "\n", stderr="connection refused")
    run.calls = calls
    return run


def test_deleted_rows_reads_psql_and_never_invents_a_count():
    assert rs.deleted_rows("DELETE 12") == 12
    assert rs.deleted_rows("DELETE 0") == 0
    assert rs.deleted_rows("") == 0
    assert rs.deleted_rows("12") == 0


def test_a_sweep_deletes_aged_tenants_and_logs_one_line(tmp_path, capsys):
    log = tmp_path / "logs" / "retention.log"
    run = _docker("demo-old-a\ndemo-old-b\ndemo-new")

    code = rs.main(["--retention-module", str(_rules(tmp_path)), "--log", str(log)], run=run)

    assert code == 0
    line = log.read_text(encoding="utf-8").strip()
    assert line.endswith("careercompiler OK aged_namespaces=2 deleted=6 remaining=1")
    assert capsys.readouterr().out.strip() == line
    assert run.calls[0][:8] == ["docker", "exec", "careercompiler-db-1", "psql", "-U",
                                "aignite", "-d", "career_compiler"]
    assert [c[-1] for c in run.calls] == ["list", "delete demo-old-a", "delete demo-old-b"]


def test_nothing_aged_is_a_quiet_pass_and_appends_to_the_log(tmp_path):
    log = tmp_path / "retention.log"
    log.write_text("earlier line\n", encoding="utf-8")
    code = rs.main(["--retention-module", str(_rules(tmp_path)), "--log", str(log)],
                   run=_docker("demo-new"))
    assert code == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "earlier line"
    assert lines[1].endswith("OK aged_namespaces=0 deleted=0 remaining=1")


def test_aged_tenants_that_would_not_delete_fail_loudly(tmp_path):
    log = tmp_path / "retention.log"
    code = rs.main(["--retention-module", str(_rules(tmp_path)), "--log", str(log)],
                   run=_docker("demo-old-a", delete_answer="DELETE 0"))
    assert code == 1
    assert "FAILED: RetentionError" in log.read_text(encoding="utf-8")
    assert "the delete removed 0 rows" in log.read_text(encoding="utf-8")


def test_a_database_that_cannot_be_reached_fails_with_the_reason(tmp_path, capsys):
    code = rs.main(["--retention-module", str(_rules(tmp_path))],
                   run=_docker("", rc=1))
    assert code == 1
    assert "FAILED: RuntimeError: psql failed: connection refused" in capsys.readouterr().out


def test_missing_rules_cannot_start(tmp_path, capsys):
    code = rs.main(["--retention-module", str(tmp_path / "nope.py")], run=_docker(""))
    assert code == 2
    assert "CANNOT START" in capsys.readouterr().out
