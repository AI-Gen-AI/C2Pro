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
            "no podran exceder*",
            "no podran superar*",
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

# Percentage words that also start a quantity ("15 por 100 metros", "2 por 100.000 habitantes"): read as
# a percentage only at the end of the text or before punctuation, or when the next word is one of these
# ("0,2 por 100 del precio", "0,2 por 100 diario").
QUANTITY_LIKE_PERCENT_WORDS: tuple[str, ...] = ("por 100",)

PERCENT_CONNECTORS: tuple[str, ...] = (
    "del",
    "de la",
    "de los",
    "de las",
    "sobre",
    "respecto",
    "diario",
    "diaria",
    "cada",
)

# A rate written as money per thousand of the price, the usual public-procurement formula (LCSP art.
# 193: "0,60 euros por cada 1.000 euros del precio del contrato"); read as a fraction (0,60 -> 0.0006).
RATIO_CURRENCY_TERMS: tuple[str, ...] = ("euros", "euro", "eur", "\u20ac")

RATIO_BASE_TERMS: tuple[str, ...] = ("1.000", "1000", "mil")

# Words that name the penalty itself (a delay word such as "retraso" does not: it only says what the
# penalty is for). A rate no daily term claimed is read only when it directly follows one of these.
PENALTY_AMOUNT_TERMS: Terms = {
    "en": ("penalt*", "penalis*", "liquidated damages", "delay damages"),
    "es": (
        "penaliz*",
        "penalidad*",
        "clausula penal",
        "multa*",
        "sancion*",
        "danos y perjuicios liquidados",
    ),
}

# The only per-day phrases that make "X euros por cada 1.000 euros" a daily rate. "diaria"/"daily" count only
# right behind a penalty word ("penalidades diarias"), never as an adjective of another noun ("parte diario").
RATIO_DAILY_TERMS: Terms = {
    "en": ("per day", "per calendar day", "per working day", "each day", "for each day"),
    "es": ("por dia", "por cada dia", "cada dia", "por dia natural", "por dia habil"),
}

# Another period right behind a figure ("0.5% per week", "2% mensual", "3% por hora"): that figure is
# not a daily rate and not a cumulative cap. An adjective is enough ("mensual"); a noun counts only after
# an introducer ("por mes", "per week", "cada hora"), so "desde el mes 6" or "within the month" do not.
OTHER_PERIOD_ADJECTIVES: Terms = {
    "en": (
        "weekly",
        "monthly",
        "yearly",
        "annual",
        "annually",
        "quarterly",
        "hourly",
        "biweekly",
        "bimonthly",
        "fortnightly",
    ),
    "es": (
        "semanal",
        "semanales",
        "mensual",
        "mensuales",
        "anual",
        "anuales",
        "trimestral",
        "trimestrales",
        "bimestral",
        "semestral",
        "quincenal",
        "horaria",
        "horario",
        "mensualmente",
        "anualmente",
        "semanalmente",
    ),
}

OTHER_PERIOD_NOUNS: Terms = {
    "en": (
        "week*",
        "month*",
        "year*",
        "quarter*",
        "fortnight*",
        "hour",
        "hours",
        "period",
        "periods",
    ),
    "es": (
        "semana*",
        "mes",
        "meses",
        "ano",
        "anos",
        "quincena*",
        "trimestre*",
        "bimestre*",
        "semestre*",
        "hora",
        "horas",
        "periodo",
        "periodos",
        "anualidad*",
        "mensualidad*",
    ),
}

PERIOD_INTRODUCERS: tuple[str, ...] = (
    "por",
    "per",
    "cada",
    "al",
    "a la",
    "en",
    "every",
    "each",
    "/",
)

# "every 7 days", "por cada 30 dias": a period made of several days is not a daily rate either.
OTHER_PERIOD_REGEXES: tuple[str, ...] = (r"(?:cada|every|each)\s+\d+\s+(?:dias?|days?)",)

# Words that mark a figure next to the penalty as something else (a retention, an advance, a bond...).
OTHER_SUBJECT_TERMS: Terms = {
    "en": (
        "retention*",
        "retain*",
        "advance*",
        "bond*",
        "guarantee*",
        "deposit*",
        "interest*",
        "tax*",
        "vat",
        "discount*",
        "bonus*",
        "liability",
        "liabilities",
    ),
    "es": (
        "retencion*",
        "retenid*",
        "retener*",
        "retend*",
        "retien*",
        "anticipo*",
        "fianza*",
        "aval*",
        "garantia*",
        "deposito*",
        "interes*",
        "impuesto*",
        "iva",
        "descuento*",
        "bonificacion*",
        "prima*",
        "responsabilidad*",
    ),
}

# A comparison right before a figure ("por cada dia de retraso superior al 10 por 100 del plazo"): the
# figure is a threshold, not the rate.
THRESHOLD_TERMS: Terms = {
    "en": (
        "below",
        "above",
        "over",
        "under",
        "less than",
        "more than",
        "exceeds",
        "exceeding",
        "reaches",
        "reaching",
        "beyond",
    ),
    "es": (
        "superior*",
        "inferior*",
        "supere*",
        "supera",
        "superan",
        "exceda*",
        "excede",
        "mas de",
        "menos de",
        "mayor*",
        "menor*",
        "alcance",
        "alcanzar",
        "alcanza",
        "transcurrido*",
    ),
}

# Words allowed between a figure and the end of its clause when the figure is a cap (the
# base: "del precio del contrato", "of the Contract Price"). Anything else after the figure ("en total",
# "as a maximum", "por ausencia del jefe de obra", "si no avisa") means it is not the daily rate.
CAP_BASE_WORDS: tuple[str, ...] = (
    "del",
    "de",
    "la",
    "el",
    "los",
    "las",
    "of",
    "the",
    "precio",
    "price",
    "contrato",
    "contract",
    "importe",
    "amount",
    "valor",
    "value",
    "adjudicacion",
    "licitacion",
    "presupuesto",
    "obra",
    "obras",
    "works",
)

# After a cap figure the base may continue with these words; the first other word must be a stop (a new
# statement), otherwise the cap is relative to something else ("del plazo", "de cada pago", "de la anualidad").
CAP_STOP_WORDS: tuple[str, ...] = (
    "y", "e", "o", "u", "ni", "and", "or", "nor", "pero", "but", "salvo", "except", "que", "which",
    "cuando", "si", "when", "if", "ni",
)  # fmt: skip

# Words that say a penalty is for being late; the daily phrase must sit next to one of them.
DELAY_TERMS: Terms = {
    "en": ("delay*", "late", "lateness"),
    "es": ("retras*", "demora*", "mora", "tardi*"),
}
