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
