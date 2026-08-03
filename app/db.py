"""Schema and session plumbing. metadata is the single source of truth; the alembic
migration applies it, and EXPECTED_TABLE_COUNT asserts the result (Standard 4)."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from .config import settings

JSON = sa.JSON().with_variant(JSONB(), "postgresql")

metadata = sa.MetaData()

candidates = sa.Table(
    "candidates", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

source_documents = sa.Table(
    "source_documents", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id"), nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

atomic_claims = sa.Table(
    "atomic_claims", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id"), nullable=False),
    sa.Column("claim_id", sa.Text, nullable=False),
    sa.Column("claim_key", sa.Text, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("statement", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("span_start", sa.Integer),
    sa.Column("span_end", sa.Integer),
    sa.Column("provenance", sa.Text, nullable=False),      # document_sourced | self_attested
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("verification_status", sa.Text, nullable=False),   # pending|passed|rejected
    sa.Column("gates", JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

job_postings = sa.Table(
    "job_postings", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("description", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

requirements = sa.Table(
    "requirements", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("job_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
    sa.Column("req_key", sa.Text, nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("must_have", sa.Boolean, nullable=False),
)

fit_reports = sa.Table(
    "fit_reports", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id"), nullable=False),
    sa.Column("job_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
    sa.Column("verdict", sa.Text, nullable=False),          # apply | do_not_apply
    sa.Column("matched", sa.Integer, nullable=False),
    sa.Column("partial", sa.Integer, nullable=False),
    sa.Column("gaps", sa.Integer, nullable=False),
    sa.Column("disqualifying", JSON, nullable=False),
    sa.Column("case_against", sa.Text, nullable=False),
    sa.Column("embedder", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

match_scores = sa.Table(
    "match_scores", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("fit_report_id", sa.Integer, sa.ForeignKey("fit_reports.id"), nullable=False),
    sa.Column("req_key", sa.Text, nullable=False),
    sa.Column("must_have", sa.Boolean, nullable=False),
    sa.Column("status", sa.Text, nullable=False),           # matched | partial | gap
    sa.Column("direct", sa.Boolean, nullable=False),
    sa.Column("evidence", JSON, nullable=False),
    sa.Column("score", sa.Float, nullable=False),
    sa.Column("explanation", sa.Text, nullable=False),
)

# Phase 2: only documents that passed BOTH gates are ever persisted. A failed compile
# returns its violations and stores nothing, so every row in these tables is a document
# whose every sentence traced to a fact at the moment it was written.
compiled_documents = sa.Table(
    "compiled_documents", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id"), nullable=False),
    sa.Column("job_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
    # 'resume' or 'cover_letter': both are gated documents in the same tables; the kind
    # only changes how the docx is framed, never what the gates require.
    sa.Column("kind", sa.Text, nullable=False, server_default="resume"),
    sa.Column("budget_lines", sa.Integer, nullable=False),
    sa.Column("used_lines", sa.Integer, nullable=False),
    sa.Column("nli_model", sa.Text, nullable=False),
    sa.Column("nli_revision", sa.Text, nullable=False),
    sa.Column("nli_threshold", sa.Float, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

rendered_bullets = sa.Table(
    "rendered_bullets", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("document_id", sa.Integer, sa.ForeignKey("compiled_documents.id"),
              nullable=False),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("cites", JSON, nullable=False),
    sa.Column("entailment", sa.Float),
)

selection_omissions = sa.Table(
    "selection_omissions", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("document_id", sa.Integer, sa.ForeignKey("compiled_documents.id"),
              nullable=False),
    sa.Column("claim_id", sa.Text, nullable=False),
    sa.Column("claim_key", sa.Text, nullable=False),
    sa.Column("reason", sa.Text, nullable=False),
    sa.Column("detail", sa.Text, nullable=False),
)

_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        _engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine)
    return _engine


def get_session():
    get_engine()
    return _Session()


def set_engine_for_tests(engine) -> None:
    """Tests inject their own engine (sqlite in-memory). Explicit, never automatic."""
    global _engine, _Session
    _engine = engine
    _Session = sessionmaker(bind=engine)
