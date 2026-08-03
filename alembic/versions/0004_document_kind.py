"""Document kind on compiled_documents: 'resume' or 'cover_letter'.

Revision ID: 0004_document_kind
Revises: 0003_compile_tables
Create Date: 2026-08-02

Column add only — no table is created or dropped, so the public schema still holds
10 app tables + alembic_version = 11. EXPECTED_TABLE_COUNT stays 11 (Standard 4).
Existing rows are resumes; the server_default records that truthfully.

Guarded: 0003 creates its tables from live app.db.metadata (the stated single source of
truth), so a FRESH database already gets `kind` at 0003 and this migration must no-op
there. Only a database that ran 0003 before the column existed needs the add. Observed
live: CI's fresh smoke database failed on DuplicateColumn without the guard.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_document_kind"
down_revision = "0003_compile_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [c["name"] for c in
            sa.inspect(op.get_bind()).get_columns("compiled_documents")]
    if "kind" in cols:
        return
    op.add_column(
        "compiled_documents",
        sa.Column("kind", sa.Text(), nullable=False, server_default="resume"))


def downgrade() -> None:
    op.drop_column("compiled_documents", "kind")
