"""JD parsing: a job description becomes typed requirements.

The LLM parses (schema-forced); nothing downstream trusts its prose. Requirements also
arrive by explicit data entry — the keyless path used by tests, the demo, and users who
want full control over what they are matched against.
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


class ReqKind(str, Enum):
    skill = "skill"
    experience = "experience"
    education = "education"
    other = "other"


class Requirement(BaseModel):
    req_key: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: ReqKind
    must_have: bool


JD_SCHEMA = {
    "name": "requirements",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "req_key": {"type": "string"},
                        "text": {"type": "string"},
                        "kind": {"type": "string", "enum": [k.value for k in ReqKind]},
                        "must_have": {"type": "boolean"},
                    },
                    "required": ["req_key", "text", "kind", "must_have"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["requirements"],
        "additionalProperties": False,
    },
}


class CompletesJson(Protocol):
    def complete(self, *, model: str, messages: list[dict],
                 json_schema: dict | None = None, temperature: float = 0.0): ...


def parse_jd(gateway: CompletesJson, model: str, jd_text: str) -> list[Requirement]:
    if not model:
        raise RuntimeError("LLM_MODEL_EXTRACTION is not set. Refusing to guess a model.")
    result = gateway.complete(
        model=model,
        messages=[
            {"role": "system",
             "content": ("Decompose the job description into typed requirements. req_key is "
                         "a short snake_case label. must_have=true only when the posting "
                         "treats it as required rather than preferred. Do not invent "
                         "requirements the text does not state. Return JSON.")},
            {"role": "user", "content": jd_text},
        ],
        json_schema=JD_SCHEMA,
    )
    return [Requirement.model_validate(r) for r in result.get("requirements", [])]


def requirements_from_entries(entries: list[dict]) -> list[Requirement]:
    """Explicit data-entry path; raises on malformed entries."""
    return [Requirement.model_validate(e) for e in entries]
