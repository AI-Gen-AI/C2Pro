"""Read-only Domain Profile catalog: load, digest, lock-verify and compose (PC-2b.1, ADR-030).

* ``profile_digest`` = ``sha256:`` over the PC-2a ``canonical_json`` of the validated profile, so
  key order and YAML formatting never change it while any content change does.
* ``profiles.lock.json`` freezes every published ``(profile_id, version)`` to its digest. Editing a
  published version in place, deleting one, or shipping an unlocked one fails the load (and CI):
  a change needs a new version, so old proposals stay reproducible.
* Composition fails closed: unknown pins, digest mismatches, two versions of one profile, two
  profiles claiming one namespace and declared conflicts are errors. A bundle pins its
  constituents by exact digest, so its own digest binds them transitively.
* The catalog is immutable at runtime: no database records, no admin CMS, no mutation API.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from pydantic import ValidationError

from src.wbs.domain.digest import canonical_json, normalize_profile_ref
from src.wbs.intelligence.profiles.schema import (
    ControlLevelNesting,
    FanoutBounds,
    Heuristic,
    WBSDomainProfileV1,
)

DEFAULT_CATALOG_DIR = Path(__file__).parent
LOCK_FILE = "profiles.lock.json"
LOCK_VERSION = "wbs-profiles-lock/v1"
EFFECTIVE_SET_VERSION = "wbs-profile-set/v1"


class ProfileCatalogError(ValueError):
    """The catalog on disk is not a valid, locked set of profiles (fails the load and CI)."""


class ProfileCompositionError(ValueError):
    """A requested profile combination cannot be resolved (fail closed)."""


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def profile_digest(model: WBSDomainProfileV1) -> str:
    """The digest that pins bind: the exact validated content, independent of formatting."""
    return _sha256(model.model_dump(mode="json"))


@dataclass(frozen=True)
class CatalogProfile:
    model: WBSDomainProfileV1
    digest: str

    @property
    def profile_id(self) -> str:
        return self.model.profile_id

    @property
    def version(self) -> str:
        return self.model.version

    @property
    def namespace(self) -> str:
        return self.model.namespace

    def pin(self) -> dict[str, str]:
        """The change-set / baseline pin (``normalize_profile_ref`` accepts the extra namespace)."""
        return {"profile_id": self.profile_id, "profile_version": self.version,
                "profile_digest": self.digest, "namespace": self.namespace}


@dataclass(frozen=True)
class HeuristicRuleRef:
    profile_id: str
    profile_version: str
    profile_digest: str
    rule_id: str


@dataclass(frozen=True)
class ResolvedProfileSet:
    """An exact, conflict-free set of profiles (bundles expanded) -- the effective profile identity."""

    members: tuple[CatalogProfile, ...]

    def pins(self) -> list[dict[str, str]]:
        return [member.pin() for member in self.members]

    @property
    def effective_digest(self) -> str:
        return _sha256({"version": EFFECTIVE_SET_VERSION,
                        "pins": [{k: v for k, v in pin.items() if k != "namespace"} for pin in self.pins()]})

    def terms_by_namespace(self) -> dict[str, frozenset[str]]:
        return {m.namespace: frozenset(k.term for k in m.model.decomposition_kinds) for m in self.members}

    def owner_of(self, namespace: str) -> CatalogProfile | None:
        return next((m for m in self.members if m.namespace == namespace), None)

    def display_term(self, kind: str) -> str:
        """Terminology is namespaced: a kind is shown in its owning profile's words, never overridden."""
        namespace, _, term = kind.partition(":")
        owner = self.owner_of(namespace)
        if owner is not None:
            for entry in owner.model.terminology:
                if entry.term == term:
                    return entry.preferred
        return term

    def synonyms(self, term: str) -> set[str]:
        return {s for m in self.members for entry in m.model.terminology if entry.term == term for s in entry.synonyms}

    def heuristics(self) -> list[tuple[HeuristicRuleRef, Heuristic]]:
        return [(HeuristicRuleRef(m.profile_id, m.version, m.digest, rule.rule_id), rule)
                for m in self.members for rule in m.model.validation_heuristics]

    def contradictions(self) -> list[tuple[HeuristicRuleRef, HeuristicRuleRef]]:
        """Pairs of rules that cannot both hold; evaluation reports them AMBIGUOUS, never GAP."""
        rules = self.heuristics()
        pairs: list[tuple[HeuristicRuleRef, HeuristicRuleRef]] = []
        for i, (ref_a, a) in enumerate(rules):
            for ref_b, b in rules[i + 1:]:
                if _contradict(a, b):
                    pairs.append((ref_a, ref_b))
        return pairs


def _contradict(a: Heuristic, b: Heuristic) -> bool:
    if isinstance(a, ControlLevelNesting) and isinstance(b, ControlLevelNesting):
        return (a.ancestor, a.descendant) == (b.ancestor, b.descendant) and a.allowed != b.allowed
    if isinstance(a, FanoutBounds) and isinstance(b, FanoutBounds) and a.applies_to_kind == b.applies_to_kind:
        return ((a.min is not None and b.max is not None and a.min > b.max)
                or (b.min is not None and a.max is not None and b.min > a.max))
    return False


class ProfileCatalog:
    """An immutable set of locked profiles."""

    def __init__(self, profiles: Iterable[CatalogProfile]) -> None:
        by_key: dict[tuple[str, str], CatalogProfile] = {}
        for profile in profiles:
            by_key[(profile.profile_id, profile.version)] = profile
        self._by_key: Mapping[tuple[str, str], CatalogProfile] = MappingProxyType(by_key)

    def profiles(self) -> tuple[CatalogProfile, ...]:
        return tuple(self._by_key[key] for key in sorted(self._by_key))

    def get(self, profile_id: str, version: str) -> CatalogProfile:
        try:
            return self._by_key[(profile_id, version)]
        except KeyError as exc:
            raise ProfileCompositionError(f"unknown profile {profile_id}@{version}") from exc

    def _lookup(self, pin: Mapping[str, Any]) -> CatalogProfile:
        try:
            ref = normalize_profile_ref(pin)
        except (TypeError, ValueError) as exc:
            raise ProfileCompositionError(f"invalid profile pin: {exc}") from exc
        profile = self.get(ref["profile_id"], ref["profile_version"])
        if profile.digest != ref["profile_digest"]:
            raise ProfileCompositionError(
                f"profile {profile.profile_id}@{profile.version} pinned with a digest that is not the published one")
        return profile

    def resolve(self, pins: Iterable[Mapping[str, Any]]) -> ResolvedProfileSet:
        members: dict[str, CatalogProfile] = {}
        pending = [self._lookup(pin) for pin in pins]
        while pending:
            profile = pending.pop()
            current = members.get(profile.profile_id)
            if current is not None:
                if current.version != profile.version:
                    raise ProfileCompositionError(
                        f"one version per profile: {profile.profile_id} pinned as {current.version} and {profile.version}")
                continue
            members[profile.profile_id] = profile
            pending += [self._lookup(include.model_dump(exclude_none=True)) for include in profile.model.composition.includes]
        by_namespace: dict[str, str] = {}
        for profile in members.values():
            other = by_namespace.setdefault(profile.namespace, profile.profile_id)
            if other != profile.profile_id:
                raise ProfileCompositionError(
                    f"namespace {profile.namespace!r} is claimed by both {other} and {profile.profile_id}")
        for profile in members.values():
            clash = set(profile.model.composition.conflicts_with) & set(members)
            if clash:
                raise ProfileCompositionError(f"{profile.profile_id} declares a conflict with {sorted(clash)}")
        return ResolvedProfileSet(members=tuple(members[key] for key in sorted(members)))


def _load_profile(path: Path) -> CatalogProfile:
    try:
        model = WBSDomainProfileV1.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (ValidationError, yaml.YAMLError) as exc:
        raise ProfileCatalogError(f"{path.name}: invalid profile: {exc}") from exc
    if path.name != f"{model.profile_id}@{model.version}.yaml" or path.parent.name != model.namespace:
        raise ProfileCatalogError(
            f"{path.name}: the file name must be <namespace>/<profile_id>@<version>.yaml "
            f"({model.namespace}/{model.profile_id}@{model.version}.yaml)")
    return CatalogProfile(model=model, digest=profile_digest(model))


def _verify_bundles(profiles: Mapping[tuple[str, str], CatalogProfile]) -> None:
    for profile in profiles.values():
        reachable = {profile.namespace: profile}
        pending = list(profile.model.composition.includes)
        while pending:
            include = pending.pop()
            constituent = profiles.get((include.profile_id, include.profile_version))
            if constituent is None or constituent.digest != include.profile_digest:
                raise ProfileCatalogError(
                    f"{profile.profile_id}@{profile.version}: constituent {include.profile_id}@"
                    f"{include.profile_version} is unknown or not pinned by its published digest")
            reachable[constituent.namespace] = constituent
            pending += list(constituent.model.composition.includes)
        for kind in profile.model.kinds_used():
            namespace, _, term = kind.partition(":")
            if namespace in {"core", profile.namespace}:
                continue
            owner = reachable.get(namespace)
            if owner is None or term not in {k.term for k in owner.model.decomposition_kinds}:
                raise ProfileCatalogError(
                    f"{profile.profile_id}@{profile.version}: {kind!r} is not declared by an included profile")


def load_catalog(root: Path) -> ProfileCatalog:
    """Load ``root/library/<namespace>/<id>@<version>.yaml`` and verify it against ``profiles.lock.json``."""
    lock_path = root / LOCK_FILE
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileCatalogError(f"cannot read {LOCK_FILE}: {exc}") from exc
    if lock.get("lock_version") != LOCK_VERSION:
        raise ProfileCatalogError(f"{LOCK_FILE} must declare lock_version {LOCK_VERSION}")
    locked = {(e["profile_id"], e["version"]): e for e in lock.get("profiles", [])}

    profiles: dict[tuple[str, str], CatalogProfile] = {}
    for path in sorted((root / "library").rglob("*.yaml")):
        profile = _load_profile(path)
        key = (profile.profile_id, profile.version)
        if key in profiles:
            raise ProfileCatalogError(f"{profile.profile_id}@{profile.version} is published twice")
        entry = locked.get(key)
        if entry is None:
            raise ProfileCatalogError(f"{profile.profile_id}@{profile.version} is not in profiles.lock")
        if entry.get("digest") != profile.digest or entry.get("namespace") != profile.namespace:
            raise ProfileCatalogError(
                f"the digest of published profile {profile.profile_id}@{profile.version} changed: "
                "publish a new version instead of editing it")
        profiles[key] = profile
    for key in locked:
        if key not in profiles:
            raise ProfileCatalogError(f"published profile {key[0]}@{key[1]} is missing from the catalog")
    _verify_bundles(profiles)
    return ProfileCatalog(profiles.values())


@lru_cache(maxsize=1)
def default_catalog() -> ProfileCatalog:
    """The shipped catalog (immutable; loaded once per process)."""
    return load_catalog(DEFAULT_CATALOG_DIR)


__all__ = [
    "DEFAULT_CATALOG_DIR",
    "CatalogProfile",
    "HeuristicRuleRef",
    "ProfileCatalog",
    "ProfileCatalogError",
    "ProfileCompositionError",
    "ResolvedProfileSet",
    "default_catalog",
    "load_catalog",
    "profile_digest",
]
