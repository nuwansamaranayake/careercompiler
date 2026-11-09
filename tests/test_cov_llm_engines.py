"""Renderer, revise, interview question drafting with a fake gateway; embedder over a
patched httpx; entailment loader over patched torch/transformers."""
from __future__ import annotations

import json
import sys
import types

import httpx
import pytest

from app.engine import embedding, entailment
from app.engine.embedding import EmbedderUnavailable, OpenRouterEmbedder, cosine
from app.engine.facts import claims_from_entries
from app.engine.interview import draft_questions
from app.engine.linker import Bullet
from app.engine.renderer import draft_bullets, draft_letter
from app.engine.revise import numeral_violations, revise_renderings


class FakeGateway:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def complete(self, *, model, messages, json_schema):
        self.calls.append({"model": model, "messages": messages, "schema": json_schema})
        return self.result


def _claims():
    return claims_from_entries([
        {"claim_key": "lead", "kind": "role",
         "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
        {"claim_key": "k8s", "kind": "skill", "statement": "Ran Kubernetes in production."},
    ])


REQS: list = []


# ---- renderer ----------------------------------------------------------------------

@pytest.mark.parametrize("fn", [draft_bullets, draft_letter])
def test_renderer_maps_aliases_back_to_claim_ids(fn):
    claims = _claims()
    gw = FakeGateway({"renderings": [{"id": "F1", "text": "Led 4 engineers."},
                                     {"id": "F2", "text": "Ran Kubernetes."},
                                     {"id": "F9", "text": "Unknown alias."}]})
    out = fn(gw, "m", claims, "Engineer", REQS)
    assert out[0] == Bullet("Led 4 engineers.", [claims[0].core.claim_id])
    assert out[1].cites == [claims[1].core.claim_id]
    # an alias outside the map stays as-is so the linker rejects it loudly
    assert out[2].cites == ["F9"]
    payload = json.loads(gw.calls[0]["messages"][1]["content"])
    assert [f["id"] for f in payload["facts"]] == ["F1", "F2"]
    assert payload["job_title"] == "Engineer"


@pytest.mark.parametrize("fn", [draft_bullets, draft_letter])
def test_renderer_accepts_bare_list_and_skips_missing(fn):
    claims = _claims()
    gw = FakeGateway([{"id": "F2", "text": "Ran Kubernetes."}])
    out = fn(gw, "m", claims, "Engineer", REQS)
    assert out == [Bullet("Ran Kubernetes.", [claims[1].core.claim_id])]
    assert fn(FakeGateway({}), "m", claims, "Engineer", REQS) == []


@pytest.mark.parametrize("fn", [draft_bullets, draft_letter])
def test_renderer_refuses_without_model_or_claims(fn):
    with pytest.raises(RuntimeError, match="LLM_MODEL_REASONING"):
        fn(FakeGateway({}), "", _claims(), "t", REQS)
    with pytest.raises(ValueError, match="selector chose no facts"):
        fn(FakeGateway({}), "m", [], "t", REQS)


# ---- revise ------------------------------------------------------------------------

def test_numeral_violations_flags_numbers_outside_cited_facts():
    claims = _claims()
    by_id = {c.core.claim_id: c for c in claims}
    bullets = [
        Bullet("Led 40 engineers.", [claims[0].core.claim_id]),
        Bullet("Led a team of 4 engineers.", [claims[0].core.claim_id]),
        Bullet("Won 7 awards.", ["missing-id"]),
    ]
    v = numeral_violations(bullets, by_id)
    assert [x["index"] for x in v] == [0, 2]
    assert v[0]["bad_tokens"] == ["40"]
    assert "4" in v[0]["allowed_tokens"]
    assert v[1]["allowed_tokens"] == [] and v[1]["statements"] == []


def test_numeral_violations_ignores_rejected_claims():
    claims = _claims()
    claims[0].core.verification.status = "rejected"
    v = numeral_violations([Bullet("Led 4 engineers.", [claims[0].core.claim_id])],
                           {claims[0].core.claim_id: claims[0]})
    assert v[0]["bad_tokens"] == ["4"] and v[0]["allowed_tokens"] == []


def test_revise_returns_text_keyed_by_bullet_index():
    offending = [
        {"index": 3, "cites": ["a"], "text": "Led 40.", "reasons": "bad number",
         "statements": ["Led a team of 4."], "allowed_tokens": ["4"]},
        {"index": 5, "cites": ["b"], "text": "Ran it.", "reasons": "too strong",
         "statements": []},
    ]
    gw = FakeGateway({"renderings": [{"id": "F1", "text": "Led 4."},
                                     {"id": "F2", "text": ""},
                                     {"id": "F7", "text": "ghost"}]})
    out = revise_renderings(gw, "m", offending)
    assert out == {3: "Led 4."}
    payload = json.loads(gw.calls[0]["messages"][1]["content"])
    items = payload["renderings"]
    assert items[0]["numerals_you_may_use_spelled_exactly"] == ["4"]
    assert "numerals_you_may_use_spelled_exactly" not in items[1]
    assert items[1]["fact"] == "(fact unavailable)"
    assert "resume bullet points" in gw.calls[0]["messages"][0]["content"]


def test_revise_letter_voice_bare_list_and_guards():
    gw = FakeGateway([{"id": "F1", "text": "I led 4."}])
    off = [{"index": 0, "cites": [], "text": "x", "reasons": "r", "statements": ["s"]}]
    assert revise_renderings(gw, "m", off, letter=True) == {0: "I led 4."}
    assert "first-person cover-letter" in gw.calls[0]["messages"][0]["content"]
    assert revise_renderings(gw, "m", []) == {}
    with pytest.raises(RuntimeError, match="LLM_MODEL_REASONING"):
        revise_renderings(gw, "", off)


# ---- interview.draft_questions -----------------------------------------------------

def test_draft_questions_maps_ids_and_drops_malformed_items():
    gw = FakeGateway({"items": [{"id": "b1", "questions": ["Why 4?", "How?"]},
                                {"questions": ["no id"]}, "junk"]})
    out = draft_questions(gw, "m", "Eng", [{"id": "b1", "text": "t", "facts": ["f"]}], [])
    assert out == {"b1": ["Why 4?", "How?"]}


def test_draft_questions_bare_list_and_no_model():
    gw = FakeGateway([{"id": "g1", "questions": ["Gap?"]}])
    assert draft_questions(gw, "m", "Eng", [], [{"id": "g1"}]) == {"g1": ["Gap?"]}
    with pytest.raises(RuntimeError, match="LLM_MODEL_REASONING"):
        draft_questions(gw, "", "Eng", [], [])


# ---- embedding ---------------------------------------------------------------------

class _Resp:
    def __init__(self, payload=None, status=200):
        self._p, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "https://x/embeddings")
            raise httpx.HTTPStatusError(
                "bad", request=req, response=httpx.Response(self.status_code, request=req))

    def json(self):
        if isinstance(self._p, Exception):
            raise self._p
        return self._p


def test_openrouter_embedder_sorts_by_index_and_sends_auth(monkeypatch):
    seen = {}

    def post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return _Resp({"data": [{"index": 1, "embedding": [0.0, 1.0]},
                               {"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr(embedding.httpx, "post", post)
    e = OpenRouterEmbedder("k", "emb/model", base_url="https://h/api/")
    assert e.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert seen["url"] == "https://h/api/embeddings"
    assert seen["headers"] == {"Authorization": "Bearer k"}
    assert seen["json"] == {"model": "emb/model", "input": ["a", "b"]}


def test_openrouter_embedder_http_status_error(monkeypatch):
    monkeypatch.setattr(embedding.httpx, "post", lambda *a, **k: _Resp(status=401))
    with pytest.raises(EmbedderUnavailable, match="answered 401 for model 'm'"):
        OpenRouterEmbedder("k", "m").embed(["a"])


def test_openrouter_embedder_transport_malformed_and_bad_json(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(embedding.httpx, "post", boom)
    with pytest.raises(EmbedderUnavailable, match="ConnectError"):
        OpenRouterEmbedder("k", "m").embed(["a"])
    monkeypatch.setattr(embedding.httpx, "post", lambda *a, **k: _Resp({"nodata": 1}))
    with pytest.raises(EmbedderUnavailable, match="KeyError"):
        OpenRouterEmbedder("k", "m").embed(["a"])
    monkeypatch.setattr(embedding.httpx, "post",
                        lambda *a, **k: _Resp(ValueError("not json")))
    with pytest.raises(EmbedderUnavailable, match="ValueError"):
        OpenRouterEmbedder("k", "m").embed(["a"])


def test_openrouter_embedder_refuses_blind():
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterEmbedder("", "m")
    with pytest.raises(RuntimeError, match="EMBEDDING_MODEL"):
        OpenRouterEmbedder("k", "")


def test_cosine_zero_vector_is_zero_and_identical_is_one():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)


# ---- entailment loader -------------------------------------------------------------

@pytest.fixture()
def fresh_load():
    entailment._load.cache_clear()
    yield
    entailment._load.cache_clear()


def _install_fakes(monkeypatch, id2label, from_pretrained_error=None):
    torch = types.ModuleType("torch")

    class _NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    torch.no_grad = lambda: _NoGrad()
    torch.softmax = lambda logits, dim: logits

    tf = types.ModuleType("transformers")

    class Tok:
        @staticmethod
        def from_pretrained(model_id, revision, local_files_only):
            if from_pretrained_error:
                raise from_pretrained_error
            assert local_files_only is True
            def tokenize(premise, hyp, **kw):
                # One token per word: enough to exercise the window check. The scored
                # call must be the truncating one; the measuring call must not truncate.
                if kw.get("return_tensors"):
                    assert kw["truncation"] is True and kw["max_length"] == 512
                    return {"p": premise, "h": hyp}
                assert kw["truncation"] is False
                return {"input_ids": (premise + " " + hyp).split()}
            return tokenize

    class Model:
        def __init__(self):
            self.config = types.SimpleNamespace(id2label=id2label)

        @staticmethod
        def from_pretrained(model_id, revision, local_files_only):
            return Model()

        def eval(self):
            pass

        def __call__(self, **batch):
            hot = [0.1, 0.1, 0.8] if "more" not in batch["h"] else [0.9, 0.05, 0.05]
            return types.SimpleNamespace(logits=[hot])

    tf.AutoTokenizer = Tok
    tf.AutoModelForSequenceClassification = Model
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", tf)


def test_load_scorer_reads_entailment_index_from_checkpoint(monkeypatch, fresh_load):
    _install_fakes(monkeypatch, {0: "CONTRADICTION", 1: "NEUTRAL", 2: "ENTAILMENT"})
    score = entailment.load_scorer("m", "a" * 40)
    assert score("premise", "same") == pytest.approx(0.8)
    assert score("premise", "much more") == pytest.approx(0.05)
    assert entailment.load_scorer("m", "a" * 40) is score  # cached


def test_a_pair_longer_than_the_window_scores_zero_without_asking_the_model(
        monkeypatch, fresh_load):
    """Truncation would score only the opening and let appended text pass unread. A
    sentence the model cannot read whole has no evidence of support: it scores 0.0."""
    _install_fakes(monkeypatch, {0: "CONTRADICTION", 1: "NEUTRAL", 2: "ENTAILMENT"})
    score = entailment.load_scorer("m", "a" * 40)
    at_limit = " ".join(["same"] * (entailment.MAX_PAIR_TOKENS - 1))
    assert score("premise", at_limit) == pytest.approx(0.8)
    assert score("premise", at_limit + " tail") == 0.0
    # Through the gate, that zero is an ordinary violation with the usual evidence.
    from app.engine.facts import claims_from_entries
    from app.engine.linker import Bullet
    [claim] = claims_from_entries([{"claim_key": "k", "kind": "skill", "statement": "premise"}])
    report = entailment.gate([Bullet(at_limit + " tail", [claim.core.claim_id])], [claim],
                             0.7, "m", "a" * 40)
    assert not report.ok and report.violations[0].entailment == 0.0
    assert "supports this at 0.00, below the 0.70 required" in report.violations[0].detail


def test_a_near_miss_score_is_never_printed_as_the_threshold():
    """0.6996 against 0.70 used to print 'supports this at 0.70, below the 0.70'."""
    v = entailment.EntailmentViolation(0, "t", "p", 0.6996, 0.7)
    assert "supports this at 0.69, below the 0.70 required" in v.detail
    report = entailment.GateReport(model_id="m", model_revision="r")
    report.violations.append(v)
    assert "scored 0.69 against its cited facts (threshold 0.70)" in str(
        entailment.EntailmentError(report))


def test_load_refuses_missing_revision(fresh_load):
    with pytest.raises(entailment.EntailmentUnavailable, match="NLI_MODEL_REVISION"):
        entailment._load("m", "")


def test_load_refuses_when_torch_missing(monkeypatch, fresh_load):
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(entailment.EntailmentUnavailable, match="requires torch"):
        entailment._load("m", "r" * 40)


def test_load_refuses_when_weights_not_in_image(monkeypatch, fresh_load):
    _install_fakes(monkeypatch, {0: "ENTAILMENT"},
                   from_pretrained_error=OSError("no local files"))
    with pytest.raises(entailment.EntailmentUnavailable,
                       match="could not load m@rrrrrrrrrrrr from the image: OSError"):
        entailment._load("m", "r" * 40)


def test_load_refuses_checkpoint_without_entailment_label(monkeypatch, fresh_load):
    _install_fakes(monkeypatch, {0: "POS", 1: "NEG"})
    with pytest.raises(entailment.EntailmentUnavailable, match="no 'entailment' class"):
        entailment._load("m", "r" * 40)
