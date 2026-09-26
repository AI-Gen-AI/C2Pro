"""Shared category inference utilities for coherence rules and graph nodes."""

from __future__ import annotations

from ..models import Clause, CoherenceCategory

# Bilingual (English + Spanish) keyword sets. c2pro's documents are predominantly
# Spanish, but the original sets were English-only, so Spanish clauses defaulted to
# SCOPE in the deterministic path. `infer_category` picks the MAX-scoring category,
# so an administrative clause dense with legal terms resolves to LEGAL even if it
# incidentally contains one technical word — that max-score design is the honesty
# guard that keeps TECHNICAL from being fabricated on non-technical contracts.
CATEGORY_KEYWORDS: dict[CoherenceCategory, list[str]] = {
    "BUDGET": [
        # English
        "budget", "cost", "price", "amount", "payment", "invoice", "expense",
        "contingency", "retention", "advance", "total", "unit_price", "line_total",
        "planned", "current", "variance", "overrun", "financial",
        # Spanish
        "presupuesto", "coste", "costo", "precio", "importe", "pago", "abono",
        "factura", "gasto", "contingencia", "retención", "anticipo", "euros",
        "certificación", "presupuestari",
    ],
    "TIME": [
        # English
        "schedule", "deadline", "milestone", "date", "duration", "start_date",
        "end_date", "timeline", "delay", "overdue", "predecessor", "task",
        "calendar", "days", "weeks", "months",
        # Spanish
        "plazo", "cronograma", "calendario", "fecha", "duración", "hito",
        "días", "semanas", "meses", "demora", "retraso", "prórroga", "entrega",
    ],
    "LEGAL": [
        # English
        "contract", "agreement", "clause", "term", "condition", "warranty",
        "liability", "penalty", "notice", "insurance", "indemnity", "review",
        "expiry", "termination", "dispute", "arbitration",
        # Spanish
        "contrato", "convenio", "cláusula", "clausula", "condición", "garantía",
        "responsabilidad", "penalización", "penalidad", "seguro", "indemnización",
        "resolución", "rescisión", "litigio", "jurisdicción", "real decreto",
        "adjudicación", "pliego", "administrativ", "licitación", "estipulaci",
    ],
    "SCOPE": [
        # English
        "scope", "deliverable", "requirement", "specification", "work",
        "objective", "inclusion", "exclusion", "change", "amendment",
        # Spanish
        "alcance", "objeto", "prestación", "obra", "obras", "entregable",
        "requisito", "inclusión", "exclusión", "modificación", "suministro",
    ],
    "TECHNICAL": [
        # English
        "bom", "material", "specification", "standard", "iso", "astm",
        "lead_time", "technical", "engineering", "design", "component",
        # Spanish — concrete measurement/equipment terms that appear in an actual
        # technical specification, NOT the "prescripciones técnicas" reference
        # wording an administrative contract uses to point at a separate pliego.
        "especificación técnica", "norma une", "potencia", "caudal", "diámetro",
        "válvula", "tubería", "montaje", "electromecánic", "tensión nominal",
        "voltaje", "amperaje", "ingeniería",
    ],
    "QUALITY": [
        # English
        "quality", "inspection", "test", "compliance", "standard",
        "acceptance", "defect", "tolerance", "frequency",
        # Spanish
        "calidad", "inspección", "ensayo", "prueba", "cumplimiento",
        "aceptación", "recepción", "defecto", "tolerancia", "control de calidad",
    ],
}


def infer_category(clause: Clause) -> CoherenceCategory:
    """
    Infer the coherence category from clause text content only.

    Uses keyword matching on the clause text to determine the most likely
    category. Data key names are intentionally excluded — after extraction,
    every clause has schema field names (specification, standard, material…)
    as keys regardless of whether those fields apply, which would corrupt
    scores if key names were included in the match target.

    Returns "SCOPE" as default if no strong match.
    """
    combined = clause.text.lower() if clause.text else ""

    scores: dict[CoherenceCategory, int] = dict.fromkeys(CATEGORY_KEYWORDS, 0)

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[category] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return "SCOPE"

    for cat, score in scores.items():
        if score == max_score:
            return cat

    return "SCOPE"
