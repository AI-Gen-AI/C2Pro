"""Golden fixture contract (``wbs-golden-fixture/v1``) -- synthetic or licensed content only.

A fixture names an archetype, pinned profiles, the target structure (empty for GENERATE), the
evidence the model may see, the availability of downstream authorities and the expectations a
deterministic scorer checks: gold scope (by aliases), decoy / excluded scope, expected
qualification statuses (including NOT_EVALUATED), seeded defects, abstention and injection markers.
Its cassette is a recorded model response; ``{{node:<ref>}}`` placeholders resolve to the
fixture's deterministic node ids, so cassettes stay readable and reproducible.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.evidence.domain.models import LocatorQuality
from src.wbs.intelligence.contracts.evidence import (
    CanonicalSourceRef,
    EvidenceManifest,
    InputClass,
    ManifestItem,
    ModelVisibleExcerpt,
)
from src.wbs.intelligence.contracts.qualification import (
    AvailabilityContext,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationStatus,
)
from src.wbs.intelligence.contracts.run import IntelligenceMode, RunOutcome
from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot

FIXTURE_VERSION = "wbs-golden-fixture/v1"
_NAMESPACE = UUID("6f7d1d2e-6c1f-4a8e-9b1e-2b3c4d5e6f70")  # fixed: fixture ids must be reproducible
_NODE_PLACEHOLDER = re.compile(r"\{\{node:([a-z0-9_]+)\}\}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FixtureNode(_Strict):
    ref: str = Field(pattern=r"^[a-z0-9_]+$")
    parent_ref: str | None = None
    code: str | None = None
    name: str
    kind: str | None = None
    control_level: str = "none"
    dictionary: dict[str, object] | None = None


class FixtureEvidence(_Strict):
    excerpt_id: str
    input_class: InputClass
    text: str


class ExpectedDimension(_Strict):
    status: QualificationStatus
    reason: NotEvaluatedReason | None = None


class GoldElement(_Strict):
    element_id: str
    aliases: tuple[str, ...] = Field(min_length=1)


class SeededDefect(_Strict):
    defect_id: str
    dimension: QualificationDimension
    node_refs: tuple[str, ...] = ()


class Expectations(_Strict):
    outcome: RunOutcome
    gold_scope: tuple[GoldElement, ...] = ()
    decoys: tuple[GoldElement, ...] = ()
    dimensions: dict[QualificationDimension, ExpectedDimension] = Field(default_factory=dict)
    seeded_defects: tuple[SeededDefect, ...] = ()
    injection_markers: tuple[str, ...] = ()


class GoldenFixture(_Strict):
    fixture_version: str = FIXTURE_VERSION
    fixture_id: str = Field(pattern=r"^GC-[A-Z]+-[A-Z0-9]+$")
    title: str
    archetype: str
    mode: IntelligenceMode
    profiles: tuple[str, ...] = ()  # "<profile_id>@<version>"
    target_nodes: tuple[FixtureNode, ...] = ()
    evidence: tuple[FixtureEvidence, ...]
    availability: AvailabilityContext
    expectations: Expectations
    cassette: str
    provenance: str  # where the content comes from: synthetic / licensed (never customer data)

    def node_id(self, ref: str) -> UUID:
        return uuid5(_NAMESPACE, f"{self.fixture_id}/node/{ref}")

    @property
    def tenant_id(self) -> UUID:
        return uuid5(_NAMESPACE, f"{self.fixture_id}/tenant")

    @property
    def project_id(self) -> UUID:
        return uuid5(_NAMESPACE, f"{self.fixture_id}/project")

    def snapshot(self) -> TargetSnapshot | None:
        if self.mode is IntelligenceMode.GENERATE and not self.target_nodes:
            return None
        orders: dict[str | None, int] = {}
        nodes = []
        for node in self.target_nodes:
            orders[node.parent_ref] = orders.get(node.parent_ref, 0) + 1
            nodes.append(SnapshotNode(
                node_id=self.node_id(node.ref), parent_id=None if node.parent_ref is None else self.node_id(node.parent_ref),
                sort_order=orders[node.parent_ref], code=node.code, name=node.name, decomposition_kind=node.kind,
                control_level=node.control_level, dictionary=node.dictionary))
        return TargetSnapshot(project_id=self.project_id, nodes=tuple(nodes))

    def manifest(self) -> EvidenceManifest:
        items = []
        for evidence in self.evidence:
            source = None
            if evidence.input_class is not InputClass.USER_CONTEXT:
                source = CanonicalSourceRef(
                    document_id=uuid5(_NAMESPACE, f"{self.fixture_id}/doc/{evidence.excerpt_id}"),
                    revision_id=uuid5(_NAMESPACE, f"{self.fixture_id}/rev/{evidence.excerpt_id}"),
                    blob_hash=hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(), page=1, char_start=0,
                    char_end=len(evidence.text), locator_quality=LocatorQuality.EXACT)
            items.append(ManifestItem(excerpt_id=evidence.excerpt_id, input_class=evidence.input_class,
                                      canonical_source=source,
                                      model_visible=ModelVisibleExcerpt.of(evidence.text, transform="none")))
        return EvidenceManifest(tenant_id=self.tenant_id, project_id=self.project_id, items=tuple(items))

    def render_cassette(self, raw: str) -> str:
        known = {node.ref for node in self.target_nodes}

        def _sub(match: re.Match[str]) -> str:
            ref = match.group(1)
            # unknown refs resolve too: a cassette may deliberately cite an invented node
            return str(self.node_id(ref)) if ref in known else str(uuid5(_NAMESPACE, f"invented/{ref}"))

        return _NODE_PLACEHOLDER.sub(_sub, raw)


class FixtureManifest(_Strict):
    manifest_version: str
    fixtures: tuple[str, ...]


def load_fixtures(root: Path) -> list[tuple[GoldenFixture, str]]:
    """All fixtures of ``root/manifest.yaml`` with their rendered cassettes, in manifest order."""
    manifest = FixtureManifest.model_validate(yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8")))
    loaded = []
    for fixture_id in manifest.fixtures:
        fixture = GoldenFixture.model_validate(
            json.loads((root / "fixtures" / f"{fixture_id}.json").read_text(encoding="utf-8")))
        if fixture.fixture_id != fixture_id:
            raise ValueError(f"{fixture_id}.json declares {fixture.fixture_id}")
        raw = (root / "cassettes" / fixture.cassette).read_text(encoding="utf-8")
        loaded.append((fixture, fixture.render_cassette(raw)))
    return loaded


__all__ = ["FIXTURE_VERSION", "GoldenFixture", "load_fixtures"]
