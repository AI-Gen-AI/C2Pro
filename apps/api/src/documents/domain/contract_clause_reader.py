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
    CLAUSE_TYPE_ORDER,
    CLAUSE_TYPE_TERMS,
    PERCENT_ROLE_TERMS,
    PERCENT_ROLE_WINDOW,
    PERCENT_WORDS,
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

_PERCENT_WORD_UNITS = "|".join(
    re.escape(word).replace(r"\ ", r"\s*") for word in sorted(PERCENT_WORDS, key=len, reverse=True)
)
_PERCENT_RE = re.compile(
    rf"(?<![\d.,])(\d(?:[\d.,]*\d)?)\s*(?:%|(?:{_PERCENT_WORD_UNITS})(?![a-z0-9]))"
)


@dataclass(frozen=True)
class PercentMention:
    value: float  # fraction: 0.001 is 0.1%
    start: int  # offsets in fold(text)
    end: int


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


def extract_percentages(text: str) -> list[PercentMention]:
    mentions: list[PercentMention] = []
    folded = fold(text)
    for match in _PERCENT_RE.finditer(folded):
        number = parse_percent_number(match.group(1))
        if number is not None:
            mentions.append(PercentMention(number / 100.0, match.start(), match.end()))
    return mentions


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


def penalty_rate_and_cap(text: str) -> tuple[float | None, float | None]:
    """(daily rate, cumulative cap) of a penalty clause, each as a fraction, or None.

    Only a sentence that itself names a penalty is read, so a liability limit, a retention or an
    advance payment in the next sentence is never taken for the penalty's cap. Inside it, each
    percentage takes the role of the term that claims it ("diario", "por día", "per day" for the
    daily rate; "tope", "máximo", "capped at", "not to exceed" for the cap). A percentage no term
    claims is not assigned. The first figure found for a role wins.
    """
    folded = fold(text)
    mentions = extract_percentages(text)
    daily: float | None = None
    cap: float | None = None
    for sentence_start, sentence_end in _sentence_spans(folded):
        in_sentence = [m for m in mentions if sentence_start <= m.start < sentence_end]
        sentence = folded[sentence_start:sentence_end]
        if not in_sentence or not any(p.search(sentence) for p in _penalty_patterns()):
            continue
        spans = [(m.start - sentence_start, m.end - sentence_start) for m in in_sentence]
        for mention, role in zip(in_sentence, _roles_in_sentence(sentence, spans), strict=True):
            if role == "DAILY" and daily is None:
                daily = mention.value
            elif role == "CAP" and cap is None:
                cap = mention.value
    return daily, cap
