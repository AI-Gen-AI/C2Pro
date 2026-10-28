"""Per-language term tables for deterministic contract-clause reading (data only, no logic).

Matching lives in ``contract_clause_reader``; this module is the only place that lists words.

* Terms are lowercase and **accent-folded** (``garantía`` is written ``garantia``); the reader folds
  the clause text the same way, so accents and case never matter.
* A trailing ``*`` marks a word **prefix** (``penaliz*`` matches ``penalización`` and ``penalizará``).
  A term without it must match a whole word or phrase (``works`` does not match ``frameworks``,
  ``cap`` does not match ``capital``).
* Languages are merged at match time: a clause in either language, or a mix, is read the same way.
  To support another language, add one key to each table.
"""

from __future__ import annotations

from collections.abc import Mapping

Terms = Mapping[str, tuple[str, ...]]  # language code -> terms

# First match wins, in this order (the order the English-only classifier already used).
CLAUSE_TYPE_ORDER: tuple[str, ...] = ("PENALTY", "PAYMENT", "WARRANTY", "SCOPE", "DELIVERY")

CLAUSE_TYPE_TERMS: Mapping[str, Terms] = {
    "PENALTY": {
        "en": ("penalt*", "penalis*", "liquidated damages", "delay*"),
        "es": (
            "penaliz*",
            "penalidad*",
            "clausula penal",
            "multa*",
            "sancion*",
            "demora*",
            "retras*",
            "danos y perjuicios liquidados",
        ),
    },
    "PAYMENT": {
        "en": (
            "payment*",
            "prepayment*",
            "repayment*",
            "overpayment*",
            "underpayment*",
            "nonpayment*",
            "downpayment*",
            "invoice*",
            "certified",
        ),
        "es": ("pago*", "pagar*", "pagad*", "certificacion*", "factura*", "abon*"),
    },
    "WARRANTY": {
        "en": ("warrant*", "defect*", "liabilit*"),
        "es": ("garanti*", "defecto*", "vicios ocultos", "responsabilidad*"),
    },
    "SCOPE": {
        "en": ("scope*", "includes", "works", "worksite*", "deliverable*"),
        "es": ("alcance*", "objeto*", "obra*", "entregable*"),
    },
    "DELIVERY": {
        "en": ("milestone*", "deadline*", "completion*", "schedule*", "reschedul*"),
        "es": ("plazo*", "hito*", "entrega*", "cronograma*", "finalizacion"),
    },
}

# Words that tell which role a percentage plays in a penalty clause. Both roles are read inside ONE
# sentence that itself names a penalty (a PENALTY term above). A term claims only the nearest
# percentage: a DAILY term may sit before or after its number ("0,1% diario", "tasa diaria del 0,1%"),
# a CAP term only before it ("tope del 10%", "capped at 10%"). A percentage with no term, or a tie, has
# no role: nothing is guessed. "limited" is deliberately NOT a cap term: it marks a liability limit.
PERCENT_ROLE_TERMS: Mapping[str, Terms] = {
    "DAILY": {
        "en": ("per day", "per calendar day", "per working day", "each day", "a day", "daily"),
        "es": (
            "diario*",
            "diaria*",
            "por dia",
            "por cada dia",
            "cada dia",
            "al dia",
            "por dia natural",
            "dia natural",
        ),
    },
    "CAP": {
        "en": (
            "cap",
            "capped",
            "maximum",
            "ceiling",
            "limit",
            "limits",
            "not exceed*",
            "not to exceed",
            "no more than",
            "at most",
            "up to",
        ),
        "es": (
            "tope*",
            "maximo*",
            "maxima*",
            "limite*",
            "techo",
            "no excedera*",
            "no superara*",
            "no podra exceder*",
            "no podra superar*",
            "sin exceder*",
            "en ningun caso",
            "hasta un",
            "hasta el",
        ),
    },
}

# Words that mark a number as a percentage when it is not followed by '%' (whole words).
PERCENT_WORDS: tuple[str, ...] = ("por ciento", "por cien", "per cent", "percent", "pct")

# How many characters on each side of a percentage are searched for a role term.
PERCENT_ROLE_WINDOW = 48
