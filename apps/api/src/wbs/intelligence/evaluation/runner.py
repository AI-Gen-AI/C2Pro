"""Cassette runner: replay recorded model responses through the real validator, then score.

No model is called. CI replays the committed cassettes; a future live mode (PC-2b.4/5) records new
cassettes under a budget cap and runs the same deterministic scorers.
"""

from __future__ import annotations

from pathlib import Path

from src.wbs.intelligence.contracts.run import RunScope
from src.wbs.intelligence.evaluation.fixtures import GoldenFixture, load_fixtures
from src.wbs.intelligence.evaluation.scoring import FixtureScore, score_fixture
from src.wbs.intelligence.profiles.catalog import ProfileCatalog, default_catalog
from src.wbs.intelligence.validation.output_validator import (
    ValidatedOutput,
    ValidationContext,
    validate_model_output,
)


def context_for(fixture: GoldenFixture, catalog: ProfileCatalog) -> ValidationContext:
    pins = []
    for ref in fixture.profiles:
        profile_id, _, version = ref.partition("@")
        pins.append(catalog.get(profile_id, version).pin())
    return ValidationContext(
        scope=RunScope(tenant_id=fixture.tenant_id, project_id=fixture.project_id), target=fixture.snapshot(),
        manifest=fixture.manifest(), profiles=catalog.resolve(pins), availability=fixture.availability)


def run_fixture(fixture: GoldenFixture, raw: str, catalog: ProfileCatalog | None = None) -> tuple[ValidatedOutput, FixtureScore]:
    catalog = catalog or default_catalog()
    ctx = context_for(fixture, catalog)
    output = validate_model_output(raw, ctx)
    return output, score_fixture(fixture, output, ctx.profiles.terms_by_namespace())


def run_all(root: Path, catalog: ProfileCatalog | None = None) -> list[FixtureScore]:
    return [run_fixture(fixture, raw, catalog)[1] for fixture, raw in load_fixtures(root)]


__all__ = ["context_for", "run_all", "run_fixture"]
