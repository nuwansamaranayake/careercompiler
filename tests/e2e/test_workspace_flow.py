"""The product, driven the way a person drives it: two inputs, then three documents.

Every assertion is on what the browser shows or what the downloaded file contains. The
API behind it is the real app with the real gates (see scripts/e2e_server.py for the
three doubles). The scripted LLM only copies sentences, so every rejection asserted here
is the real linker or the real entailment model refusing an edit typed in the browser.
"""
from __future__ import annotations

import io
import re

from docx import Document
from playwright.sync_api import expect
from pypdf import PdfReader

from . import samples


def _pdf_text(path) -> str:
    return " ".join("\n".join((p.extract_text() or "") for p in PdfReader(path).pages).split())


def _docx_text(path) -> str:
    return "\n".join(p.text for p in Document(path).paragraphs)


def _analyze(page, resume: str = samples.RESUME, job: str = samples.JOB,
             title: str = samples.JOB_TITLE) -> None:
    page.goto("/workspace/")
    page.get_by_test_id("resume-paste-tab").click()
    page.get_by_test_id("resume-text").fill(resume)
    page.get_by_test_id("job-title").fill(title)
    page.get_by_test_id("job-text").fill(job)
    page.get_by_test_id("analyze").click()


def _no_unexpected_errors(page, allow: str = "") -> None:
    unexpected = [p for p in page.problems if not (allow and allow in p)]
    assert not unexpected, unexpected


def test_pasted_resume_to_verdict_resume_edit_and_cover_letter(page):
    _analyze(page)

    # ---- career match
    stamp = page.get_by_test_id("verdict-stamp")
    expect(stamp).to_have_attribute("data-verdict", "apply")
    expect(stamp).to_have_text("apply")
    expect(page.get_by_test_id("tally")).to_contain_text("3matched")
    expect(page.get_by_test_id("tally")).to_contain_text("1partial")
    expect(page.get_by_test_id("tally")).to_contain_text("1gap")
    expect(page.get_by_test_id("signed-as")).to_contain_text("Jordan Alvarez")
    expect(page.get_by_test_id("signed-as")).to_contain_text("first line of your resume")
    rows = page.get_by_test_id("fit-table").locator("tbody tr")
    expect(rows).to_have_count(5)
    # Requirements appear in the posting's own words, not as machine keys.
    expect(rows.nth(0)).to_contain_text("Built and operated Python services")
    expect(rows.nth(2)).to_contain_text("Led a team of engineers")
    expect(rows.nth(0)).to_contain_text("must-have")
    expect(rows.nth(0)).to_contain_text("matched")
    expect(rows.nth(4)).to_contain_text("gap")
    expect(rows.nth(4)).to_contain_text("no evidence in the fact graph")

    # ---- resume: generate
    page.get_by_test_id("go-resume").click()
    page.get_by_test_id("budget-28").click()
    page.get_by_test_id("compile-resume").click()
    sheet = page.get_by_test_id("resume-sheet")
    expect(sheet).to_be_visible()
    expect(sheet).to_contain_text("Jordan Alvarez")
    expect(sheet.locator(".line")).to_have_count(5)
    first = page.get_by_test_id("resume-line-0")
    expect(first).to_contain_text("Built and operated Python services in production for 6 years")
    assert re.fullmatch(r"0\.\d\d|1\.00", first.locator(".sc").inner_text())

    # ---- resume: modify. An overstated number is rejected by the real linker.
    first.click()
    editor = page.get_by_test_id("line-editor")
    expect(editor).to_contain_text("document sourced")
    page.get_by_test_id("overstate").click()
    verdict = page.get_by_test_id("gate-verdict")
    expect(verdict).to_have_attribute("data-ok", "false")
    expect(verdict).to_contain_text("unsupported_number")
    expect(page.get_by_test_id("edit-text")).to_have_value(re.compile("60 years"))

    # Saving the overstated text is refused by the server too, and the sheet is unchanged.
    page.get_by_test_id("save-edit").click()
    expect(page.get_by_test_id("gate-verdict")).to_have_attribute("data-ok", "false")
    expect(page.get_by_test_id("edit-saved")).to_have_count(0)
    expect(first).to_contain_text("for 6 years at Acme Corp.")

    # An overstated verb passes the linker and is rejected by the real entailment model.
    page.get_by_test_id("edit-text").fill(
        "Directed the entire engineering organisation at Acme Corp.")
    # A verdict belongs to the text it checked: typing clears the old one.
    expect(page.get_by_test_id("gate-verdict")).to_have_count(0)
    page.get_by_test_id("check-edit").click()
    verdict = page.get_by_test_id("gate-verdict")
    expect(verdict).to_have_attribute("data-ok", "false")
    expect(verdict).to_contain_text("entailment 0.")
    expect(verdict).to_contain_text("< threshold 0.7")

    # An honest edit passes both gates, is saved, and is marked on the sheet.
    page.get_by_test_id("edit-text").fill(samples.HONEST_EDIT)
    page.get_by_test_id("save-edit").click()
    expect(page.get_by_test_id("edit-saved")).to_contain_text("Downloads now carry this line")
    first = page.get_by_test_id("resume-line-0")
    expect(first).to_contain_text(samples.HONEST_EDIT)
    expect(first).to_have_class(re.compile("edited"))
    expect(page.get_by_test_id("resume-line-1")).to_contain_text("Led a team of 4 engineers")

    # ---- the PDF carries the saved edit, the name, and the provenance
    with page.expect_download() as dl:
        page.get_by_test_id("resume-download-pdf").click()
    assert dl.value.suggested_filename.endswith(".pdf")
    text = _pdf_text(dl.value.path())
    assert "Jordan Alvarez" in text
    assert samples.HONEST_EDIT in text
    assert "for 6 years at Acme Corp." not in text.split("PROVENANCE")[0]
    assert "Led a team of 4 engineers at Acme Corp from 2019 to 2022." in text

    # ---- cover letter: same gates, template frame marked
    page.get_by_test_id("tab-letter").click()
    page.get_by_test_id("compile-letter").click()
    letter = page.get_by_test_id("letter-sheet")
    expect(letter).to_contain_text("Dear Hiring Team,")
    expect(letter).to_contain_text("I am writing to apply for the Platform Engineer role.")
    expect(letter.locator(".tpl")).to_have_count(2)
    expect(letter).to_contain_text("I led a team of 4 engineers at Acme Corp")
    expect(page.get_by_test_id("signoff")).to_contain_text("Jordan Alvarez")

    # ---- a rename signs the letter at once and the next download
    page.get_by_test_id("rename").click()
    page.get_by_test_id("name-input").fill("J. Alvarez")
    page.get_by_test_id("name-save").click()
    expect(page.get_by_test_id("signed-as")).to_contain_text("J. Alvarez")
    expect(page.get_by_test_id("signoff")).to_contain_text("J. Alvarez")
    with page.expect_download() as dl:
        page.get_by_test_id("letter-download-docx").click()
    assert dl.value.suggested_filename.endswith(".docx")
    body = _docx_text(dl.value.path())
    assert "J. Alvarez" in body and "Jordan Alvarez" not in body
    assert "Dear Hiring Team," in body

    # ---- the resume survived the trip to the letter tab (tabs stay mounted)
    page.get_by_test_id("tab-resume").click()
    expect(page.get_by_test_id("resume-line-0")).to_contain_text(samples.HONEST_EDIT)

    # ---- interview prep is built from the compiled resume
    page.get_by_test_id("tab-prep").click()
    page.get_by_test_id("build-pack").click()
    pack = page.get_by_test_id("pack")
    expect(pack).to_contain_text(samples.HONEST_EDIT)
    expect(pack).to_contain_text("experience with rust", ignore_case=True)
    # No title was mangled into the letter's fixed frame.
    assert "the The" not in page.get_by_test_id("letter-sheet").inner_text()
    _no_unexpected_errors(page, allow="422")


def test_uploaded_docx_resume_reaches_a_verdict(page, tmp_path):
    doc = Document()
    for para in samples.RESUME.strip().split("\n\n"):
        doc.add_paragraph(para)
    path = tmp_path / "jordan-alvarez.docx"
    doc.save(path)

    page.goto("/workspace/")
    page.get_by_test_id("resume-file").set_input_files(str(path))
    expect(page.get_by_test_id("resume-file-chosen")).to_contain_text("jordan-alvarez.docx")
    # No title typed: it is read from the posting's first line, visibly, before the run.
    page.get_by_test_id("job-text").fill(samples.JOB)
    expect(page.get_by_test_id("job-title")).to_have_value("Platform Engineer")
    page.get_by_test_id("analyze").click()

    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "apply")
    expect(page.get_by_test_id("verdict")).to_contain_text("Platform Engineer")
    expect(page.get_by_test_id("signed-as")).to_contain_text("Jordan Alvarez")
    expect(page.get_by_test_id("verdict")).to_contain_text("5 facts anchored in your resume")
    _no_unexpected_errors(page)


def test_a_planted_must_have_gap_is_do_not_apply_with_the_case_stated(page):
    _analyze(page, job=samples.JOB_WITH_CLEARANCE)

    stamp = page.get_by_test_id("verdict-stamp")
    expect(stamp).to_have_attribute("data-verdict", "do_not_apply")
    expect(stamp).to_have_text("do not apply")
    expect(page.get_by_test_id("case-against")).to_contain_text("The case against applying")
    clearance = page.get_by_test_id("fit-table").locator("tbody tr", has_text="Active TS/SCI security clearance")
    expect(clearance).to_contain_text("must-have")
    expect(clearance).to_contain_text("gap")
    _no_unexpected_errors(page)


def test_the_form_refuses_to_run_on_missing_inputs(page):
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url) if "/api/" in r.url else None)
    page.goto("/workspace/")
    page.get_by_test_id("analyze").click()

    expect(page.get_by_test_id("resume-error")).to_contain_text("Add your resume")
    expect(page.get_by_test_id("job-error")).to_contain_text("Paste the full job description")
    expect(page.get_by_test_id("title-error")).to_contain_text("Add the job title")
    assert requests == [], "validation must stop the run before any API call"

    # A typed title is the person's; pasting a posting afterwards must not overwrite it.
    page.get_by_test_id("job-title").fill("Staff Engineer")
    page.get_by_test_id("job-text").fill(samples.JOB)
    expect(page.get_by_test_id("job-title")).to_have_value("Staff Engineer")

    page.get_by_test_id("resume-paste-tab").click()
    page.get_by_test_id("resume-text").fill("too short")
    page.get_by_test_id("analyze").click()
    expect(page.get_by_test_id("resume-error")).to_contain_text("at least 200 characters")
    assert requests == []


def test_a_posting_with_no_requirements_stops_the_build_and_keeps_the_inputs(page):
    _analyze(page, job=samples.JOB_WITHOUT_REQUIREMENTS)

    error = page.get_by_test_id("pipeline-error")
    expect(error).to_contain_text("No requirements could be read out of that text")
    log = page.get_by_test_id("build-log")
    expect(log.locator('li[data-step="facts"]')).to_have_attribute("data-state", "done")
    expect(log.locator('li[data-step="requirements"]')).to_have_attribute("data-state", "failed")
    expect(log.locator('li[data-step="match"]')).to_have_attribute("data-state", "pending")

    # The session opened for the stopped build is kept, so the retry does not spend
    # another one (sessions are rate-limited per address).
    token = page.evaluate("JSON.parse(sessionStorage.getItem('cc-session')).token")
    assert token

    page.get_by_test_id("edit-inputs").click()
    expect(page.get_by_test_id("resume-text")).to_have_value(re.compile("Jordan Alvarez"))
    expect(page.get_by_test_id("job-text")).to_have_value(re.compile("friendly company"))
    page.get_by_test_id("job-text").fill(samples.JOB)
    page.get_by_test_id("analyze").click()
    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "apply")
    assert page.evaluate("JSON.parse(sessionStorage.getItem('cc-session')).token") == token
    _no_unexpected_errors(page)


def test_a_compiled_document_survives_a_failed_evidence_load(page):
    _analyze(page)
    expect(page.get_by_test_id("verdict-stamp")).to_be_visible()

    # The compile succeeds; the follow-up read of its provenance fails once.
    doc_read = re.compile(r"/api/v1/compile/\d+$")
    page.route(doc_read, lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail": "database is busy"}')
        if route.request.method == "GET" else route.continue_())
    page.get_by_test_id("tab-resume").click()
    page.get_by_test_id("compile-resume").click()

    sheet = page.get_by_test_id("resume-sheet")
    expect(sheet.locator(".line")).to_have_count(5)
    expect(page.get_by_test_id("evidence-error")).to_contain_text("database is busy")
    # The document was not thrown away: it downloads, and interview prep can see it.
    with page.expect_download() as dl:
        page.get_by_test_id("resume-download-pdf").click()
    assert "Jordan Alvarez" in _pdf_text(dl.value.path())

    page.unroute(doc_read)
    page.get_by_test_id("evidence-retry").click()
    expect(page.get_by_test_id("evidence-error")).to_have_count(0)
    page.get_by_test_id("resume-line-0").click()
    expect(page.get_by_test_id("line-editor")).to_contain_text("document sourced")
    page.get_by_test_id("tab-prep").click()
    expect(page.get_by_test_id("build-pack")).to_be_visible()
    _no_unexpected_errors(page, allow="500")


def test_a_resume_without_a_readable_name_asks_for_one(page):
    _analyze(page, resume=samples.RESUME_NO_NAME)

    form = page.get_by_test_id("name-form")
    expect(form).to_contain_text("We could not read your name from the resume")
    page.get_by_test_id("name-save").click()
    expect(form).to_contain_text("Enter the name to sign your documents with")
    page.get_by_test_id("name-input").fill("Jordan Alvarez")
    page.get_by_test_id("name-input").press("Enter")
    expect(page.get_by_test_id("signed-as")).to_contain_text("Jordan Alvarez")
    expect(page.get_by_test_id("signed-as")).to_contain_text("as you entered it")
    _no_unexpected_errors(page)


def test_an_expired_session_ends_in_one_panel_and_a_clean_restart(page):
    _analyze(page)
    expect(page.get_by_test_id("verdict-stamp")).to_be_visible()

    # The server stops honouring the token (expiry and a spent budget look the same to
    # a browser: a 401 or a 429 on an authenticated call).
    page.route("**/api/v1/compile", lambda route: route.fulfill(
        status=401, content_type="application/json",
        body='{"detail": "missing or invalid bearer token"}'))
    page.get_by_test_id("tab-resume").click()
    page.get_by_test_id("compile-resume").click()

    ended = page.get_by_test_id("session-ended")
    expect(ended).to_contain_text("This session expired")
    assert page.evaluate("sessionStorage.getItem('cc-session')") is None
    page.get_by_test_id("new-session").click()
    expect(page.get_by_test_id("analyze")).to_be_visible()
    _no_unexpected_errors(page, allow="401")


def test_a_second_analysis_never_shows_the_first_verdict(page):
    _analyze(page)
    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "apply")
    token = page.evaluate("JSON.parse(sessionStorage.getItem('cc-session')).token")

    page.get_by_test_id("restart").click()
    page.get_by_test_id("job-text").fill(samples.JOB_WITH_CLEARANCE)
    page.get_by_test_id("analyze").click()

    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "do_not_apply")
    expect(page.get_by_test_id("fit-table").locator("tbody tr")).to_have_count(6)
    # The live session was reused: a second analysis costs no second session.
    assert page.evaluate("JSON.parse(sessionStorage.getItem('cc-session')).token") == token
    _no_unexpected_errors(page)


def test_the_sample_shows_both_verdicts_on_synthetic_data(page):
    page.goto("/demo/")
    page.get_by_test_id("open-sample").click()

    page.get_by_test_id("sample-job-do_not_apply").click()
    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "do_not_apply")
    expect(page.get_by_test_id("verdict")).to_contain_text("synthetic sample")
    expect(page.get_by_test_id("case-against")).to_contain_text("active_ts_sci_clearance")
    expect(page.get_by_test_id("signed-as")).to_have_count(0)

    page.get_by_test_id("restart").click()
    page.get_by_test_id("sample-job-apply").click()
    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "apply")
    page.get_by_test_id("tab-letter").click()
    page.get_by_test_id("compile-letter").click()
    expect(page.get_by_test_id("signoff")).to_contain_text("Jordan Alvarez")
    _no_unexpected_errors(page)


def test_landing_and_guide_carry_their_promised_content(page, base_url):
    page.goto("/")
    expect(page.locator("h1")).to_contain_text("A resume compiler with compile errors.")
    expect(page.locator(".limits")).to_contain_text(
        "the suite is synthetic and small, so it does not measure performance on real "
        "resumes or real postings")
    page.get_by_role("link", name="Open the workspace").click()
    expect(page).to_have_url(re.compile(r"/workspace/$"))
    expect(page.get_by_test_id("analyze")).to_be_visible()

    page.goto("/guide/")
    for heading in ("Enter your resume and the job description",
                    "Career match: should you apply?",
                    "Resume: generate it, then modify it", "Cover letter"):
        expect(page.get_by_role("heading", name=heading, level=2)).to_be_visible()
    expect(page.locator("main")).to_contain_text("synthetic data")
    shots = page.locator(".shot img")
    expect(shots).to_have_count(15)
    broken = page.evaluate(
        """async () => {
             const imgs = [...document.querySelectorAll('.shot img')];
             const res = await Promise.all(imgs.map((i) => fetch(i.src).then((r) => r.ok)));
             return imgs.filter((_, n) => !res[n]).map((i) => i.getAttribute('src'));
           }""")
    assert broken == [], f"guide screenshots missing from the build: {broken}"
    _no_unexpected_errors(page)


def test_the_api_stays_closed_without_a_token(base_url):
    import httpx
    assert httpx.get(f"{base_url}/api/v1/fit/1").status_code == 401
    assert httpx.put(f"{base_url}/api/v1/compile/1/bullets/0",
                     json={"text": "x"}).status_code == 401
    assert httpx.patch(f"{base_url}/api/v1/candidates/1", json={"name": "x"}).status_code == 401
    assert io.BytesIO(httpx.get(f"{base_url}/workspace/").content).read(15) == b"<!DOCTYPE html>"
