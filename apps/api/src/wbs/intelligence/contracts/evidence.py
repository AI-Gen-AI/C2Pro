"""Evidence contract of WBS intelligence: trusted input classes and source-specific authority.

Two locations are never confused:

* ``CanonicalSourceRef`` -- a reproducible locator into the exact ORIGINAL artifact (document,
  revision, blob / artifact identity, page / section / row / offsets of the original text). It is
  selected by the server when the evidence manifest is built, BEFORE anything is anonymised.
* ``ModelVisibleExcerpt`` -- the sanitised (PII-anonymised) text the model reads. Offsets or quotes
  in it are never presented as positions in the source document: anonymisation changes lengths.

A model cites a manifest ``excerpt_id`` (plus an optional quote of the model-visible text); it can
never state a document, revision, page or offset, and never its own authority. The authority comes
from the manifest item's input class; verification is deterministic and done by the server.
Reuses the ADR-011 ``LocatorQuality`` / ``VerificationStatus`` vocabulary (no second evidence model).
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.evidence.domain.models import LocatorQuality, VerificationStatus
from src.wbs.domain.digest import canonical_json

MANIFEST_VERSION = "wbs-evidence-manifest/v1"
_DIGEST = r"^sha256:[0-9a-f]{64}$"
EXCERPT_ID = r"^[A-Z][A-Z0-9_-]{0,15}$"
MAX_EXCERPT_CHARS = 8000
MAX_QUOTE_CHARS = 400


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InputClass(StrEnum):
    """What may enter WBS intelligence, and with which authority (ADR-030)."""

    TRUSTED_PROJECT_EVIDENCE = "TRUSTED_PROJECT_EVIDENCE"  # #714 TRUSTED current revisions / entities
    PROPOSED_EVIDENCE = "PROPOSED_EVIDENCE"  # PROPOSED artifacts, untrusted revisions -- human-included only
    ADVISORY_EVIDENCE = "ADVISORY_EVIDENCE"  # schedule hierarchy, BC3 chapters, legacy structure
    HUMAN_PROVIDED_IMPORT = "HUMAN_PROVIDED_IMPORT"  # an imported WBS: the target, not proof of itself
    CURRENT_APPROVED_WBS = "CURRENT_APPROVED_WBS"  # Baseline #N: the target of review, not evidence
    USER_CONTEXT = "USER_CONTEXT"  # the requester's bounded free text: data, recorded


class EvidenceAuthority(StrEnum):
    TRUSTED = "TRUSTED"
    PROPOSED = "PROPOSED"
    ADVISORY = "ADVISORY"
    HUMAN_IMPORT = "HUMAN_IMPORT"
    USER_CONTEXT = "USER_CONTEXT"


AUTHORITY_BY_INPUT_CLASS: dict[InputClass, EvidenceAuthority] = {
    InputClass.TRUSTED_PROJECT_EVIDENCE: EvidenceAuthority.TRUSTED,
    InputClass.PROPOSED_EVIDENCE: EvidenceAuthority.PROPOSED,
    InputClass.ADVISORY_EVIDENCE: EvidenceAuthority.ADVISORY,
    InputClass.HUMAN_PROVIDED_IMPORT: EvidenceAuthority.HUMAN_IMPORT,
    InputClass.CURRENT_APPROVED_WBS: EvidenceAuthority.HUMAN_IMPORT,
    InputClass.USER_CONTEXT: EvidenceAuthority.USER_CONTEXT,
}


class EvidenceBasis(StrEnum):
    DIRECT = "DIRECT"  # a located quote of trusted project evidence
    INFERRED = "INFERRED"  # reasoned from cited evidence, no verbatim support
    PROFILE_HEURISTIC = "PROFILE_HEURISTIC"  # a pinned profile rule -- never documentary fact
    USER_CONTEXT = "USER_CONTEXT"
    IMPORTED_STRUCTURE = "IMPORTED_STRUCTURE"


class CanonicalSourceRef(_Frozen):
    """A reproducible location in the exact original artifact (never derived from model text)."""

    document_id: UUID
    revision_id: UUID
    blob_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: UUID | None = None
    artifact_version: int | None = Field(default=None, ge=1)
    artifact_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=200)
    row: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    locator_quality: LocatorQuality

    @model_validator(mode="after")
    def _offsets(self) -> CanonicalSourceRef:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("original-text offsets come as a pair")
        if self.char_start is not None and self.char_end is not None and self.char_end < self.char_start:
            raise ValueError("char_end precedes char_start")
        return self


def _text_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class ModelVisibleExcerpt(_Frozen):
    """The sanitised text a model reads. Quotes are checked against THIS text only."""

    text: str = Field(min_length=1, max_length=MAX_EXCERPT_CHARS)
    text_digest: str = Field(pattern=_DIGEST)
    transform: str = Field(min_length=1, max_length=100)  # e.g. "pii-anonymizer/v1" or "none"
    anonymised: bool

    @classmethod
    def of(cls, text: str, *, transform: str) -> ModelVisibleExcerpt:
        return cls(text=text, text_digest=_text_digest(text), transform=transform, anonymised=transform != "none")

    @model_validator(mode="after")
    def _digest_matches(self) -> ModelVisibleExcerpt:
        if self.text_digest != _text_digest(self.text):
            raise ValueError("text_digest does not match the model-visible text")
        return self


class ManifestItem(_Frozen):
    excerpt_id: str = Field(pattern=EXCERPT_ID)
    input_class: InputClass
    canonical_source: CanonicalSourceRef | None
    model_visible: ModelVisibleExcerpt

    @model_validator(mode="after")
    def _source_presence(self) -> ManifestItem:
        if (self.input_class is InputClass.USER_CONTEXT) != (self.canonical_source is None):
            raise ValueError("every project artifact excerpt has a canonical source; user context has none")
        return self

    @property
    def authority(self) -> EvidenceAuthority:
        return AUTHORITY_BY_INPUT_CLASS[self.input_class]


class EvidenceManifest(_Frozen):
    """Exactly what one run may show a model -- tenant and project explicit, digested."""

    tenant_id: UUID
    project_id: UUID
    items: tuple[ManifestItem, ...]

    @model_validator(mode="after")
    def _unique(self) -> EvidenceManifest:
        ids = [item.excerpt_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("an excerpt_id appears twice in the evidence manifest")
        return self

    def get(self, excerpt_id: str) -> ManifestItem | None:
        return next((item for item in self.items if item.excerpt_id == excerpt_id), None)

    @property
    def evidence_set_digest(self) -> str:
        body = {
            "version": MANIFEST_VERSION,
            "tenant_id": str(self.tenant_id),
            "project_id": str(self.project_id),
            "items": sorted(
                ({"excerpt_id": item.excerpt_id, "input_class": item.input_class.value,
                  "canonical_source": None if item.canonical_source is None
                  else item.canonical_source.model_dump(mode="json"),
                  "text_digest": item.model_visible.text_digest, "transform": item.model_visible.transform}
                 for item in self.items),
                key=lambda entry: str(entry["excerpt_id"]),
            ),
        }
        return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


class ModelEvidenceCitation(_Frozen):
    """What a model may say about evidence: a manifest excerpt and a quote of ITS visible text."""

    excerpt_id: str | None = Field(default=None, pattern=EXCERPT_ID)
    basis: Literal["DIRECT", "INFERRED", "PROFILE_HEURISTIC", "USER_CONTEXT", "IMPORTED_STRUCTURE"]
    quote: str | None = Field(default=None, min_length=1, max_length=MAX_QUOTE_CHARS)
    profile_rule: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,40}:[a-z][a-z0-9_]{1,40}$")


class ProfileRuleRef(_Frozen):
    profile_id: str
    profile_version: str
    profile_digest: str = Field(pattern=_DIGEST)
    rule_id: str


class EvidenceItem(_Frozen):
    """Server-verified evidence of a stored finding or proposal."""

    basis: EvidenceBasis
    authority: EvidenceAuthority | None  # None only for a profile heuristic (not project evidence)
    excerpt_id: str | None = None
    canonical_source: CanonicalSourceRef | None = None  # copied from the manifest, never from the model
    model_quote: str | None = None
    quote_scope: Literal["MODEL_VISIBLE_TEXT"] | None = None
    verification: VerificationStatus
    profile_rule: ProfileRuleRef | None = None

    @model_validator(mode="after")
    def _shape(self) -> EvidenceItem:
        if self.basis is EvidenceBasis.PROFILE_HEURISTIC:
            if self.profile_rule is None or self.excerpt_id is not None:
                raise ValueError("a profile heuristic cites a pinned profile rule, not a document")
        elif self.excerpt_id is None or self.authority is None:
            raise ValueError("project evidence cites a manifest excerpt and carries its authority")
        if (self.model_quote is None) != (self.quote_scope is None):
            raise ValueError("a quote is always scoped to the model-visible text")
        if self.basis is EvidenceBasis.DIRECT and (self.model_quote is None
                                                   or self.verification is not VerificationStatus.VERIFIED):
            raise ValueError("DIRECT evidence is a verified quote")
        return self


__all__ = [
    "AUTHORITY_BY_INPUT_CLASS",
    "CanonicalSourceRef",
    "EvidenceAuthority",
    "EvidenceBasis",
    "EvidenceItem",
    "EvidenceManifest",
    "InputClass",
    "ManifestItem",
    "ModelEvidenceCitation",
    "ModelVisibleExcerpt",
    "ProfileRuleRef",
]
