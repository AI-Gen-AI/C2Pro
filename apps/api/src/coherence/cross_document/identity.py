"""
Project-identity consistency comparator (SCOPE cross-reference, ADR-023).

Detects a location/name discrepancy between the project's identity (its name) and the
contract text. Golden pattern LOC-MISMATCH: project name "LAV La Roda-Pobla de Lena" vs
contract "La Robla-Pola de Lena" — the signal is a name token that is SIMILAR-but-different
from a contract token (a typo/mislabel), not merely absent (an absent token may just be a
qualifier the contract omits). Deterministic; emits a SCOPE ``FindingSignal``.

Refers to Suite ID: TS-UD-COH-IDENTITY-001.
"""
from __future__ import annotations

import difflib
import re

from src.coherence.models import FindingSignal

RULE_PROJECT_IDENTITY_MISMATCH = "DET-CRS-IDMISMATCH"

# A token close enough to be the SAME place yet different enough to be a typo/mislabel.
# Tuned so "Roda"↔"Robla" (ratio ~0.67) flags while unrelated words do not.
_SIMILARITY_CUTOFF = 0.6
# Place names are Title-Case proper nouns (capital + lowercase). Matching only these
# excludes common lowercase words ("toda") and ALL-CAPS boilerplate ("CONTRATO"), which
# otherwise produce spurious fuzzy matches.
_TOKEN_RE = re.compile(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}")

# Common project/contract vocabulary that is NOT place-identity (so it never drives a match).
_STOPWORDS = frozenset(
    {
        # ES
        "proyecto", "proyectos", "obra", "obras", "contrato", "contratos", "tipo", "objeto",
        "presente", "ejecucion", "construccion", "constructivo", "sistema", "sistemas",
        "instalacion", "instalaciones", "suministro", "montaje", "lote", "fase", "fases",
        "linea", "para", "segun", "sobre", "entre", "desde", "hasta", "conforme", "anexo",
        "clausula", "condiciones", "generales", "particulares", "empresa", "cliente",
        "contratista", "trabajos", "servicio", "servicios", "equipos", "material", "materiales",
        # EN
        "project", "projects", "contract", "works", "scope", "supply", "installation",
        "system", "systems", "phase", "line", "type", "object", "annex", "clause",
        "general", "particular", "client", "contractor", "company", "services", "equipment",
        # Domain qualifiers that recur across unrelated projects
        "rail", "electrical", "civil", "solar", "plant", "substation",
    }
)


def _identity_tokens(text: str) -> list[str]:
    """Significant place/identity tokens: length >= 4, not common contract vocabulary."""
    return [tok for tok in _TOKEN_RE.findall(text) if tok.lower() not in _STOPWORDS]


def project_identity_mismatch(project_name: str, contract_text: str) -> FindingSignal | None:
    """Flag a location/name token in the project name that is similar-but-different in the contract.

    Returns None when the project name is fully consistent with the contract (every significant
    token either appears verbatim or has no near-match — i.e. no typo/mislabel signal).
    """
    if not project_name or not contract_text:
        return None

    contract_lower = {tok.lower() for tok in _identity_tokens(contract_text)}
    if not contract_lower:
        return None

    for token in _identity_tokens(project_name):
        low = token.lower()
        if low in contract_lower:
            continue  # exact match → consistent
        close = difflib.get_close_matches(low, contract_lower, n=1, cutoff=_SIMILARITY_CUTOFF)
        # A typo/mislabel preserves the start of the word ("Roda"↔"Robla"); a genuinely
        # different word diverges at the prefix ("Bioenergia" vs "Agroenergia"). Requiring a
        # shared 2-char prefix keeps real discrepancies and drops compound-word false positives.
        if close and close[0] != low and close[0][:2] == low[:2]:
            return FindingSignal(
                rule_id=RULE_PROJECT_IDENTITY_MISMATCH,
                clause_id="project-identity",
                source="deterministic",
                impact_score=0.6,
                confidence=0.7,
                severity="high",
                category="SCOPE",
                evidence_summary=(
                    f"Project identity mismatch: the project name references '{token}' but the "
                    f"contract references '{close[0]}' — a location/name discrepancy requiring review."
                ),
                quote=f"name: {project_name[:70]} | contract: '{close[0]}'",
                raw_data={"project_token": token, "contract_token": close[0]},
            )
    return None


__all__ = ["RULE_PROJECT_IDENTITY_MISMATCH", "project_identity_mismatch"]
