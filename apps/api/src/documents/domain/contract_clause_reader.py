"""Pure functions that read a contract clause's type and penalty figures (Spanish and English).

No I/O and no database: the words come from ``contract_clause_lexicon``. Percentages are returned as
fractions (``0.001`` is 0.1%), the unit the LEGAL evaluators expect.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache

from src.documents.domain.contract_clause_lexicon import (
    AGGREGATE_TERMS,
    CAP_STOP_WORDS,
    CAP_SUBJECT_WORDS,
    CAP_VERB_TERMS,
    CLAUSE_TYPE_ORDER,
    CLAUSE_TYPE_TERMS,
    COORDINATOR_TERMS,
    DAILY_SENTENCE_TERMS,
    DELAY_TERMS,
    IMPOSITION_WORDS,
    OTHER_PERIOD_ADJECTIVES,
    OTHER_PERIOD_NOUNS,
    OTHER_PERIOD_REGEXES,
    OTHER_SUBJECT_TERMS,
    PENALTY_AMOUNT_TERMS,
    PERCENT_CONNECTORS,
    PERCENT_ROLE_TERMS,
    PERCENT_ROLE_WINDOW,
    PERCENT_WORDS,
    PERIOD_INTRODUCERS,
    QUANTITY_LIKE_PERCENT_WORDS,
    RATE_INTRODUCER_WORDS,
    RATIO_BASE_TERMS,
    RATIO_CURRENCY_TERMS,
    RATIO_DAILY_TERMS,
    RESIDUAL_BASE_WORDS,
    THRESHOLD_TERMS,
    Terms,
)


def fold(text: str) -> str:
    """Lowercase, strip accents, and turn non-breaking spaces into spaces."""
    decomposed = unicodedata.normalize("NFKD", text.replace("\u00a0", " "))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


@cache
def _term_pattern(term: str) -> re.Pattern[str]:
    prefix = term.endswith("*")
    body = re.escape(term.rstrip("*")).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9]){body}" + ("" if prefix else r"(?![a-z0-9])"))


def _all_terms(terms: Terms) -> Iterable[str]:
    for language_terms in terms.values():
        yield from language_terms


def infer_clause_type_name(text: str) -> str | None:
    """Name of the first clause type (in ``CLAUSE_TYPE_ORDER``) with a matching term, or None."""
    folded = fold(text)
    for name in CLAUSE_TYPE_ORDER:
        if any(_term_pattern(term).search(folded) for term in _all_terms(CLAUSE_TYPE_TERMS[name])):
            return name
    return None


# ── percentages ──────────────────────────────────────────────────────────────────────────────────


def _word_alternation(words: Iterable[str]) -> str:
    return "|".join(
        re.escape(word).replace(r"\ ", r"\s*") for word in sorted(words, key=len, reverse=True)
    )


_PERCENT_WORD_UNITS = _word_alternation(PERCENT_WORDS)
_QUANTITY_LIKE_UNITS = _word_alternation(QUANTITY_LIKE_PERCENT_WORDS)
_CONNECTORS = _word_alternation(PERCENT_CONNECTORS)
_PERCENT_RE = re.compile(
    rf"(?<![\d.,])(\d(?:[\d.,]*\d)?)\s*(?:%"
    rf"|(?:{_PERCENT_WORD_UNITS})(?![a-z0-9])"
    rf"|(?P<quantity_like>{_QUANTITY_LIKE_UNITS}))"
)
# "por 100" is a percentage at the end of the text, before punctuation (not '100.000' or '100,5') or
# before a connector word; otherwise it starts a quantity ("2 por 100.000 habitantes", "15 por 100 metros")
_QUANTITY_LIKE_IS_PERCENT = re.compile(
    rf"(?![a-z0-9])(?:[ \t]*(?:$|[.,;:)](?!\d))|[ \t]+(?:{_CONNECTORS})(?![a-z0-9]))"
)
_CURRENCY = _word_alternation(RATIO_CURRENCY_TERMS)
_RATIO_BASE = _word_alternation(RATIO_BASE_TERMS)
_RATIO_RE = re.compile(
    rf"(?<![\d.,])(\d(?:[\d.,]*\d)?)\s*(?:{_CURRENCY})\s+por\s+cada\s+(?:{_RATIO_BASE})\s*"
    rf"(?:{_CURRENCY})(?![a-z0-9])"
)


@dataclass(frozen=True)
class PercentMention:
    value: float  # fraction: 0.001 is 0.1%
    start: int  # offsets in fold(text)
    end: int
    ratio: bool = False  # "0,60 euros por cada 1.000 euros", not a percentage
    readable: bool = (
        True  # False: "N por 100" that may start a quantity; it holds its place, no value
    )


def parse_percent_number(token: str) -> float | None:
    """The number in ``token`` read in percentage context, or None when it is not a plain number.

    A percentage almost never has a thousands separator, so a lone ``,`` or ``.`` is the decimal mark
    (``0,1`` and ``0.1`` are both a tenth, ``0,125`` is 0.125). When both marks appear the last one is
    the decimal mark and the other groups thousands (``1.000,5`` and ``1,000.5`` are both 1000.5).
    Several marks of one kind (``1.000.000``) are not a percentage.
    """
    marks = [ch for ch in token if ch in ".,"]
    if not marks:
        normalized = token
    elif "." in token and "," in token:
        decimal = token[max(token.rfind("."), token.rfind(","))]
        thousands = "," if decimal == "." else "."
        integer_part = token.rpartition(decimal)[0]
        groups = integer_part.split(thousands)
        well_formed = (
            token.count(decimal) == 1
            and 1 <= len(groups[0]) <= 3
            and all(len(group) == 3 for group in groups[1:])
        )
        if not well_formed:
            return None
        normalized = token.replace(thousands, "").replace(decimal, ".")
    elif len(marks) == 1:
        normalized = token.replace(",", ".")
    else:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _percent_mentions(folded: str) -> list[PercentMention]:
    mentions: list[PercentMention] = []
    for match in _PERCENT_RE.finditer(folded):
        number = parse_percent_number(match.group(1))
        if number is None:
            continue
        readable = not match.group("quantity_like") or bool(
            _QUANTITY_LIKE_IS_PERCENT.match(folded, match.end())
        )
        mentions.append(
            PercentMention(number / 100.0, match.start(), match.end(), readable=readable)
        )
    return mentions


def extract_percentages(text: str) -> list[PercentMention]:
    return [mention for mention in _percent_mentions(fold(text)) if mention.readable]


def extract_rate_mentions(text: str) -> list[PercentMention]:
    """Percentages plus "X euros por cada 1.000 euros" ratios (X/1000), in text order.

    A "N por 100" that may start a quantity is kept as an unreadable mention: it holds its place so
    that the figure next to it is not taken for the only one.
    """
    folded = fold(text)
    mentions = _percent_mentions(folded)
    for match in _RATIO_RE.finditer(folded):
        number = parse_percent_number(match.group(1))
        if number is not None:
            # "1.200 euros" is a thousand-separated amount, not 1,2 euros: hold the place, no value
            looks_like_thousands = bool(_THOUSANDS_RE.fullmatch(match.group(1)))
            mentions.append(
                PercentMention(
                    number / 1000.0,
                    match.start(),
                    match.end(),
                    ratio=True,
                    readable=not looks_like_thousands,
                )
            )
    return sorted(mentions, key=lambda mention: mention.start)


_THOUSANDS_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
_SENTENCE_BREAK = re.compile(r"(?<=[.;!?])\s+|\n+")


def _sentence_spans(folded: str) -> list[tuple[int, int]]:
    """Offsets of each sentence. A '.' inside a number (``0.1%``) is not followed by a space."""
    spans: list[tuple[int, int]] = []
    start = 0
    for found in _SENTENCE_BREAK.finditer(folded):
        spans.append((start, found.start()))
        start = found.end()
    spans.append((start, len(folded)))
    return [(a, b) for a, b in spans if b > a]


def _compile(terms: Terms) -> tuple[re.Pattern[str], ...]:
    return tuple(_term_pattern(term) for term in _all_terms(terms))


_PENALTY = _compile(CLAUSE_TYPE_TERMS["PENALTY"])
_PENALTY_AMOUNT = _compile(PENALTY_AMOUNT_TERMS)
_DAILY_SENTENCE = _compile(DAILY_SENTENCE_TERMS)
_DELAY = _compile(DELAY_TERMS)
_DAILY_ROLE = _compile(PERCENT_ROLE_TERMS["DAILY"])
_CAP_ROLE = _compile(PERCENT_ROLE_TERMS["CAP"])
_OTHER_SUBJECT = _compile(OTHER_SUBJECT_TERMS)
_THRESHOLD = _compile(THRESHOLD_TERMS)


def _alternation(terms: Terms) -> str:
    return "|".join(_term_pattern(term).pattern for term in _all_terms(terms))


# "por cada dia natural de retraso", "for each day of delay": the per-day phrase leads straight to the delay
_DAILY_DELAY = re.compile(
    rf"(?:{_alternation(DAILY_SENTENCE_TERMS)})\s+"
    rf"(?:(?:natural|naturales|habil|habiles|calendar|working|business|de|del|of|in|en|the)\s+)*"
    rf"(?:{_alternation(DELAY_TERMS)})"
)
_PERIOD_INTRODUCER = "|".join(
    re.escape(word) if word == "/" else _term_pattern(word).pattern for word in PERIOD_INTRODUCERS
)
_PERIOD_NOUN_RE = re.compile(
    rf"(?:{_PERIOD_INTRODUCER})\s*(?:(?:cada|el|la|un|una|an?)\s+)?(?:{_alternation(OTHER_PERIOD_NOUNS)})"
)
# an adjective qualifies the figure only when it comes right behind it ("2% mensual"), not inside the
# base ("0.1% of the monthly invoice")
_PERIOD_ADJECTIVE_RE = re.compile(rf"\s*(?:{_alternation(OTHER_PERIOD_ADJECTIVES)})")
_OTHER_PERIOD_REGEXES = tuple(re.compile(pattern) for pattern in OTHER_PERIOD_REGEXES)
_CAP_VERBS = frozenset(_all_terms(CAP_VERB_TERMS))
_CAP_VERB_PATTERNS = tuple(_term_pattern(term) for term in _CAP_VERBS)
_AGGREGATE = _compile(AGGREGATE_TERMS)
_RATIO_DAILY = _compile(RATIO_DAILY_TERMS)
_AFTER_PENALTY_WORD = re.compile(rf"(?:{_alternation(PENALTY_AMOUNT_TERMS)})[a-z]*\s+$")
_PENALTY_DAILY_ADJECTIVE = re.compile(
    rf"(?:{_alternation(PENALTY_AMOUNT_TERMS)})[a-z]*\s+(?:diari[oa]s?|daily)(?![a-z0-9])"
)
_CAP_SUBJECT_WORDS = frozenset(CAP_SUBJECT_WORDS)
_RESIDUAL_BASE_WORDS = frozenset(RESIDUAL_BASE_WORDS)
# a later clause that says the figure is a limit, not a rate ("..., beyond which the Employer may terminate")
_LIMIT_REACHED = re.compile(
    r"\b(?:beyond|past|upon reaching|once|reached|alcanzad\w+|superad\w+)\b"
)
_TAX_QUALIFIER = re.compile(
    r"\(?\b(?:iva|vat)\s+(?:excluid\w+|incluid\w+|excluded|included|not included)\b\)?"
)
_ROLE_PATTERNS: Mapping[str, tuple[tuple[re.Pattern[str], bool, str], ...]] = {
    role: tuple((_term_pattern(term), term in _CAP_VERBS, term) for term in _all_terms(terms))
    for role, terms in PERCENT_ROLE_TERMS.items()
}
_MONEY_RE = re.compile(
    rf"\d[\d.,]*\s*(?:mil\s+)?(?:{_CURRENCY}|usd|dolar(?:es)?|gbp|chf|pesos?|libras?)(?![a-z0-9])"
    rf"|(?:usd|eur|gbp|chf)\s*\d|[$\u00a3\u20ac]\s*\d"
)
_SEGMENT_BREAK = re.compile(
    r"(?<!\d),|,(?!\d)|[;:]|\s(?:y|e|o|ni|mas|and|or|plus|while|whereas|but|pero|mientras que|asi como|junto con|together with|as well as)\s"
)
_HARD_BREAK = re.compile(r"(?<!\d),|,(?!\d)|[;:]")
_AUXILIARIES = re.compile(
    r"\s+(?:shall|will|may|must|should|can|podra|podran|debera|deberan|sera|seran)$"
)
_RELATIVE = re.compile(
    r"\bof which\b|\bde (?:la|las) cual(?:es)?\b|\bcuy[oa]s?\b|^(?:la|el|lo|las|los) cual(?:es)?$"
)
_COORDINATOR = re.compile(
    rf"(?<![a-z0-9])(?:{_word_alternation(COORDINATOR_TERMS)})(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:alcanz|resol|pudiend|terminat|reach)[a-z]*"
)
_IMPOSITION_WORDS = frozenset(IMPOSITION_WORDS)
_CAP_STOP_WORDS = frozenset(CAP_STOP_WORDS)
_CAP_BASE_WORDS = _RESIDUAL_BASE_WORDS | {"sobre", "respecto", "acumulado", "acumulada"}
_ADJECTIVAL_DAILY = frozenset({"diario*", "diaria*", "daily"})
_ADJECTIVAL_GAP = 20  # "0,1% diario", "daily penalty of": the adjective stands next to its figure
_NOT_A_DAY_RATE = re.compile(r"\s+(?:siguiente|anterior|posterior|habil|de\b|del\b)")
_LEAD_MAX = 12  # the per-day phrase opens the sentence, after at most a clause number ("18.1 ")
_GAP_WORD = frozenset(RATE_INTRODUCER_WORDS)
_PERIOD_REACH = 20  # characters after a figure searched for another period ("0.5% per week")
_RATIO_REACH = 48  # a ratio is followed by its base ("del precio del contrato") before the period
_AFTER_MENTION = 24  # characters after a figure searched for an "other subject" word
_BEFORE_MENTION = (
    24  # characters before a figure searched for a threshold or an "other subject" word
)
_MAX_SENTENCE = 4000  # a longer "sentence" is not a clause: no data


def _any_match(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _word_end(text: str, position: int) -> int:
    """End of the word that a prefix term matched up to ``position``."""
    while position < len(text) and "a" <= text[position] <= "z":
        position += 1
    return position


def _penalty_words_end_before(text: str, limit: int) -> list[int]:
    return [
        end
        for pattern in _PENALTY_AMOUNT
        for found in pattern.finditer(text)
        if (end := _word_end(text, found.end())) <= limit
    ]


def _is_a_penalty_subject(part: str) -> bool:
    """A cap verb's subject: penalty words, delay words and the closed list of fillers, nothing else."""
    tokens = re.findall(r"[a-z]+", part)
    if not tokens or not _penalty_words_end_before(part, len(part)):
        return False
    return all(
        token in _CAP_SUBJECT_WORDS
        or _any_match(_PENALTY_AMOUNT, token)
        or _any_match(_DELAY, token)
        for token in tokens
    )


def _cap_verb_binds_to_the_penalty(sentence: str, term_start: int) -> bool:
    """For a verb cap term ("no podran superar"): what its clause is about is the penalty.

    The clause is the stretch since the last comma, colon or semicolon. With a subject of its own, every
    coordinated part of it must be a penalty subject (closed grammar, see ``_is_a_penalty_subject``),
    the stretch must hold no other subject (retention, bond, liability, ...) and, unless a figure is
    already attached to it, no per-day word (then the verb is about a rate). Without one (empty, "of
    which", "la cual", "cuyo") the clause just before must carry the penalty's own rate: a figure, and
    a penalty word in it or in the sentence's first clause, with no other subject in either. A bare
    "que"/"which" is never read, nor is a verb that opens the sentence: they may point at any noun.
    """
    before = sentence[:term_start]
    clauses = [clause for clause in _HARD_BREAK.split(before) if clause.strip()]
    if not clauses:
        return False
    clause_ended = before.rstrip().endswith((",", ";", ":"))
    stretch = "" if clause_ended else clauses[-1]
    earlier = clauses if clause_ended else clauses[:-1]
    parts = [_AUXILIARIES.sub("", part.strip()) for part in _SEGMENT_BREAK.split(stretch)]
    conjunct = parts[-1]
    if conjunct and not _RELATIVE.search(conjunct):
        return (
            not re.match(r"(?:cada|each)\b", conjunct)
            and all(_is_a_penalty_subject(part) for part in parts if part)
            and not _any_match(_OTHER_SUBJECT, stretch)
            and not (_any_match(_DAILY_ROLE, stretch) and not re.search(r"\d", stretch))
        )
    inner = [part for part in parts[:-1] if part]
    previous = inner[-1] if inner else (earlier[-1] if earlier else "")
    return _carries_the_penalty_rate(previous, clauses[0])


def _carries_the_penalty_rate(previous: str, first_clause: str) -> bool:
    """The clause before a subject-less cap verb holds the rate, and the penalty is named with it."""
    if not re.search(r"\d", previous) or _any_match(_OTHER_SUBJECT, previous):
        return False
    if _penalty_words_end_before(previous, len(previous)):
        return True
    return bool(_penalty_words_end_before(first_clause, len(first_clause))) and not _any_match(
        _OTHER_SUBJECT, first_clause
    )


def _roles_in_sentence(sentence: str, spans: list[tuple[int, int]]) -> list[str | None]:
    """Role of each percentage (``spans`` are offsets inside ``sentence``): 'DAILY', 'CAP' or None.

    Every role term claims the single nearest percentage it can bind to (ties claim nothing); a
    percentage then takes the role of its nearest claim (a tie between roles gives it no role).
    """
    claims: dict[int, list[tuple[int, str]]] = {}
    for role, patterns in _ROLE_PATTERNS.items():
        for pattern, is_verb, term in patterns:
            for found in pattern.finditer(sentence):
                window = PERCENT_ROLE_WINDOW
                if term in _ADJECTIVAL_DAILY and not _AFTER_PENALTY_WORD.search(
                    sentence[: found.start()]
                ):
                    window = _ADJECTIVAL_GAP  # "informe diario": the adjective of another noun
                if is_verb and not _cap_verb_binds_to_the_penalty(sentence, found.start()):
                    continue
                if term == "al dia" and _NOT_A_DAY_RATE.match(sentence, found.end()):
                    continue  # "al dia siguiente del vencimiento" is a date, not a rate
                candidates: list[tuple[int, int]] = []
                for index, (mention_start, mention_end) in enumerate(spans):
                    if mention_start >= found.end():  # the number follows the term
                        gap = mention_start - found.end()
                    elif mention_end <= found.start() and role == "DAILY":  # "0,1% diario"
                        gap = found.start() - mention_end
                    else:
                        continue
                    if gap <= window:
                        candidates.append((gap, index))
                candidates.sort()
                if not candidates or (len(candidates) > 1 and candidates[0][0] == candidates[1][0]):
                    continue
                gap, index = candidates[0]
                claims.setdefault(index, []).append((gap, role))
    roles: list[str | None] = []
    for index in range(len(spans)):
        own = sorted(claims.get(index, []))
        if not own or (len(own) > 1 and own[0][0] == own[1][0] and own[0][1] != own[1][1]):
            roles.append(None)
        else:
            roles.append(own[0][1])
    return roles


def _period_follows(sentence: str, end: int, next_start: int, reach: int) -> bool:
    """Another period behind a figure: an adjective right after it, or "per week", "every 7 days"."""
    region = sentence[end : min(end + reach, next_start)]
    return bool(
        _PERIOD_ADJECTIVE_RE.match(region)
        or _PERIOD_NOUN_RE.search(region)
        or any(pattern.search(region) for pattern in _OTHER_PERIOD_REGEXES)
    )


def _has_other_period(sentence: str) -> bool:
    return bool(
        _PERIOD_NOUN_RE.search(sentence)
        or _PERIOD_ADJECTIVE_RE.search(sentence)
        or any(pattern.search(sentence) for pattern in _OTHER_PERIOD_REGEXES)
    )


def _around(sentence: str, start: int, end: int, after: int = _AFTER_MENTION) -> str:
    """Words next to a figure: before it, and after it up to the end of its clause."""
    following = _HARD_BREAK.split(sentence[end : end + after])[0]
    return _TAX_QUALIFIER.sub(
        " ", sentence[max(0, start - _BEFORE_MENTION) : start] + " " + following
    )


def _clause_before(sentence: str, start: int) -> str:
    """The words of the figure's clause that come before it (at most the role window and a half)."""
    window = sentence[max(0, start - 3 * PERCENT_ROLE_WINDOW // 2) : start]
    return _HARD_BREAK.split(window)[-1]


def _daily_claim_is_plausible(sentence: str, start: int, end: int) -> bool:
    """A figure a per-day term claimed is not a threshold ("superior al 10%") or another subject's."""
    before = sentence[max(0, start - _BEFORE_MENTION) : start]
    return (
        not _any_match(_THRESHOLD, before)
        and not _any_match(_AGGREGATE, _clause_before(sentence, start))
        and not _any_match(_CAP_VERB_PATTERNS, before)
        and not _any_match(_OTHER_SUBJECT, _around(sentence, start, end))
    )


def _ratio_is_a_clean_rate(sentence: str, spans: list[tuple[int, int]], index: int) -> bool:
    """A 'euros por cada 1.000 euros' ratio is a daily rate only when it is the sentence's one amount.

    A strong per-day phrase ("por dia", "per day", "diaria") must sit next to it. A fixed amount
    elsewhere in the sentence, another period anywhere in it, a cap word before the ratio, or a word of
    another subject (bond, interest...) around it means the ratio may belong to something else.
    """
    start, end = spans[index]
    rest = sentence
    for a, b in spans:  # blank every figure, the ratio's own words included
        rest = rest[:a] + " " * (b - a) + rest[b:]
    if _MONEY_RE.search(rest) or _has_other_period(sentence):
        return False
    near = sentence[max(0, start - PERCENT_ROLE_WINDOW) : end + PERCENT_ROLE_WINDOW]
    if not (_any_match(_RATIO_DAILY, near) or _PENALTY_DAILY_ADJECTIVE.search(sentence)):
        return False
    previous_end = max((b for _, b in spans if b <= start), default=0)
    return not _any_match(_CAP_ROLE, sentence[previous_end:start]) and not _any_match(
        _OTHER_SUBJECT, _around(sentence, start, end, _RATIO_REACH)
    )


def _is_the_penalty_rate(sentence: str, start: int, end: int) -> bool:
    """True when the figure at ``sentence[start:end]`` is introduced by a word naming the penalty.

    The sentence must open with the per-day phrase and reach the figure through a plain statement (no
    coordinator or condition in between). The figure is the rate only if: exactly one penalty word precedes it and only rate introducers
    ("del", "equal to", "amounting to") sit between the two; the sentence holds no amount of money; its
    clause holds no other subject (retention, bond, interest...) and no aggregate wording ("total",
    "aggregate") before the figure; and only the base ("del precio del contrato", "of the Contract
    Price") follows it in its clause, so "en total", "como maximo", "si no avisa" or "por ausencia del
    jefe de obra" make it something else.
    """
    lead = _DAILY_DELAY.search(sentence)
    if lead is None or lead.start() > _LEAD_MAX or _COORDINATOR.search(sentence[:start]):
        return False
    ends = _penalty_words_end_before(sentence, start)
    if len(ends) != 1 or _MONEY_RE.search(sentence):
        return False
    penalty_start = min(
        found.start() for pattern in _PENALTY_AMOUNT for found in pattern.finditer(sentence)
    )
    middle = re.findall(r"[a-z]+", sentence[_word_end(sentence, lead.end()) : penalty_start])
    if not set(middle) <= _IMPOSITION_WORDS:
        return False
    gap = sentence[ends[0] : start]
    if len(gap) > PERCENT_ROLE_WINDOW or not set(gap.split()) <= _GAP_WORD:
        return False
    clause_start = max((m.end() for m in _HARD_BREAK.finditer(sentence, 0, start)), default=0)
    following = _HARD_BREAK.search(sentence, end)
    clause_end = following.start() if following else len(sentence)
    clause = _TAX_QUALIFIER.sub(" ", sentence[clause_start:clause_end])
    base = _TAX_QUALIFIER.sub(" ", sentence[end:clause_end])
    return (
        not _any_match(_OTHER_SUBJECT, clause)
        and not _any_match(_AGGREGATE, sentence[clause_start:start])
        and set(re.findall(r"[a-z]+", base)) <= _RESIDUAL_BASE_WORDS
        and not _LIMIT_REACHED.search(sentence[clause_end:])
    )


def _base_is_the_price(after_figure: str) -> bool:
    """What follows a cap figure is the price ("del precio del contrato") and then a stop or the end.

    "del plazo", "de las unidades", "de cada pago", "de la anualidad" make the cap relative to something
    else: the first word that is not part of the price base must start a new statement.
    """
    for token in re.findall(r"[a-z]+", _HARD_BREAK.split(_TAX_QUALIFIER.sub(" ", after_figure))[0]):
        if token in _CAP_BASE_WORDS:
            continue
        return token in _CAP_STOP_WORDS
    return True


def _cap_has_a_period_or_unit(sentence: str, start: int, end: int, next_start: int) -> bool:
    """A cap per month ("superar mensualmente el 1%") or per unit ("el 5% de cada pago") is not the total.

    Only the words between the cap term and the figure count: an earlier period belongs to the figure before.
    """
    before = sentence[max(0, start - 2 * _BEFORE_MENTION) : start]
    cap_term_ends = [m.end() for pattern in _CAP_ROLE for m in pattern.finditer(before)]
    # the period must stand between the cap term and its figure, not belong to the figure before
    before = before[max(cap_term_ends, default=0) :]
    base = sentence[end:next_start]
    return bool(
        _PERIOD_ADJECTIVE_RE.search(before)
        or _PERIOD_NOUN_RE.search(before)
        or not _base_is_the_price(base)
    )


def _role_is_reliable(
    sentence: str,
    mention: PercentMention,
    spans: list[tuple[int, int]],
    index: int,
    role: str,
) -> bool:
    """Whether the figure that a term claimed can be trusted with its role."""
    start, end = spans[index]
    next_start = spans[index + 1][0] if index + 1 < len(spans) else len(sentence)
    reach = _RATIO_REACH if mention.ratio else _PERIOD_REACH
    if _period_follows(sentence, end, next_start, reach):
        return False  # "0.5% per week" is neither a daily rate nor a total cap
    if role == "CAP":
        return not mention.ratio and not _cap_has_a_period_or_unit(sentence, start, end, next_start)
    if not _daily_claim_is_plausible(sentence, start, end):
        return False
    return not mention.ratio or _ratio_is_a_clean_rate(sentence, spans, index)


def _drop_unreliable_roles(
    sentence: str,
    in_sentence: list[PercentMention],
    spans: list[tuple[int, int]],
    roles: list[str | None],
) -> None:
    """Withdraw the role of a figure that cannot be trusted with it (in place)."""
    for index, mention in enumerate(in_sentence):
        role = roles[index]
        if (
            role is not None
            and not (mention.readable and _role_is_reliable(sentence, mention, spans, index, role))
            or not mention.readable
        ):
            roles[index] = None


def _sentence_roles(
    sentence: str, in_sentence: list[PercentMention], offset: int
) -> list[str | None]:
    spans = [(m.start - offset, m.end - offset) for m in in_sentence]
    roles = _roles_in_sentence(sentence, spans)
    _drop_unreliable_roles(sentence, in_sentence, spans, roles)
    if "DAILY" not in roles and roles.count(None) == 1 and not _has_other_period(sentence):
        index = roles.index(None)
        mention = in_sentence[index]
        if mention.readable and not mention.ratio and _is_the_penalty_rate(sentence, *spans[index]):
            roles[index] = "DAILY"
    return roles


def penalty_rate_and_cap(text: str) -> tuple[float | None, float | None]:
    """(daily rate, cumulative cap) of a penalty clause, each as a fraction, or None.

    Only a sentence that itself names a penalty is read, so a liability limit, a retention or an
    advance payment in the next sentence is never taken for the penalty's cap. Inside it, each
    percentage takes the role of the term that claims it ("diario", "por día", "per day" for the
    daily rate; "tope", "máximo", "capped at", "not to exceed" for the cap), unless another period
    follows the figure ("0.5% per week"). A percentage no term claims is not assigned, with one
    exception: when the sentence has a per-day phrase next to a delay word but too far from the rate
    ("Por cada día natural de retraso ..., una penalización del 0,1% ...") and exactly one percentage
    is left without a role, introduced by a word that names the penalty, that percentage is the daily
    rate. A rate given as money per thousand of the price counts only as an explicitly daily rate and
    only when it is the sentence's only amount. The first figure found for a role wins.
    """
    folded = fold(text)
    mentions = extract_rate_mentions(text)
    daily: float | None = None
    cap: float | None = None
    for sentence_start, sentence_end in _sentence_spans(folded):
        in_sentence = [m for m in mentions if sentence_start <= m.start < sentence_end]
        sentence = folded[sentence_start:sentence_end]
        if not in_sentence or len(sentence) > _MAX_SENTENCE or not _any_match(_PENALTY, sentence):
            continue
        roles = _sentence_roles(sentence, in_sentence, sentence_start)
        caps = {m.value for m, role in zip(in_sentence, roles, strict=True) if role == "CAP"}
        for mention, role in zip(in_sentence, roles, strict=True):
            if role == "DAILY" and daily is None:
                daily = mention.value
            elif role == "CAP" and cap is None and len(caps) == 1:
                cap = (
                    mention.value
                )  # two different caps in one sentence: which is the total is a guess
    return daily, cap
