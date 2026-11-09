"""The PDF, with its provenance carried inside the document — the print-grade sibling of
docx_out.

Same discipline: only gate-passing documents ever reach this module, every bullet carries a
bracketed reference, and the final page resolves each reference to the exact fact
statements that license it, plus every omission with its typed reason. A printed copy still
traces every sentence to a fact.

ReportLab, deliberately: pure Python, ~13 MB, deterministic output. A docx->PDF converter
(LibreOffice headless, ~400 MB) would blow the image's 1.9 GB assertion on a box that
serves a paying product, for no gain a reviewer can see.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (HRFlowable, PageBreak, Paragraph, SimpleDocTemplate)

from .entailment import display_score
from .facts import AtomicClaim
from .selector import Omission

CHARCOAL = colors.HexColor("#2b2f36")
GREEN = colors.HexColor("#2D8C4E")
GRAY = colors.HexColor("#6a7280")
RULE = colors.HexColor("#c9d1dc")

_BASE = dict(fontName="Helvetica", textColor=CHARCOAL, leading=13.5)
S_NAME = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=21,
                        textColor=CHARCOAL, leading=24, spaceAfter=2)
S_ROLE = ParagraphStyle("role", fontName="Helvetica-Oblique", fontSize=10.5,
                        textColor=GRAY, leading=13, spaceAfter=10)
S_SECTION = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10,
                           textColor=GREEN, leading=12, spaceBefore=14, spaceAfter=6)
S_BULLET = ParagraphStyle("bullet", fontSize=10.5, **_BASE, alignment=TA_JUSTIFY,
                          leftIndent=14, bulletIndent=2, spaceAfter=5)
S_BODY = ParagraphStyle("body", fontSize=10.5, **_BASE, spaceAfter=6)
S_SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, textColor=GRAY,
                         leading=11, spaceAfter=3)
S_FACT = ParagraphStyle("fact", fontName="Helvetica", fontSize=9, textColor=CHARCOAL,
                        leading=12, leftIndent=26, spaceAfter=3)
S_PROVHEAD = ParagraphStyle("provhead", fontName="Helvetica-Bold", fontSize=10,
                            textColor=CHARCOAL, leading=13, spaceBefore=8, spaceAfter=2)


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(0.75 * inch, 0.5 * inch,
                      "Compiled by CareerCompiler — every sentence cites verified career "
                      "facts; anything stronger than its evidence did not compile.")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, f"page {doc.page}")
    canvas.restoreState()


def _provenance_story(bullets: list[dict], claims_by_id: dict[str, AtomicClaim],
                      omissions: list[Omission], entailment_note: str,
                      unit: str) -> list:
    story = [PageBreak(), Paragraph("PROVENANCE", S_SECTION)]
    story.append(Paragraph(
        _esc(f"Every {unit} above cites the career facts that license it. The compiler "
             "rejects a sentence that cites nothing, cites a fact that does not exist, "
             "carries a number appearing in no cited fact, or claims more than its cited "
             f"evidence supports ({entailment_note})."), S_SMALL))
    for b in bullets:
        story.append(Paragraph(f"[{b['position'] + 1}]  {_esc(b['text'])}", S_PROVHEAD))
        for cid in b.get("cites", []):
            claim = claims_by_id.get(cid)
            if claim is None:
                story.append(Paragraph(_esc(f"{cid} (not resolved)"), S_FACT))
                continue
            story.append(Paragraph(
                f"<b>{_esc(claim.claim_key)}:</b> {_esc(claim.core.statement)} "
                f"<font size=7.5 color='#6a7280'>— {_esc(claim.provenance.value)}, "
                f"fact {_esc(cid)}</font>", S_FACT))
        score = b.get("entailment")
        if score is not None:
            story.append(Paragraph(f"entailment {display_score(score)}", S_SMALL))
    if omissions:
        story.append(Paragraph("WHAT WAS LEFT OUT, AND WHY", S_SECTION))
        story.append(Paragraph(
            "A selector that drops evidence silently is not explainable. Every eligible "
            "fact that did not reach the page:", S_SMALL))
        for o in omissions:
            story.append(Paragraph(
                f"<b>{_esc(o.claim_key)}:</b> {_esc(o.reason.value)} — {_esc(o.detail)}",
                S_FACT))
    return story


def _build(story: list, title: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER, title=title, author="CareerCompiler",
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.85 * inch)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def render_pdf(
    candidate_name: str,
    job_title: str,
    bullets: list[dict],
    claims_by_id: dict[str, AtomicClaim],
    omissions: list[Omission],
    entailment_note: str,
) -> bytes:
    """The resume. bullets: [{position, text, cites, entailment}] — already gated."""
    story = [
        Paragraph(_esc(candidate_name), S_NAME),
        Paragraph(_esc(f"Compiled for: {job_title}"), S_ROLE),
        HRFlowable(width="100%", thickness=1, color=RULE, spaceAfter=4),
        Paragraph("EXPERIENCE", S_SECTION),
    ]
    for b in bullets:
        story.append(Paragraph(
            f"{_esc(b['text'])} <font size=7 color='#6a7280'>[{b['position'] + 1}]</font>",
            S_BULLET, bulletText="•"))
    story += _provenance_story(bullets, claims_by_id, omissions, entailment_note,
                               unit="sentence")
    return _build(story, f"{candidate_name} — resume")


def render_letter_pdf(
    candidate_name: str,
    job_title: str,
    sentences: list[dict],
    claims_by_id: dict[str, AtomicClaim],
    entailment_note: str,
    frame: dict,
) -> bytes:
    """The cover letter, in the same deterministic frame the docx uses: the frame is the
    only text allowed to reference the role, and it claims nothing about the candidate."""
    story = [
        Paragraph(_esc(candidate_name), S_NAME),
        Paragraph(_esc(f"Cover letter — {job_title}"), S_ROLE),
        HRFlowable(width="100%", thickness=1, color=RULE, spaceAfter=10),
        Paragraph(_esc(frame["greeting"]), S_BODY),
        Paragraph(_esc(frame["opening"]), S_BODY),
    ]
    for s_ in sentences:
        story.append(Paragraph(
            f"{_esc(s_['text'])} <font size=7 color='#6a7280'>[{s_['position'] + 1}]</font>",
            S_BODY))
    story.append(Paragraph(_esc(frame["closing"]), S_BODY))
    for line in frame["signoff"].split("\n"):
        story.append(Paragraph(_esc(line), S_BODY))
    story += _provenance_story(sentences, claims_by_id, [], entailment_note,
                               unit="bracketed sentence")
    return _build(story, f"{candidate_name} — cover letter")
