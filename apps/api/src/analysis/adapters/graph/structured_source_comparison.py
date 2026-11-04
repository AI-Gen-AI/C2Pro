"""Source-bound provisional EPC comparisons: canonical XLSX rows vs verified N4 quotes.

No LLM calls, unapproved baseline promotion, scored conflicts, or cross-tenant reads.
All findings have both original revision-bound sources and row/quote locators.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from src.analysis.domain.contracts import DocumentArtifact
from src.coherence.cross_document.comparators import (
    budget_exceeds_contract,
    schedule_overruns_deadline,
)
from src.coherence.cross_document.findings import CrossDocFinding, CrossDocProvisional
from src.coherence.cross_document.inputs import (
    BASIS_SOURCE_OBSERVED,
    DATE_KIND_CONTRACT_COMPLETION,
    DATE_KIND_SCHEDULE_FINISH,
    DatedSource,
    ProjectCrossDocInputs,
)

_ISO = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_CURRENCY = re.compile(r"(EUR|USD|GBP|€|\$|£)\s*(\d[\d,.]*)", re.IGNORECASE)
_COMPLETION = re.compile(
    r"(?:contractual\s+completion|completion\s+(?:date|deadline)|"
    r"fecha\s+(?:límite\s+de\s+)?(?:finalización|terminación)|"
    r"shall\s+(?:achieve|reach)\s+completion|complete\s+(?:the\s+works|commissioning))",
    re.IGNORECASE,
)
_PRICE = re.compile(r"(?:contract\s+(?:price|sum|value)|total\s+contract\s+value|"
    r"precio\s+del\s+contrato|importe\s+del\s+contrato|valor\s+del\s+contrato)", re.IGNORECASE)
_SPEC_MILESTONES = ("factory acceptance", "site acceptance", "commissioning", "performance test",
                    "pruebas de aceptación en fábrica", "puesta en marcha", "pruebas de rendimiento")
_CODES = {"€": "EUR", "$": "USD", "£": "GBP", "EURO": "EUR", "EUROS": "EUR" }
_DATE_ES = re.compile(
    r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(20\d{2})\b",
    re.IGNORECASE,
)
_MONTH_ES = {month: n for n, month in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"), 1)}
_MONTH_ES["setiembre"] = 9
_CURRENCY_AFTER = re.compile(r"(\d[\d,.]*)\s*(euros?|EUR|USD|GBP|€|\$|£)\b", re.IGNORECASE)


def _source_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Accept only a content-hash-valid row from an immutable canonical revision."""
    family = str(row.get("family") or "")
    raw = row.get("payload")
    if family not in {"budget", "schedule"} or not isinstance(raw, dict):
        return None
    doc, rev, loc = (str(row.get(k) or "") for k in ("document_id", "revision_id", "source_locator"))
    blob, checksum = (str(row.get(k) or "") for k in ("blob_hash", "unit_sha256"))
    if not all((doc, rev, loc)) or not re.fullmatch(r"[0-9a-f]{64}", blob):
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        return None
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != checksum:
        return None
    if raw.get("source_locator") != loc:
        return None
    return {
        "family": family,
        "document_id": doc,
        "revision_id": rev,
        "source_locator": loc,
        "blob_sha256": blob,
        "unit_sha256": checksum,
        "payload": raw,
    }


def _quoted_risks(artifacts: list[DocumentArtifact], *, technical: bool = False) -> list[dict[str, Any]]:
    result = []
    for artifact in artifacts:
        doc_type = artifact.doc_type.lower()
        if technical and doc_type not in {"technical", "technical_spec", "technical_specification", "specification"}:
            continue
        if not technical and doc_type != "contract":
            continue
        if not artifact.document_revision_id:
            continue
        for risk in artifact.extracted_risks:
            quote = risk.source_quote
            if risk.source_quote_status != "VERIFIED" or not quote:
                continue
            result.append({
                "document_id": artifact.document_id,
                "revision_id": artifact.document_revision_id,
                "source_locator": risk.clause_ref or "verified-quote:" + hashlib.sha256(quote.encode()).hexdigest()[:16],
                "source_quote": quote,
                "source_quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
            })
    return result


def _date_from_quote(quote: str) -> str | None:
    dates = set(_ISO.findall(quote))
    for day, month, year in _DATE_ES.findall(quote):
        try:
            dates.add(date(int(year), _MONTH_ES[month.lower()], int(day)).isoformat())
        except ValueError:
            return None
    if len(dates) != 1:
        return None
    value = next(iter(dates))
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _row_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?", text):
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _amount(text: str) -> tuple[float, str] | None:
    matches = [(curr, val) for curr, val in _CURRENCY.findall(text)]
    matches += [(curr, val) for val, curr in _CURRENCY_AFTER.findall(text)]
    if len(matches) != 1:
        return None
    currency, amount = matches[0]
    amount = amount.strip(".,")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", amount):
        decimal = amount.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", amount):
        decimal = amount.replace(",", "")
    elif re.fullmatch(r"\d+(?:[,.]\d{1,2})?", amount):
        decimal = amount.replace(",", ".")
    else:
        return None  # Ambiguous number/decimal convention: do not compare.
    try:
        return float(Decimal(decimal)), _CODES.get(currency.upper(), currency.upper())
    except InvalidOperation:
        return None


def _finding(rule: str, summary: str, contract: dict[str, Any], row: dict[str, Any],
             *, values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": rule,
        "state": "PROVISIONAL",
        "reason": "SOURCE_OBSERVED_NOT_APPROVED_BASELINE",
        "summary": summary,
        "compared_values": dict(values),
        "sources": [
            {**contract, "role": "verified_document_quote"},
            {
                "family": row["family"], "document_id": row["document_id"],
                "revision_id": row["revision_id"], "source_locator": row["source_locator"],
                "blob_sha256": row["blob_sha256"], "unit_sha256": row["unit_sha256"],
                "role": "original_source_row",
            },
        ],
        "scored": False,
        "requires_human_review": True,
    }


def compare_original_source_rows(
    artifacts: list[DocumentArtifact],
    units: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return explicit provisional deviations, never canonical Coherence Score signals."""
    rows = [good for unit in units if (good := _source_row(unit)) is not None]
    schedule = [row for row in rows if row["family"] == "schedule" and row["payload"].get("kind") == "activity"]
    budget = [row for row in rows if row["family"] == "budget" and row["payload"].get("kind") == "declared_total"]
    findings: list[dict[str, Any]] = []
    reasons: list[str] = []
    contract_quotes = _quoted_risks(artifacts)

    deadlines = [
        (src, parsed) for src in contract_quotes
        if _COMPLETION.search(src["source_quote"])
        if (parsed := _date_from_quote(src["source_quote"])) is not None
    ]
    if schedule and len({d for _, d in deadlines}) == 1 and deadlines:
        schedule_dates = [(row, _row_date(row["payload"].get("end_date"))) for row in schedule]
        if all(dt is not None for _, dt in schedule_dates):
            finish_row, finish = max(schedule_dates, key=lambda pair: pair[1] or "")
            contract, deadline = deadlines[0]
            comparison = schedule_overruns_deadline(ProjectCrossDocInputs(
                contract_completion=DatedSource(
                    kind=DATE_KIND_CONTRACT_COMPLETION, value=deadline,
                    document_id=contract["document_id"], revision_id=contract["revision_id"],
                    locator=contract["source_locator"],
                ),
                schedule_finish=DatedSource(
                    kind=DATE_KIND_SCHEDULE_FINISH, value=finish,
                    document_id=finish_row["document_id"], revision_id=finish_row["revision_id"],
                    locator=finish_row["source_locator"], basis=BASIS_SOURCE_OBSERVED,
                ),
            ))
            if isinstance(comparison, CrossDocProvisional):
                findings.append(_finding(comparison.rule_id, comparison.summary, contract, finish_row,
                                         values={"contract_deadline": deadline, "planned_finish": finish,
                                                 "overrun_days": int(comparison.delta)}))
        else:
            reasons.append("SCHEDULE_DATE_UNASSESSED")
    else:
        reasons.append("CONTRACT_COMPLETION_OR_SCHEDULE_NOT_UNAMBIGUOUS")

    contract_prices = [
        (src, amount) for src in contract_quotes if _PRICE.search(src["source_quote"])
        if (amount := _amount(src["source_quote"])) is not None
    ]
    if len(budget) == 1 and len({val for _, val in contract_prices}) == 1 and contract_prices:
        budget_row = budget[0]
        payload = budget_row["payload"]
        try:
            total = float(Decimal(str(payload["total"])))
        except (InvalidOperation, ValueError, TypeError, KeyError):
            total = None
        currency = str(payload.get("currency") or "").upper().strip()
        contract, (price, contract_currency) = contract_prices[0]
        if total is not None and currency and currency == contract_currency:
            finding = budget_exceeds_contract(ProjectCrossDocInputs(
                contract_total=price, budget_total=total,
                contract_currencies=frozenset({contract_currency}),
                budget_currencies=frozenset({currency}),
            ))
            if isinstance(finding, CrossDocFinding):
                findings.append(_finding(finding.rule_id, finding.summary, contract, budget_row,
                                         values={"contract_price": price, "budget_declared_total": total,
                                                 "currency": currency, "difference": total - price}))
        else:
            reasons.append("BUDGET_CURRENCY_OR_TOTAL_UNASSESSED")
    else:
        reasons.append("CONTRACT_PRICE_OR_BUDGET_TOTAL_NOT_UNAMBIGUOUS")

    # Specification-specific milestone conflicts: require a verified quote,
    # identical named activity in a source row and an unambiguous explicit date.
    specs = _quoted_risks(artifacts, technical=True)
    for spec in specs:
        quote = spec["source_quote"].lower()
        deadline = _date_from_quote(spec["source_quote"])
        if deadline is None or not any(mark in quote for mark in
            ("no later than", " by ", "a más tardar", "antes del", "no después del")):
            continue
        names = [name for name in _SPEC_MILESTONES if name in quote]
        if len(names) != 1:
            continue
        for row in schedule:
            task = str(row["payload"].get("task") or "").lower()
            finish = _row_date(row["payload"].get("end_date"))
            if names[0] not in task or finish is None or finish <= deadline:
                continue
            findings.append(_finding(
                "SPEC-MILESTONE-VS-SCHEDULE",
                names[0] + " planned for " + finish + " after specification deadline " + deadline,
                spec, row,
                values={"technical_deadline": deadline, "planned_finish": finish,
                        "overrun_days": (date.fromisoformat(finish) - date.fromisoformat(deadline)).days},
            ))
    return {
        "findings": findings,
        "not_assessed_reasons": sorted(set(reasons)),
        "source_rows_verified": len(rows),
        "scoring_policy": "provisional_only_not_scored",
    }
