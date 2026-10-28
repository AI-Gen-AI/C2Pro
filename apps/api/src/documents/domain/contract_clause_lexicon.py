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
            "limite",
            "limites",
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

# How many characters on each side of a percentage are searched for a role term.
PERCENT_ROLE_WINDOW = 48

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

# Unambiguous "per day" phrases: the daily terms that may justify reading a lone percentage as the daily
# rate when no term sits next to it. "al dia" ("al dia siguiente") and "a day" are left out on purpose.
DAILY_SENTENCE_TERMS: Terms = {
    "en": ("per day", "per calendar day", "per working day", "each day", "for each day", "daily"),
    "es": (
        "diario*",
        "diaria*",
        "por dia",
        "por cada dia",
        "cada dia",
        "por dia natural",
        "por dia habil",
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

# Words that say a penalty is for being late; the daily phrase must sit next to one of them.
DELAY_TERMS: Terms = {
    "en": ("delay*", "late", "lateness"),
    "es": ("retras*", "demora*", "mora", "tardi*"),
}

# The only words allowed between a penalty word and a figure for that figure to be its rate
# ("penalizacion del 0,1%", "liquidated damages amounting to 0.05%"). Anything else ("hasta alcanzar
# el", "limitada al", "cuando el avance sea inferior al") means the figure is something else.
RATE_INTRODUCER_WORDS: tuple[str, ...] = (
    "de",
    "del",
    "un",
    "una",
    "el",
    "la",
    "a",
    "razon",
    "equivalente",
    "igual",
    "proporcion",
    "en",
    "of",
    "an",
    "the",
    "at",
    "to",
    "rate",
    "amounting",
    "equal",
    "equals",
    "equivalent",
    "al",
    "es",
    "sea",
    "sera",
    "seran",
    "is",
    "be",
    "shall",
    "fixed",
    "set",
)

# Cap terms that are verbs ("las penalidades no podran superar el 5%"): they bind a figure to whatever
# the sentence is about, so the words before them must name the penalty (or nothing, "..., no superara
# el 10%") and no other subject (retention, bond, liability...).
CAP_VERB_TERMS: Terms = {
    "en": ("not exceed*", "not to exceed", "no more than"),
    "es": (
        "no excedera*",
        "no superara*",
        "no podra exceder*",
        "no podra superar*",
        "no podran exceder*",
        "no podran superar*",
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


# Closed grammar for the subject of a cap verb ("las penalidades por demora no podran superar el 10%"):
# a penalty word, a delay word and these words, nothing else. Any other noun ("por defectos", "en el pago",
# "impuestas por incumplimiento de las normas de seguridad") is another penalty's cap.
CAP_SUBJECT_WORDS: tuple[str, ...] = (
    "el",
    "la",
    "los",
    "las",
    "lo",
    "the",
    "all",
    "any",
    "de",
    "del",
    "of",
    "por",
    "for",
    "importe",
    "total",
    "suma",
    "cuantia",
    "amount",
    "aggregate",
    "sum",
    "impuesta",
    "impuestas",
    "aplicadas",
    "aplicables",
    "payable",
    "imposed",
    "applied",
    "damages",
    "liquidated",
    "by",
    "under",
    "contractor",
    "works",
    "completion",
    "late",
    "clause",
    "sub",
    "is",
    "are",
    "be",
    # the penalty's own rate in the subject ("la penalidad del 0,05% por dia de demora no excederan ...")
    "dia",
    "natural",
    "cada",
    "day",
    "per",
)

# Words allowed between a figure and the end of its clause when the figure is the rate of a penalty (the
# base: "del precio del contrato", "of the Contract Price"). Anything else after the figure ("en total",
# "as a maximum", "por ausencia del jefe de obra", "si no avisa") means it is not the daily rate.
RESIDUAL_BASE_WORDS: tuple[str, ...] = (
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

# Aggregate wording before a penalty word ("el importe total de la penalidad del 10%"): a total, not a rate.
AGGREGATE_TERMS: Terms = {
    "en": ("total", "aggregate", "cumulative", "overall", "global", "sum"),
    "es": ("total", "acumulad*", "conjunto", "suma", "global"),
}

# Words that join or condition a second statement. A per-day phrase that opens the sentence reaches a
# figure only through a plain statement: no coordinator or condition may come between them.
COORDINATOR_TERMS: tuple[str, ...] = (
    "y",
    "e",
    "o",
    "u",
    "ni",
    "and",
    "or",
    "nor",
    "but",
    "pero",
    "si",
    "if",
    "when",
    "cuando",
    "caso",
    "case",
    "unless",
    "salvo",
    "tras",
    "after",
    "once",
    "failing",
    "otherwise",
    "mientras",
    "while",
    "sin perjuicio",
)

# The words allowed between the per-day phrase and the penalty word in the residual rule ("Por cada dia
# natural de retraso en la finalizacion de las obras, el Contratista abonara una penalizacion del 0,1%"):
# fillers, the parties, the milestone being late and the verbs that impose a penalty. A verb that records,
# permits or terminates ("se anotara", "pudiendo resolverse") is not in the list, so it is not read.
IMPOSITION_WORDS: tuple[str, ...] = (
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas", "de", "del", "al", "a", "en", "con",
    "sobre", "respecto", "se", "the", "an", "of", "to", "in", "on", "for", "by", "under", "beyond",
    "at", "its", "this", "such", "shall", "will", "must", "debera", "deberan",
    "abonara", "abonar", "pagara", "pagar", "aplicara", "aplicaran", "aplicar", "impondra", "impondran",
    "imponer", "sufrira", "asumira", "devengara", "descontara", "pay", "apply", "applies", "incur",
    "contratista", "adjudicatario", "administracion", "contractor", "employer", "obras", "obra", "works",
    "work", "contrato", "contract", "proyecto", "project", "plazo", "finalizacion", "terminacion",
    "ejecucion", "entrega", "completion", "time", "programa", "trabajo", "trabajos", "presentacion",
    "cumplimiento", "fecha", "ofertado", "ofertada", "total", "parcial", "hito", "hitos", "milestone",
    "natural", "naturales", "habil", "habiles", "calendar", "working", "business", "retraso", "demora",
    "delay",
)  # fmt: skip

# After a cap figure the base may continue with these words; the first other word must be a stop (a new
# statement), otherwise the cap is relative to something else ("del plazo", "de cada pago", "de la anualidad").
CAP_STOP_WORDS: tuple[str, ...] = (
    "y", "e", "o", "u", "ni", "and", "or", "nor", "pero", "but", "salvo", "except", "que", "which",
    "cuando", "si", "when", "if", "ni",
)  # fmt: skip
