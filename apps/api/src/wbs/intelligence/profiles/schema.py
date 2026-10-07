"""``wbs-domain-profile/v1``: the declarative contract every WBS Domain Profile must satisfy.

Industries are DATA here: no Python enum names an industry. Only the heuristic predicate TYPES
are code (a closed, side-effect-free vocabulary); a profile cannot carry executable content.
Every model is frozen and rejects unknown fields, so a profile cannot smuggle in an approver,
a governance switch or a new control level.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.wbs.domain.digest import DICTIONARY_LIST_KEYS
from src.wbs.domain.governance import CORE_DECOMPOSITION_TERMS, ControlLevel

SCHEMA_VERSION = "wbs-domain-profile/v1"

_IDENT = r"^[a-z][a-z0-9_]{1,40}$"
_SEMVER = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
_TERM = r"^[a-z][a-z0-9_]*$"
_KIND = re.compile(r"^([a-z][a-z0-9_]*):([a-z][a-z0-9_]*)$")
_DIGEST = r"^sha256:[0-9a-f]{64}$"
_CONTROL_LEVELS = frozenset(level.value for level in ControlLevel)
_DICTIONARY_FIELDS = frozenset({"scope_statement", *DICTIONARY_LIST_KEYS})

# Prompt guidance is product content sent to a model: it may describe the domain, never steer
# governance. These phrasings are refused outright (the loader fails, the profile never ships).
_GOVERNANCE_OVERRIDES = re.compile(
    r"ignore (all |any )?(previous|prior|above)|disregard (the |all )?(previous|prior|above|instructions)"
    r"|auto-?approv|you may approve|approve the change|submit the change|on behalf of the user"
    r"|bypass|override (the )?(governance|policy|rules|core)|system prompt|act as (an? )?(admin|approver)",
    re.IGNORECASE,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Text = Annotated[str, Field(min_length=1, max_length=500)]


class ProfilePin(_Frozen):
    """An exact profile identity: what change sets, baselines and bundles pin."""

    profile_id: str = Field(pattern=_IDENT)
    profile_version: str = Field(pattern=_SEMVER)
    profile_digest: str = Field(pattern=_DIGEST)
    namespace: str | None = Field(default=None, pattern=_TERM)


class Archetype(_Frozen):
    project_types: tuple[Annotated[str, Field(pattern=_TERM)], ...] = ()
    tags: tuple[Annotated[str, Field(pattern=_TERM)], ...] = ()


class TermEntry(_Frozen):
    term: str = Field(pattern=_TERM)
    preferred: Text
    synonyms: tuple[Text, ...] = ()


class KindDeclaration(_Frozen):
    term: str = Field(pattern=_TERM)
    description: Text


class PatternLevel(_Frozen):
    kind: str
    label: Text
    control_level: str | None = None


class DecompositionPattern(_Frozen):
    pattern_id: str = Field(pattern=_IDENT)
    description: Text
    levels: tuple[PatternLevel, ...] = Field(min_length=1)


class ScopeCategory(_Frozen):
    category_id: str = Field(pattern=_IDENT)
    label: Text
    expectation: Literal["expected", "conditional", "optional"]
    condition: Text | None = None
    evidence_cues: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def _conditional_has_condition(self) -> ScopeCategory:
        if (self.expectation == "conditional") != (self.condition is not None):
            raise ValueError("a conditional scope category states its condition (and only it does)")
        return self


class _Heuristic(_Frozen):
    rule_id: str = Field(pattern=_IDENT)
    severity: Literal["INFO", "WARNING"] = "WARNING"  # advisory: never a blocking GAP
    message: Text


class MaxDepth(_Heuristic):
    predicate: Literal["max_depth"]
    max: int = Field(ge=1, le=20)


class FanoutBounds(_Heuristic):
    predicate: Literal["fanout_bounds"]
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=1)
    applies_to_kind: str | None = None


class RequiredDictionaryFields(_Heuristic):
    predicate: Literal["required_dictionary_fields"]
    control_level: str
    fields: tuple[str, ...] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def _known_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = set(value) - _DICTIONARY_FIELDS
        if unknown:
            raise ValueError(f"unknown wbs-dictionary/v1 fields {sorted(unknown)}")
        return value


class SiblingKindHomogeneity(_Heuristic):
    predicate: Literal["sibling_kind_homogeneity"]


class ForbiddenParentChildKinds(_Heuristic):
    predicate: Literal["forbidden_parent_child_kinds"]
    parent_kind: str
    child_kind: str


class ControlLevelNesting(_Heuristic):
    predicate: Literal["control_level_nesting"]
    ancestor: str
    descendant: str
    allowed: bool


Heuristic = Annotated[
    MaxDepth | FanoutBounds | RequiredDictionaryFields | SiblingKindHomogeneity | ForbiddenParentChildKinds
    | ControlLevelNesting,
    Field(discriminator="predicate"),
]


class RecommendedControlLevel(_Frozen):
    kind: str
    control_level: str


class SpecialistWarning(_Frozen):
    warning_id: str = Field(pattern=_IDENT)
    trigger_cues: tuple[Text, ...] = Field(min_length=1)
    message: Text


class ExampleNode(_Frozen):
    ref: str = Field(pattern=_IDENT)
    parent_ref: str | None = Field(default=None, pattern=_IDENT)
    name: Text
    kind: str | None = None
    control_level: str | None = None


class Example(_Frozen):
    example_id: str = Field(pattern=_IDENT)
    title: Text
    nodes: tuple[ExampleNode, ...] = Field(min_length=1)


class Composition(_Frozen):
    includes: tuple[ProfilePin, ...] = ()
    compatible_with: tuple[Annotated[str, Field(pattern=_IDENT)], ...] = ()
    conflicts_with: tuple[Annotated[str, Field(pattern=_IDENT)], ...] = ()


class WBSDomainProfileV1(_Frozen):
    """One versioned Domain Profile. Advisory only: it can never author or approve WBS."""

    schema_version: Literal["wbs-domain-profile/v1"]
    profile_id: str = Field(pattern=_IDENT)
    version: str = Field(pattern=_SEMVER)
    namespace: str = Field(pattern=_TERM, max_length=40)
    title: Text
    status: Literal["active", "deprecated"]
    applicable_archetypes: tuple[Archetype, ...] = ()
    terminology: tuple[TermEntry, ...] = ()
    decomposition_kinds: tuple[KindDeclaration, ...] = ()
    decomposition_patterns: tuple[DecompositionPattern, ...] = ()
    expected_scope_categories: tuple[ScopeCategory, ...] = ()
    validation_heuristics: tuple[Heuristic, ...] = ()
    recommended_control_levels: tuple[RecommendedControlLevel, ...] = ()
    specialist_warnings: tuple[SpecialistWarning, ...] = ()
    examples: tuple[Example, ...] = ()
    prompt_guidance: str | None = Field(default=None, max_length=2000)
    composition: Composition = Composition()

    @field_validator("namespace")
    @classmethod
    def _not_core(cls, value: str) -> str:
        if value == "core":
            raise ValueError("the core namespace belongs to C2Pro, never to a profile")
        return value

    @field_validator("prompt_guidance")
    @classmethod
    def _no_governance_override(cls, value: str | None) -> str | None:
        if value is not None and _GOVERNANCE_OVERRIDES.search(value):
            raise ValueError("prompt_guidance may describe the domain, never steer governance")
        return value

    @model_validator(mode="after")
    def _references(self) -> WBSDomainProfileV1:
        declared = [kind.term for kind in self.decomposition_kinds]
        if len(set(declared)) != len(declared):
            raise ValueError("a decomposition term is declared twice")
        for level in self.control_levels_used():
            if level not in _CONTROL_LEVELS:
                raise ValueError(f"control_level {level!r} is not a core control level")
        for kind in self.kinds_used():
            match = _KIND.fullmatch(kind)
            if match is None:
                raise ValueError(f"decomposition kind {kind!r} is not 'namespace:term'")
            namespace, term = match.groups()
            if namespace == "core" and term not in CORE_DECOMPOSITION_TERMS:
                raise ValueError(f"{kind!r} is not in the core vocabulary")
            if namespace == self.namespace and term not in declared:
                raise ValueError(f"{kind!r} uses an undeclared term of this profile")
            if namespace not in {"core", self.namespace} and not self.composition.includes:
                raise ValueError(f"{kind!r} belongs to another namespace and this profile includes none")
        for example in self.examples:
            own = {node.ref for node in example.nodes}
            if len(own) != len(example.nodes):
                raise ValueError(f"example {example.example_id} repeats a node ref")
            if any(node.parent_ref is not None and node.parent_ref not in own for node in example.nodes):
                raise ValueError(f"example {example.example_id} has a parent outside the example")
        rule_ids = [rule.rule_id for rule in self.validation_heuristics]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("a heuristic rule_id is used twice")
        return self

    def kinds_used(self) -> list[str]:
        kinds = [lvl.kind for pattern in self.decomposition_patterns for lvl in pattern.levels]
        kinds += [rec.kind for rec in self.recommended_control_levels]
        kinds += [node.kind for example in self.examples for node in example.nodes if node.kind]
        for rule in self.validation_heuristics:
            if isinstance(rule, ForbiddenParentChildKinds):
                kinds += [rule.parent_kind, rule.child_kind]
            elif isinstance(rule, FanoutBounds) and rule.applies_to_kind:
                kinds.append(rule.applies_to_kind)
        return kinds

    def control_levels_used(self) -> list[str]:
        levels = [lvl.control_level for p in self.decomposition_patterns for lvl in p.levels if lvl.control_level]
        levels += [rec.control_level for rec in self.recommended_control_levels]
        levels += [node.control_level for e in self.examples for node in e.nodes if node.control_level]
        for rule in self.validation_heuristics:
            if isinstance(rule, RequiredDictionaryFields):
                levels.append(rule.control_level)
            elif isinstance(rule, ControlLevelNesting):
                levels += [rule.ancestor, rule.descendant]
        return levels


__all__ = [
    "SCHEMA_VERSION",
    "ControlLevelNesting",
    "FanoutBounds",
    "ForbiddenParentChildKinds",
    "Heuristic",
    "MaxDepth",
    "ProfilePin",
    "RequiredDictionaryFields",
    "SiblingKindHomogeneity",
    "WBSDomainProfileV1",
]
