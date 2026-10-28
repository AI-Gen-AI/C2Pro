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
    CAP_BASE_WORDS,
    CAP_STOP_WORDS,
    CLAUSE_TYPE_ORDER,
    CLAUSE_TYPE_TERMS,
    DELAY_TERMS,
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
    RATIO_BASE_TERMS,
    RATIO_CURRENCY_TERMS,
    RATIO_DAILY_TERMS,
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
    new_form: bool = False  # "N por 100" or a ratio: a figure the reader could not read before
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
            PercentMention(
                number / 100.0,
                match.start(),
                match.end(),
                readable=readable,
                new_form=bool(match.group("quantity_like")),
            )
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
                    new_form=True,
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


def _alternation(terms: Terms) -> str:
    return "|".join(_term_pattern(term).pattern for term in _all_terms(terms))


_CAP_ROLE = _compile(PERCENT_ROLE_TERMS["CAP"])
_OTHER_SUBJECT = _compile(OTHER_SUBJECT_TERMS)
_RATIO_DAILY = _compile(RATIO_DAILY_TERMS)
# "penalidades diarias": "diaria"/"daily" counts for a ratio only right behind a penalty word, never as the
# adjective of another noun ("parte diario", "limpieza diaria")
_PENALTY_DAILY_ADJECTIVE = re.compile(
    rf"(?:{_alternation(PENALTY_AMOUNT_TERMS)})[a-z]*\s+(?:diari[oa]s?|daily)(?![a-z0-9])"
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
_TAX_QUALIFIER = re.compile(
    r"\(?\b(?:iva|vat)\s+(?:excluid\w+|incluid\w+|excluded|included|not included)\b\)?"
)
_MONEY_RE = re.compile(
    rf"\d[\d.,]*\s*(?:mil\s+)?(?:{_CURRENCY}|usd|dolar(?:es)?|gbp|chf|pesos?|libras?)(?![a-z0-9])"
    rf"|(?:usd|eur|gbp|chf)\s*\d|[$\u00a3\u20ac]\s*\d"
)
_HARD_BREAK = re.compile(r"(?<!\d),|,(?!\d)|[;:]")
_THRESHOLD = _compile(THRESHOLD_TERMS)
_DELAY = _compile(DELAY_TERMS)
_PROGRESS = re.compile(r"\b(?:avance|ejecucion|progress)\b")
_CAP_BASE_WORDS = frozenset(CAP_BASE_WORDS) | {"sobre", "respecto"}
_CAP_STOP_WORDS = frozenset(CAP_STOP_WORDS)
_ADJECTIVAL_DAILY = re.compile(r"diari[oa]s?\b|\bdaily\b")
_ADJECTIVAL_REACH = 20  # "1 por 100 diario": the adjective stands next to its figure
_PERIOD_REACH = 20  # characters after a figure searched for another period ("0.5% per week")
_RATIO_REACH = 48  # a ratio is followed by its base ("del precio del contrato") before the period
_AFTER_MENTION = 24  # characters after a figure searched for an "other subject" word
_BEFORE_MENTION = 24  # characters before a figure searched for an "other subject" word


def _any_match(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


@cache
def _role_patterns() -> Mapping[str, tuple[re.Pattern[str], ...]]:
    return {
        role: tuple(_term_pattern(term) for term in _all_terms(terms))
        for role, terms in PERCENT_ROLE_TERMS.items()
    }


@cache
def _penalty_patterns() -> tuple[re.Pattern[str], ...]:
    return tuple(_term_pattern(term) for term in _all_terms(CLAUSE_TYPE_TERMS["PENALTY"]))


def _roles_in_sentence(sentence: str, spans: list[tuple[int, int]]) -> list[str | None]:
    """Role of each percentage (``spans`` are offsets inside ``sentence``): 'DAILY', 'CAP' or None.

    Every role term claims the single nearest percentage it can bind to (ties claim nothing); a
    percentage then takes the role of its nearest claim (a tie between roles gives it no role).
    """
    claims: dict[int, list[tuple[int, str]]] = {}
    for role, patterns in _role_patterns().items():
        for pattern in patterns:
            for found in pattern.finditer(sentence):
                candidates: list[tuple[int, int]] = []
                for index, (mention_start, mention_end) in enumerate(spans):
                    if mention_start >= found.end():  # the number follows the term
                        gap = mention_start - found.end()
                    elif mention_end <= found.start() and role == "DAILY":  # "0,1% diario"
                        gap = found.start() - mention_end
                    else:
                        continue
                    if gap <= PERCENT_ROLE_WINDOW:
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
    if _MONEY_RE.search(rest) or _has_other_period(sentence) or not _is_about_delay(sentence):
        return False
    near = sentence[max(0, start - PERCENT_ROLE_WINDOW) : end + PERCENT_ROLE_WINDOW]
    if not (_any_match(_RATIO_DAILY, near) or _PENALTY_DAILY_ADJECTIVE.search(sentence)):
        return False
    previous_end = max((b for _, b in spans if b <= start), default=0)
    return not _any_match(_CAP_ROLE, sentence[previous_end:start]) and not _any_match(
        _OTHER_SUBJECT, _around(sentence, start, end, _RATIO_REACH)
    )


def _is_about_delay(sentence: str) -> bool:
    """A delay word, or "penalidades diarias": a per-day figure of a penalty for another breach is not read."""
    return _any_match(_DELAY, sentence) or bool(_PENALTY_DAILY_ADJECTIVE.search(sentence))


def _base_is_the_price(after_figure: str) -> bool:
    """What follows a cap figure is the price ("del precio del contrato") and then a stop or the end.

    "del plazo", "de las unidades", "de la ejecucion" make the cap relative to something else: the first
    word that is not part of the price base must start a new statement.
    """
    for token in re.findall(r"[a-z]+", _HARD_BREAK.split(_TAX_QUALIFIER.sub(" ", after_figure))[0]):
        if token in _CAP_BASE_WORDS:
            continue
        return token in _CAP_STOP_WORDS
    return True


def _new_form_is_trustworthy(
    sentence: str, start: int, end: int, next_start: int, role: str
) -> bool:
    """A figure written in a way the reader could not read before ("N por 100") may take a role only when
    nothing suggests it is a threshold, another subject's, a ceiling or a cap relative to something else.

    Daily: a strong per-day phrase, or "diario/diaria" next to the figure, or a penalty word with its
    adjective; no comparison word ("superior al") or cap term right before it; no other subject
    (retention, bond, interest...) around it. Cap: the base after it is the price.
    """
    before = sentence[max(0, start - _BEFORE_MENTION) : start]
    if _any_match(_THRESHOLD, before) or _any_match(_OTHER_SUBJECT, _around(sentence, start, end)):
        return False
    if role == "CAP":
        return not _PROGRESS.search(before) and _base_is_the_price(sentence[end:next_start])
    if not _is_about_delay(sentence):
        return False
    near = sentence[max(0, start - _ADJECTIVAL_REACH) : end + _ADJECTIVAL_REACH]
    wide = sentence[max(0, start - PERCENT_ROLE_WINDOW) : end + PERCENT_ROLE_WINDOW]
    has_day_phrase = (
        _any_match(_RATIO_DAILY, wide)
        or _ADJECTIVAL_DAILY.search(near)
        or _PENALTY_DAILY_ADJECTIVE.search(sentence)
    )
    return bool(has_day_phrase) and not _any_match(_CAP_ROLE, before)


def _drop_unreliable_roles(
    sentence: str,
    in_sentence: list[PercentMention],
    spans: list[tuple[int, int]],
    roles: list[str | None],
) -> None:
    """Withdraw the role of a figure that cannot be trusted with it (in place)."""
    for index, mention in enumerate(in_sentence):
        role = roles[index]
        if role is None:
            continue
        next_start = spans[index + 1][0] if index + 1 < len(spans) else len(sentence)
        reach = _RATIO_REACH if mention.ratio else _PERIOD_REACH
        reliable = (
            mention.readable
            and not _period_follows(sentence, spans[index][1], next_start, reach)
            and (
                not mention.ratio
                or (role == "DAILY" and _ratio_is_a_clean_rate(sentence, spans, index))
            )
            and (
                not mention.new_form
                or mention.ratio
                or _new_form_is_trustworthy(sentence, *spans[index], next_start, role)
            )
        )  # "0.5% per week" is neither a daily rate nor a total cap; a ratio is only ever a daily rate
        if not reliable:
            roles[index] = None


def penalty_rate_and_cap(text: str) -> tuple[float | None, float | None]:
    """(daily rate, cumulative cap) of a penalty clause, each as a fraction, or None.

    Only a sentence that itself names a penalty is read, so a liability limit, a retention or an
    advance payment in the next sentence is never taken for the penalty's cap. Inside it, each
    percentage takes the role of the term that claims it ("diario", "por día", "per day" for the
    daily rate; "tope", "máximo", "capped at", "not to exceed" for the cap). A percentage no term
    claims is not assigned. A figure with another period right behind it ("0.5% per week") has no
    role; a rate written as money per thousand of the price ("0,60 euros por cada 1.000 euros") counts
    only as an explicitly daily rate and only when it is the sentence's only amount; a "N por 100" that
    may start a quantity has no value. The first figure found for a role wins.
    """
    folded = fold(text)
    mentions = extract_rate_mentions(text)
    daily: float | None = None
    cap: float | None = None
    for sentence_start, sentence_end in _sentence_spans(folded):
        in_sentence = [m for m in mentions if sentence_start <= m.start < sentence_end]
        sentence = folded[sentence_start:sentence_end]
        if not in_sentence or not any(p.search(sentence) for p in _penalty_patterns()):
            continue
        spans = [(m.start - sentence_start, m.end - sentence_start) for m in in_sentence]
        roles = _roles_in_sentence(sentence, spans)
        _drop_unreliable_roles(sentence, in_sentence, spans, roles)
        for mention, role in zip(in_sentence, roles, strict=True):
            if role == "DAILY" and daily is None:
                daily = mention.value
            elif role == "CAP" and cap is None:
                cap = mention.value
    return daily, cap
