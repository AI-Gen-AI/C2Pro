"""WS-B offline replay: stored SolarMax N4 risks + N12 observations through the 1233a1b code path.

Zero LLM calls. The only boundary substituted is the persisted-clause repository
(an in-memory ``list_clauses_bound_to_revision``) - no DB session, no model.
Real code exercised: ``nodes._risk_contract_item`` (provenance gate), ``build_risk_signals``,
``load_trusted_risk_source_clause_ids``, ``evaluate_artifact_set`` (engine in low-budget,
no-LLM mode), ``build_trusted_state_candidate``, ProjectGraph ``health``,
``AlertGenerator.generate_risk_alerts``, ``AlertMapper.to_response``.

Inputs (skipped if absent): /home/aigenadmin/qa_evidence/solarmax-real-pdf-20261110/
Clause splitting is a replay stand-in for persisted clauses (heading regex on the PDF text).
Regression tests at the bottom (RED_A/B/C) were RED at 1233a1b and pass with the evidence-status fixes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest

EVID = Path("/home/aigenadmin/qa_evidence/solarmax-real-pdf-20261110")
RESULT = EVID / "live_claude_n4_n12_result_v1.json"
PDF = EVID / "solarmax_ex991_original.pdf"
pytestmark = pytest.mark.skipif(
    not (RESULT.exists() and PDF.exists()), reason="SolarMax evidence files unavailable"
)

TENANT = uuid5(NAMESPACE_URL, "wsb-replay/tenant")
PROJECT = uuid5(NAMESPACE_URL, "wsb-replay/project")
DOC = uuid5(NAMESPACE_URL, "wsb-replay/doc")
REV = uuid5(NAMESPACE_URL, "wsb-replay/rev")
# Risk indices whose quote does not carry the headline claim / is contradicted (WS-B matrix).
NOT_CARRIED = {2, 4, 13, 14}


def _pages() -> list[str]:
    import fitz  # PyMuPDF

    return [p.get_text() for p in fitz.open(str(PDF))]


@pytest.fixture(scope="module")
def stored() -> dict:
    return json.loads(RESULT.read_text())


@pytest.fixture(scope="module")
def text() -> str:
    return "\n".join(_pages())


def _split_clauses(text: str) -> dict[str, str]:
    """code -> clause text (heading to next heading), body only (after preamble, page 6)."""
    pages = _pages()
    body_start = len("\n".join(pages[:5])) + 1
    squashed_pages = [re.sub(r"\s+", " ", p) for p in pages]
    flat = " ".join(squashed_pages)
    start = len(" ".join(squashed_pages[:5])) + 1
    heads = []
    for m in re.finditer(r"(?<=[ .;:])(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+(?=[A-Z“(])", flat):
        if m.start() < start:
            continue
        before = flat[max(0, m.start() - 12) : m.start()]
        if re.search(r"(Sections?|and|to|with|in|under|of|by|,)\s*$", before):
            continue
        heads.append((m.start(), m.group(1)))
    clauses: dict[str, str] = {}
    for i, (pos, code) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(flat)
        clauses.setdefault(code, flat[pos:end])
    del body_start
    return clauses


class _Repo:
    def __init__(self, clauses):
        self._clauses = clauses

    async def list_clauses_bound_to_revision(self, tenant, document, revision):
        return self._clauses


def _source_clauses(text: str, codes: set[str]):
    from src.documents.domain.models import Clause

    split = _split_clauses(text)
    return [
        Clause(
            id=uuid5(NAMESPACE_URL, f"wsb-replay/clause/{c}"),
            project_id=PROJECT, tenant_id=TENANT, document_id=DOC,
            clause_code=c, clause_type=None, title=None,
            full_text=split[c], revision_id=REV,
        )
        for c in sorted(codes)
        if c in split
    ]


@pytest.fixture(scope="module")
def gated(stored, text):
    from src.analysis.adapters.graph.nodes import _risk_contract_item

    return [_risk_contract_item(r, text) for r in stored["n4"]["risks"]]


def _artifact(gated, confidence=None):
    from src.analysis.domain.contracts import DocumentArtifact

    return DocumentArtifact(
        document_id=str(DOC), document_revision_id=str(REV), doc_type="contract",
        document_category="LEGAL", extracted_risks=list(gated), confidence_score=confidence,
    )


def _code(risk) -> str:
    return risk.clause_ref.removeprefix("§").strip()


# ----------------------------------------------------------------- provenance gate
def test_provenance_gate_assigns_verified_to_all_15_including_not_carried(gated):
    statuses = [r.source_quote_status for r in gated]
    assert statuses == ["VERIFIED"] * 15  # location-only gate: no claim-level status exists
    assert {i for i in NOT_CARRIED} <= set(range(15))


def test_n12_observations_have_literal_quotes_but_feed_no_gate(stored, text):
    from src.analysis.domain.risk_provenance import classify_quote

    notes = stored["n12"]["notes"]
    quotes = re.findall(r"Source: “(.*?)”", notes, re.S)
    assert len(quotes) == 5 and stored["n12"]["status"] == "UNASSESSED"
    assert [classify_quote(q, text)[1] for q in quotes] == ["VERIFIED"] * 5


# ----------------------------------------------------------------- bridge / signals
def test_live_n8_bridge_scores_all_15_as_whole_document_signals(gated):
    from src.analysis.adapters.graph.risk_signal_bridge import build_risk_signals

    res = build_risk_signals(
        [r.model_dump(mode="python") for r in gated], clause_id="doc-surrogate",
        document_id=str(DOC), document_revision_id=str(REV),
    )
    assert len(res.signals) == 15 and res.dropped_count == 0
    assert all(s.confidence == 0.7 for s in res.signals)  # fixed fallback, not measured
    assert all(s.source == "llm" for s in res.signals)


@pytest.mark.asyncio
async def test_trusted_projectgraph_binding_per_risk(gated, text):
    from src.analysis.adapters.persistence.risk_source_clause_binding import (
        load_trusted_risk_source_clause_ids,
    )

    art = _artifact(gated)
    clauses = _source_clauses(text, {_code(r) for r in gated})
    mapping = await load_trusted_risk_source_clause_ids(
        None, tenant_id=TENANT, project_id=PROJECT, artifacts=[art], repository=_Repo(clauses)
    )
    from src.analysis.adapters.graph.review_source_references import risk_quote_source_key

    bound = {
        i for i, r in enumerate(gated)
        if risk_quote_source_key(DOC, REV, r.clause_ref, r.source_quote) in mapping
    }
    print("BOUND_RISK_INDICES", sorted(bound), "CLAUSES_RESOLVED", [c.clause_code for c in clauses])
    # NB: a splitter-built 12.1.5 clause runs to 12.2 so it contains the unnumbered closing
    # paragraph of 12.1 (p84): #13 therefore binds. Whether that paragraph belongs to 12.1.5 is
    # a legal-structure question (UNVERIFIED).
    assert bound  # at least some resolve


@pytest.mark.asyncio
async def test_coherence_and_health_with_partial_binding(gated, text):
    from uuid import UUID as _U
    from src.analysis.adapters.graph.project_graph import evaluate_artifact_set, health
    from src.analysis.adapters.persistence.risk_source_clause_binding import (
        load_trusted_risk_source_clause_ids,
    )
    from src.project_state.application.trusted_artifact_projector import (
        TrustedRevisionBundle, build_trusted_state_candidate,
    )

    art = _artifact(gated)
    clauses = _source_clauses(text, {_code(r) for r in gated})
    mapping = await load_trusted_risk_source_clause_ids(
        None, tenant_id=TENANT, project_id=PROJECT, artifacts=[art], repository=_Repo(clauses)
    )
    ev = await evaluate_artifact_set(
        [art], project_id=PROJECT, tenant_id=TENANT, llm_on=False,
        risk_source_clause_ids=mapping, risk_source_binding_status="OK",
    )
    cand = build_trusted_state_candidate(
        project_id=PROJECT, tenant_id=TENANT,
        bundles=[TrustedRevisionBundle(art, tuple(clauses), "trusted", "active")],
    )
    print("COHERENCE", ev.summary.overall_score, ev.engine_result.score_reason,
          "signals", ev.summary.signal_count, "excluded", getattr(ev.summary, "excluded_risk_count", None))
    print("PROJECTOR", cand.diagnostics)
    h = health({
        "project_id": PROJECT, "tenant_id": TENANT, "artifacts": [art],
        "coherence_result": ev.summary, "canonical_project_state": cand.state, "node_results": [],
    })
    dims = {d["dimension"]: d for d in h["health_result"]["dimensions"]}
    print("HEALTH", h["health_result"]["composite_score"],
          {k: (v["score"], v.get("band")) for k, v in dims.items()})
    assert cand.diagnostics.source_bound_risks + cand.diagnostics.rejected_unverified_risks == 15


# ----------------------------------------------------------------- alerts (a)
def _alert_rows(gated, text, bound_refs: bool):
    from datetime import UTC, datetime
    from src.alerts.application.mappers.alert_mapper import AlertMapper
    from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
    from src.alerts.domain.models import Alert
    from src.analysis.adapters.graph.review_source_references import (
        bind_risk_alert_source_references, grounded_review_source_references,
    )
    from src.coherence.alert_generator import AlertGenerator

    risks = [r.model_dump(mode="json") for r in gated]
    if bound_refs:
        clauses = _source_clauses(text, {_code(r) for r in gated})
        refs = grounded_review_source_references(
            tenant_id=TENANT, project_id=PROJECT, document_id=DOC, revision_id=REV,
            clause_codes={_code(r) for r in gated}, persisted_clauses=clauses,
        )
        risks = bind_risk_alert_source_references(risks, refs)
    dtos = AlertGenerator(project_id=PROJECT, analysis_id=uuid4()).generate_risk_alerts(risks)
    out = []
    for dto in dtos:
        alert = Alert(
            id=uuid4(), project_id=PROJECT, severity=AlertSeverity(dto.severity.value),
            category=dto.category or "OTHER", status=AlertStatus.PENDING if hasattr(AlertStatus, "PENDING") else list(AlertStatus)[0],
            approval_status=list(ApprovalStatus)[0], rule_id=dto.rule_id, title=dto.title,
            description=dto.description, alert_metadata=dto.alert_metadata,
            source_clause_id=dto.source_clause_id, created_at=datetime.now(UTC),
        )
        out.append((dto, AlertMapper.to_response(alert, TENANT)))
    return out


def test_alert_per_risk_user_visible_fields(gated, text):
    rows = _alert_rows(gated, text, bound_refs=True)
    assert len(rows) == 15  # an alert is emitted for every risk
    for i, (dto, resp) in enumerate(rows):
        fields = set(resp.model_dump().keys())
        print("ALERT", i, _code(gated[i]), resp.severity, "clause", resp.source_clause_id is not None,
              "prov", dto.alert_metadata["source_provenance"]["verification_status"],
              "evidence", resp.detection_evidence is not None)
        assert not any("verif" in f or "provenance" in f or "quote_status" in f for f in fields)


def _tampered(stored, text, index=3):
    from src.analysis.adapters.graph.nodes import _risk_contract_item

    raw = dict(stored["n4"]["risks"][index])
    raw["source_quote"] = "Contractor shall pay a fabricated penalty of one million dollars per day."
    raw["source_text_snippet"] = raw["source_quote"]
    return _risk_contract_item(raw, text)


@pytest.mark.asyncio
async def test_non_verified_risk_is_withheld_from_scored_paths_GREEN(stored, text, gated):
    """Pins the working part of the gate: an invented quote is never scored/projected."""
    from src.analysis.adapters.graph.risk_signal_bridge import build_risk_signals
    from src.project_state.application.trusted_artifact_projector import (
        TrustedRevisionBundle, build_trusted_state_candidate,
    )

    bad = _tampered(stored, text)
    assert bad.source_quote_status == "NOT_FOUND_IN_DOCUMENT" and bad.source_quote is None
    res = build_risk_signals([bad.model_dump(mode="python")], clause_id="x")
    assert res.signals == () and res.dropped_reasons == {"unverified_quote": 1}
    art = _artifact([bad])
    clauses = _source_clauses(text, {_code(bad)})
    cand = build_trusted_state_candidate(
        project_id=PROJECT, tenant_id=TENANT,
        bundles=[TrustedRevisionBundle(art, tuple(clauses), "trusted", "active")],
    )
    assert cand.diagnostics.rejected_unverified_risks == 1 and cand.state.risks == []


def test_blank_pages_9_21_55_do_not_touch_any_gate_input(stored, text):
    pages = _pages()
    blank = [i + 1 for i, p in enumerate(pages) if not p.strip()]
    assert blank == [9, 21, 55]
    squashed = [re.sub(r"\s+", " ", p) for p in pages]
    quote_pages = set()
    for r in stored["n4"]["risks"]:
        q = re.sub(r"\s+", " ", r["source_quote"]).strip()
        quote_pages |= {i + 1 for i, p in enumerate(squashed) if q in p}
    assert quote_pages and not (quote_pages & {9, 21, 55})
    # classify_quote / bridge / projector take (quote, text) only: no page number or
    # completeness flag exists in their signatures, so blank pages are invisible to them.
    import inspect
    from src.analysis.domain.risk_provenance import classify_quote

    assert "page" not in " ".join(inspect.signature(classify_quote).parameters)


# ================================================================== RED tests
@pytest.mark.asyncio
async def test_RED_A_alert_for_invented_quote_looks_identical_to_verified_alert(stored, text, gated):
    """User-visible API fields must differ between a VERIFIED-quote alert and a NOT_FOUND-quote alert.

    Today: bind_risk_alert_source_references() keys on clause_ref only (review_source_references.py:
    ~164-192) so the invented-quote risk also gets source_locator_status=VERIFIED, a source_clause_id
    and a detection_evidence locator; AlertResponse (alerts/application/dtos.py:129-146) has no
    evidence-status field and the UI (AlertReviewCenter.tsx:352-436) renders none.
    """
    ok, bad = gated[3], _tampered(stored, text)
    rows = _alert_rows([ok, bad], text, bound_refs=True)
    drop = {"id", "message", "created_at", "sla_due_at"}
    a, b = (r.model_dump(mode="json", exclude=drop) for _, r in rows)
    assert a != b, "alert for an unverified quote is indistinguishable in the API response"


def test_RED_B_risk_health_unqualified_when_n12_not_assessed(gated, text):
    """N12 UNASSESSED => artifact.confidence_score is None. The Risk dimension must carry a
    qualification (missing_data) instead of a bare number, since 4/15 quotes do not carry the claim.

    Today: health() -> score_risk_dimension(..., extraction_quality=None) skips the quality floor
    (health/application/risk_scorer.py:47) and emits score with default confidence 0.7, no missing_data.
    """
    from src.analysis.adapters.graph.project_graph import health
    from src.project_state.application.trusted_artifact_projector import (
        TrustedRevisionBundle, build_trusted_state_candidate,
    )

    art = _artifact(gated, confidence=None)
    cand = build_trusted_state_candidate(
        project_id=PROJECT, tenant_id=TENANT,
        bundles=[TrustedRevisionBundle(art, tuple(_source_clauses(text, {_code(r) for r in gated})),
                                       "trusted", "active")],
    )
    h = health({"project_id": PROJECT, "tenant_id": TENANT, "artifacts": [art],
                "canonical_project_state": cand.state, "node_results": []})
    risk = next(d for d in h["health_result"]["dimensions"] if d["dimension"] == "risk")
    assert risk["score"] is not None  # documents the current numeric output ...
    assert risk["missing_data"], "numeric risk health with N12 UNASSESSED carries no qualification"


@pytest.mark.asyncio
async def test_RED_C_all_withheld_risks_yield_clean_green_risk_health(stored, text, gated):
    """If every risk is withheld (e.g. none bound/verified) Risk health must not be a clean 90/95.

    Today: canonical state with 0 risks + artifacts present => score_risk_dimension's `not risks`
    branch returns _CLEAN_ASSESSMENT_SCORE 90 with a VERIFIED 'risk-assessment-clean' evidence
    (health/application/risk_scorer.py:52-67), while 15 proposals were rejected.
    """
    from src.analysis.adapters.graph.project_graph import health
    from src.project_state.application.trusted_artifact_projector import (
        TrustedRevisionBundle, build_trusted_state_candidate,
    )

    art = _artifact(gated, confidence=0.9)
    cand = build_trusted_state_candidate(  # no physical clauses => every risk rejected
        project_id=PROJECT, tenant_id=TENANT,
        bundles=[TrustedRevisionBundle(art, (), "trusted", "active")],
    )
    assert cand.diagnostics.rejected_unverified_risks == 15 and cand.state.risks == []
    h = health({"project_id": PROJECT, "tenant_id": TENANT, "artifacts": [art],
                "canonical_project_state": cand.state, "node_results": []})
    risk = next(d for d in h["health_result"]["dimensions"] if d["dimension"] == "risk")
    assert risk["score"] is None or risk["score"] < 90, f"clean risk health shown: {risk['score']}"
