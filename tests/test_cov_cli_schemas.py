"""CLI and schema behaviour, driven through the real golden file."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import cli
from app.schemas import DemoResponse

GOLDEN = str(Path(__file__).resolve().parent.parent / "data" / "synthetic" / "golden"
             / "golden.json")


def test_fit_apply_verdict_returns_zero_and_writes_report(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = cli.fit(GOLDEN, "platform-role", str(out))
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Fit Report")
    assert "APPLY" in text
    assert capsys.readouterr().out.startswith("# Fit Report")


def test_fit_do_not_apply_returns_one_without_report_file(capsys):
    assert cli.fit(GOLDEN, "gap-disqualifier", None) == 1
    assert "DO NOT APPLY" in capsys.readouterr().out


def test_fit_unknown_case_returns_two_and_lists_cases(capsys):
    assert cli.fit(GOLDEN, "no-such-case", None) == 2
    err = capsys.readouterr().err
    assert "unknown case 'no-such-case'" in err
    assert "platform-role" in err


@pytest.mark.parametrize("case,code", [("platform-role", 0), ("gap-disqualifier", 1),
                                       ("nope", 2)])
def test_main_exits_with_fit_code(monkeypatch, capsys, case, code):
    monkeypatch.setattr(sys, "argv", ["careercompiler", "fit", "--facts", GOLDEN,
                                      "--case", case])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == code


def test_main_requires_a_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["careercompiler"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2


def test_demo_response_accepts_items_and_rejects_non_list():
    r = DemoResponse(items=[{"a": 1}, {"b": "x"}])
    assert r.items == [{"a": 1}, {"b": "x"}]
    with pytest.raises(ValidationError):
        DemoResponse(items="nope")
    with pytest.raises(ValidationError):
        DemoResponse()


def test_cli_module_runs_as_a_script(monkeypatch, capsys):
    import runpy
    monkeypatch.setattr(sys, "argv", ["app.cli", "fit", "--facts", GOLDEN, "--case",
                                      "gap-disqualifier"])
    with pytest.raises(SystemExit) as e:
        runpy.run_module("app.cli", run_name="__main__")
    assert e.value.code == 1
    assert "DO NOT APPLY" in capsys.readouterr().out
