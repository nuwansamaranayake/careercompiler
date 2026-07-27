"""Standard-4 harness scripts must fail loud, never silently no-op."""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_check_migrations_fails_loud_without_expected_count():
    env = os.environ.copy()
    env.pop("EXPECTED_TABLE_COUNT", None)
    # The knob check must fire before any DB connection is attempted.
    env["DATABASE_URL"] = "postgresql+psycopg://unused:unused@localhost:1/none"
    r = subprocess.run([sys.executable, "scripts/check_migrations.py"],
                       cwd=str(REPO), env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 1
    assert "EXPECTED_TABLE_COUNT" in r.stderr
    assert "MIGRATION OK" not in r.stdout
