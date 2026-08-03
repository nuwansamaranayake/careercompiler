"""Document kind on compiled_documents: 'resume' or 'cover_letter'.

Revision ID: 0004_document_kind
Revises: 0003_compile_tables
Create Date: 2026-08-02

Column add only — no table is created or dropped, so the public schema still holds
10 app tables + alembic_version = 11. EXPECTED_TABLE_COUNT stays 11 (Standard 4).
Existing rows are resumes; the server_default records that truthfully.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_document_kind"
down_revision = "0003_compile_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compiled_documents",
        sa.Column("kind", sa.Text(), nullable=False, server_default="resume"))


def downgrade() -> None:
    op.drop_column("compiled_documents", "kind")
