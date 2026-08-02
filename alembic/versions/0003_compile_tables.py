"""Phase 2 compile tables: compiled_documents, rendered_bullets, selection_omissions.

Revision ID: 0003_compile_tables
Revises: 0002_real_schema
Create Date: 2026-08-02

app.db.metadata stays the single source of truth; this migration applies exactly the three
new tables. After upgrade the public schema holds 10 app tables + alembic_version = 11.
EXPECTED_TABLE_COUNT=11 (Standard 4).
"""
import sys
from pathlib import Path

from alembic import op

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

revision = "0003_compile_tables"
down_revision = "0002_real_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import compiled_documents, metadata, rendered_bullets, selection_omissions
    metadata.create_all(op.get_bind(), tables=[
        compiled_documents, rendered_bullets, selection_omissions])


def downgrade() -> None:
    from app.db import compiled_documents, rendered_bullets, selection_omissions
    for table in (selection_omissions, rendered_bullets, compiled_documents):
        op.drop_table(table.name)
