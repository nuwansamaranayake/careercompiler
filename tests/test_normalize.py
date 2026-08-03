"""The upload normalization: layout artifacts out of the anchoring source.

The regression case is the one measured in production (candidate 31, 35/138 rejected):
PDF extraction hard-wrapped a sentence mid-clause and doubled spaces at layout gaps, so
the model's faithfully-spaced quote failed the verbatim find. Normalization makes the
stored source carry the document's sentences; the anchor stays byte-verbatim.
"""
from app.routes import _display, _normalize_doc_text


def test_tenant_prefixes_never_reach_a_document():
    # Observed live: a letter opened with "the demo-20260803T031221Z-bcd0dc-Platform
    # Engineer role". Scoping machinery is not a name.
    assert _display("demo-20260803T031221Z-bcd0dc-Platform Engineer") == "Platform Engineer"
    assert _display("smoke-20260803T023734Z-ab12cd-T. Reviewer") == "T. Reviewer"
    assert _display("Platform Engineer") == "Platform Engineer"


def test_layout_wraps_join_and_spaces_collapse():
    raw = ("Software engineering leader with 30 years of enterprise experience and "
           "3+ years building and operating AI-native \nsystems in production.")
    out = _normalize_doc_text(raw)
    # The exact quote the model produced in the measured failure now anchors verbatim.
    assert "3+ years building and operating AI-native systems in production" in out


def test_double_space_separators_collapse():
    raw = "Houston, TX  |  832-202-5960  |  US Citizen"
    assert _normalize_doc_text(raw) == "Houston, TX | 832-202-5960 | US Citizen"


def test_paragraph_boundaries_survive():
    raw = "EXECUTIVE SUMMARY\nLeader of things.\n\nEXPERIENCE\nDid work."
    out = _normalize_doc_text(raw)
    assert out == "EXECUTIVE SUMMARY Leader of things.\nEXPERIENCE Did work."


def test_bullets_keep_their_glyphs_verbatim():
    raw = "• Ran Kubernetes in production.\n• Wrote Terraform modules."
    out = _normalize_doc_text(raw)
    assert "• Ran Kubernetes in production. • Wrote Terraform modules." == out
