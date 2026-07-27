import os
import sys
from sqlalchemy import create_engine, text


def main():
    # Standard 4 needs an expected count to assert against. An unset knob must fail loud,
    # not silently skip the check while still printing MIGRATION OK (the GoviHub mode).
    raw = os.getenv("EXPECTED_TABLE_COUNT")
    if not raw:
        print("MIGRATION CHECK FAILED: EXPECTED_TABLE_COUNT is not set "
              "(see .env.example); refusing to skip the table-count assertion",
              file=sys.stderr)
        sys.exit(1)
    expected = int(raw)
    url = os.environ["DATABASE_URL"]
    with create_engine(url).connect() as c:
        n = c.execute(
            text("select count(*) from information_schema.tables where table_schema='public'")
        ).scalar_one()
    if n != expected:
        print(f"MIGRATION CHECK FAILED: expected {expected} tables, found {n}", file=sys.stderr)
        sys.exit(1)
    print(f"MIGRATION OK: {n} tables")


if __name__ == "__main__":
    main()
