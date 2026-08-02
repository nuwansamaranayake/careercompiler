"""D3/D5: the entailment gate. A sentence stronger than its evidence is a compile error.

The linker proves a bullet points at real facts. This proves the bullet does not say more
than those facts support — the difference between "led a team of 4" and "led engineering",
which reference integrity alone cannot see because both cite the same true fact.

Two rules govern this module, and both exist because of how this class of system fails:

**The model is pinned by revision digest, not by tag.** `main` moves. A gate whose verdict can
change because somebody pushed to a model repository is not a gate. The digest lives in
`DECISIONS.md` with the date and the source it was read from.

**There is no fallback path.** If the model cannot be loaded, `compile` raises
`EntailmentUnavailable` and the build fails. It does not degrade to keyword overlap, it does
not warn and continue, and no environment variable can make it pass. A silent fallback on the
fabrication gate is the exact failure this application exists to prevent, and it is the same
class of defect as the mock-data fallback that cost GoviHub five days.

The label index is read from `model.config.id2label` at load time rather than hardcoded.
Label order differs between NLI checkpoints, and a gate that assumed the wrong index would
score contradiction as entailment and pass everything — a vacuous gate that looks green.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Protocol

from .facts import AtomicClaim
from .linker import Bullet


class EntailmentUnavailable(Exception):
    """The gate could not run. This fails the build; it never degrades to a weaker check."""


class EntailmentError(Exception):
    """One or more sentences claim more than their cited evidence supports."""

    def __init__(self, report: "GateReport"):
        self.report = report
        first = report.violations[0]
        super().__init__(
            f"{len(report.violations)} sentence(s) outran their evidence; first: "
            f"{first.text!r} scored {first.entailment:.2f} against its cited facts "
            f"(threshold {first.threshold:.2f})")


@dataclass(frozen=True)
class EntailmentViolation:
    bullet_index: int
    text: str
    premise: str
    entailment: float
    threshold: float

    @property
    def detail(self) -> str:
        return (f"the cited evidence supports this at {self.entailment:.2f}, below the "
                f"{self.threshold:.2f} required; the sentence claims more than the fact does")


@dataclass
class GateReport:
    violations: list[EntailmentViolation] = field(default_factory=list)
    scored: list[tuple[int, float]] = field(default_factory=list)
    model_id: str = ""
    model_revision: str = ""

    @property
    def ok(self) -> bool:
        return not self.violations

    def raise_if_broken(self) -> None:
        if self.violations:
            raise EntailmentError(self)


class Scorer(Protocol):
    """(premise, hypothesis) -> probability that the premise entails the hypothesis."""

    def __call__(self, premise: str, hypothesis: str) -> float: ...


@lru_cache(maxsize=1)
def _load(model_id: str, revision: str) -> Callable[[str, str], float]:
    """Load the pinned checkpoint. Raises EntailmentUnavailable rather than degrading.

    `local_files_only=True` is deliberate: D4 requires the weights baked into the image. A
    first request that reaches the network would make the gate's availability depend on
    Hugging Face being up, on a box that serves a live revenue product.
    """
    if not revision:
        raise EntailmentUnavailable(
            "NLI_MODEL_REVISION is not set; the entailment gate refuses to resolve a "
            "floating tag, because a gate whose verdict can change when somebody pushes to "
            "a model repository is not a gate")
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as e:
        raise EntailmentUnavailable(
            f"the entailment gate requires torch and transformers: {e}") from e

    try:
        tok = AutoTokenizer.from_pretrained(model_id, revision=revision,
                                            local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_id, revision=revision, local_files_only=True)
    except Exception as e:
        raise EntailmentUnavailable(
            f"could not load {model_id}@{revision[:12]} from the image: {type(e).__name__}: "
            f"{e}. The weights must be baked in; the gate does not download at request time."
        ) from e
    model.eval()

    # Read the label order from the checkpoint. Never assume it.
    labels = {v.lower(): k for k, v in model.config.id2label.items()}
    if "entailment" not in labels:
        raise EntailmentUnavailable(
            f"{model_id}@{revision[:12]} exposes labels {list(model.config.id2label.values())}, "
            "which contain no 'entailment' class; this checkpoint cannot drive the gate")
    entail_idx = labels["entailment"]

    def score(premise: str, hypothesis: str) -> float:
        with torch.no_grad():
            batch = tok(premise, hypothesis, truncation=True, max_length=512,
                        return_tensors="pt")
            probs = torch.softmax(model(**batch).logits[0], dim=-1)
        return float(probs[entail_idx])

    return score


def load_scorer(model_id: str, revision: str) -> Callable[[str, str], float]:
    return _load(model_id, revision)


def gate(
    bullets: list[Bullet],
    claims: list[AtomicClaim],
    threshold: float,
    model_id: str,
    revision: str,
    scorer: Scorer | None = None,
) -> GateReport:
    """Score every bullet against the facts it cites.

    `scorer` is a seam for tests, which must be able to exercise the gate's logic without a
    700 MB download. It is never populated from configuration: production has exactly one
    path, and it either loads the pinned model or fails.
    """
    score = scorer or _load(model_id, revision)
    by_id = {c.core.claim_id: c for c in claims}
    report = GateReport(model_id=model_id, model_revision=revision)

    for i, b in enumerate(bullets):
        premise = " ".join(by_id[c].core.statement for c in b.cites if c in by_id).strip()
        if not premise:
            # The linker owns this failure; scoring against an empty premise would invent a
            # number for a sentence that has no evidence at all.
            continue
        p = score(premise, b.text.strip())
        report.scored.append((i, round(p, 4)))
        if p < threshold:
            report.violations.append(EntailmentViolation(
                bullet_index=i, text=b.text.strip(), premise=premise,
                entailment=p, threshold=threshold))

    return report
