"""Clause anchor resolver for ADR-016 L1 structural diff.

TS-UT-CI-ANCH-001 / TS-UT-CI-IDENT-001

Cross-revision clause identity is resolved fail-closed:

1. ``exact_content`` - identical normalized clause text is deterministic
   continuity. Text that is identical apart from the source number in front of
   it is a renumbering. Duplicated text is paired only when both revisions hold
   the same number of copies.
2. ``source_identifier`` - a clause number read from the clause's *own source
   text* (``4.2``, ``Clause 4.2``, ``Article 17``, ``Annex III.2``) is
   deterministic identity only when it occurs once on each side, the revision
   pair shows no renumbering, and the two texts are still recognisably the same
   clause (similarity >= ``fuzzy_threshold``). Once any clause is observed
   renumbered, numbers are not identity for that pair.
3. ``similarity_candidate`` - a candidate above ``fuzzy_threshold`` that is the
   only one in both directions is proposed for review; it never establishes
   identity.
4. A clause with more than one candidate is ambiguous and stays unpaired.
5. A shared stable number whose text was substantially rewritten, and for which
   no similar counterpart exists, is proposed for review, never asserted.

``Clause.clause_code`` is never identity evidence: ingestion assigns positional
``AUTO-NNN`` codes, and a code is only provably source-derived when it is read
from the clause text itself.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.change_intelligence.domain.contracts import MatchBasis
from src.documents.domain.models import Clause

_NUMBER = r"\d{1,3}(?:\.\d{1,3}){0,6}"
_ROMAN = r"[ivxlcdm]{1,8}(?:\.\d{1,3}){0,6}"
_ORDINAL = r"primera|segunda|tercera|cuarta|quinta|sexta|septima|octava|novena|decima"
_KEYWORD_LABEL = re.compile(
    r"^(?P<keyword>clause|clausula|article|articulo|section|seccion|annex|anexo|estipulacion)"
    rf"\s+(?P<number>{_NUMBER}|{_ROMAN}|{_ORDINAL})\b"
)
_ORDINAL_LABEL = re.compile(rf"^(?P<number>{_ORDINAL})\b(?=\s*[.:\-–])")
# A bare number is a heading only when punctuated ("2." "2)" "2 -") or multi-level
# ("5.2 "), so a clause that merely starts with "30 days" is not mistaken for one.
_MULTI_LEVEL_LABEL = re.compile(r"^(?P<number>\d{1,3}(?:\.\d{1,3}){1,6})\.?(?=\s)")
_SINGLE_LABEL = re.compile(r"^(?P<number>\d{1,3})(?:\.|\)|\s*[-–])(?=\s|$)")
_LABEL_TRAILER = re.compile(r"^[\s.:)\-–]+")


@dataclass(frozen=True)
class AnchorMatch:
    old: Clause
    new: Clause
    anchor: str
    match_confidence: float
    needs_review: bool
    basis: MatchBasis = "exact_content"
    rationale: str = ""


@dataclass(frozen=True)
class AnchorResolution:
    matched: list[AnchorMatch]
    unmatched_old: list[Clause]
    unmatched_new: list[Clause]
    # Subsets of the unmatched lists whose identity is ambiguous rather than absent.
    ambiguous_old: list[Clause] = field(default_factory=list)
    ambiguous_new: list[Clause] = field(default_factory=list)


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def split_source_label(text: str | None) -> tuple[str | None, str]:
    """Return the clause number written at the start of the source text, and the body.

    The label is evidence only because it is read from the clause's verbatim
    source span. It is folded (case, accents, trailing dot) for comparison.
    """
    normalized = _normalize_text(text)
    folded = _fold(normalized)
    keyword = _KEYWORD_LABEL.match(folded)
    if keyword is not None:
        label = f"{keyword.group('keyword')} {keyword.group('number').rstrip('.')}"
        end = keyword.end()
    else:
        bare = (
            _ORDINAL_LABEL.match(folded)
            or _MULTI_LEVEL_LABEL.match(folded)
            or _SINGLE_LABEL.match(folded)
        )
        if bare is None:
            return None, normalized
        label = bare.group("number").rstrip(".")
        end = bare.end()
    # Folding can lengthen a prefix (e.g. ligatures); map the cut back onto the
    # original text. Labels are short, so this scans only a few characters.
    cut = 0
    while cut < len(normalized) and len(_fold(normalized[:cut])) < end:
        cut += 1
    return label, _LABEL_TRAILER.sub("", normalized[cut:])


def display_anchor(clause: Clause) -> str:
    """Human locator inside one revision; never cross-revision identity."""
    label, _ = split_source_label(clause.full_text)
    return label or clause.clause_code


@dataclass(frozen=True)
class _View:
    index: int
    clause: Clause
    text: str
    label: str | None
    body: str


def _view(index: int, clause: Clause) -> _View:
    label, body = split_source_label(clause.full_text)
    return _View(index, clause, _normalize_text(clause.full_text), label, body)


def _ratio(old: _View, new: _View) -> float:
    if not old.body and not new.body:
        return 0.0
    return SequenceMatcher(a=old.body, b=new.body).ratio()


def _groups(views: list[_View], key: Callable[[_View], str | None]) -> dict[str, list[_View]]:
    grouped: dict[str, list[_View]] = defaultdict(list)
    for view in views:
        value = key(view)
        if value:
            grouped[value].append(view)
    return grouped


class _Pairing:
    """Mutable working set; each clause is paired at most once."""

    def __init__(self, old: list[Clause], new: list[Clause]) -> None:
        self.old = [_view(index, clause) for index, clause in enumerate(old)]
        self.new = [_view(index, clause) for index, clause in enumerate(new)]
        self.matched: list[AnchorMatch] = []

    def pair(
        self,
        old: _View,
        new: _View,
        *,
        basis: MatchBasis,
        confidence: float,
        rationale: str,
        needs_review: bool = False,
    ) -> None:
        self.old.remove(old)
        self.new.remove(new)
        self.matched.append(
            AnchorMatch(
                old=old.clause,
                new=new.clause,
                anchor=new.label or old.label or new.clause.clause_code,
                match_confidence=confidence,
                needs_review=needs_review,
                basis=basis,
                rationale=rationale,
            )
        )

    def unique_pairs(self, key: Callable[[_View], str | None]) -> list[tuple[str, _View, _View]]:
        new_groups = _groups(self.new, key)
        return [
            (value, olds[0], new_groups[value][0])
            for value, olds in _groups(self.old, key).items()
            if len(olds) == 1 and len(new_groups.get(value, [])) == 1
        ]


def resolve_clause_anchors(
    old: list[Clause],
    new: list[Clause],
    *,
    fuzzy_threshold: float = 0.8,
) -> AnchorResolution:
    """Pair clauses across revisions without ever trusting positional codes."""

    work = _Pairing(old, new)

    # 1. Identical clause text; duplicates pair only when both sides hold equal counts.
    new_by_text = _groups(work.new, lambda view: view.text)
    for text, olds in _groups(work.old, lambda view: view.text).items():
        news = new_by_text.get(text, [])
        if len(olds) == len(news):
            for old_view, new_view in zip(olds, news, strict=True):
                work.pair(
                    old_view,
                    new_view,
                    basis="exact_content",
                    confidence=1.0,
                    rationale="normalized clause text is identical in both revisions",
                )

    # 2. Identical body under a different source number: a renumbering.
    renumbered = False
    for _, old_view, new_view in work.unique_pairs(lambda view: view.body):
        renumbered = renumbered or old_view.label != new_view.label
        work.pair(
            old_view,
            new_view,
            basis="exact_content",
            confidence=1.0,
            rationale=(
                "clause text is identical; source identifier changed from "
                f"{old_view.label or 'none'} to {new_view.label or 'none'}"
            ),
        )

    # 3. Source identifiers are identity only while numbering is demonstrably stable
    #    and the text is still recognisably the same clause.
    if not renumbered:
        for label, old_view, new_view in work.unique_pairs(lambda view: view.label):
            if _ratio(old_view, new_view) < fuzzy_threshold:
                continue
            work.pair(
                old_view,
                new_view,
                basis="source_identifier",
                confidence=1.0,
                rationale=(
                    f"source identifier {label} appears once in each revision's clause "
                    "text and no renumbering was observed between the revisions"
                ),
            )

    # 4. Similarity proposes a review candidate only when it is unique both ways.
    candidates = [
        (old_view, new_view, ratio)
        for old_view in work.old
        for new_view in work.new
        if (ratio := _ratio(old_view, new_view)) >= fuzzy_threshold
    ]
    old_counts: dict[int, int] = defaultdict(int)
    new_counts: dict[int, int] = defaultdict(int)
    for old_view, new_view, _ in candidates:
        old_counts[old_view.index] += 1
        new_counts[new_view.index] += 1
    ambiguous_old: set[int] = set()
    ambiguous_new: set[int] = set()
    for old_view, new_view, ratio in candidates:
        if old_counts[old_view.index] == 1 and new_counts[new_view.index] == 1:
            work.pair(
                old_view,
                new_view,
                basis="similarity_candidate",
                confidence=ratio,
                needs_review=True,
                rationale=(
                    f"proposed by text similarity {ratio:.2f} as the only candidate in both "
                    "revisions; identity is not established and requires review"
                ),
            )
        else:
            ambiguous_old.add(old_view.index)
            ambiguous_new.add(new_view.index)

    # 5. A stable number left on both sides after a substantial rewrite is only a proposal.
    if not renumbered:
        for label, old_view, new_view in work.unique_pairs(lambda view: view.label):
            if old_view.index in ambiguous_old or new_view.index in ambiguous_new:
                continue
            ratio = _ratio(old_view, new_view)
            work.pair(
                old_view,
                new_view,
                basis="source_identifier",
                confidence=ratio,
                needs_review=True,
                rationale=(
                    f"source identifier {label} appears once in each revision but the "
                    f"clause text was substantially rewritten (similarity {ratio:.2f}); "
                    "identity is not established and requires review"
                ),
            )

    return AnchorResolution(
        matched=work.matched,
        unmatched_old=[view.clause for view in work.old],
        unmatched_new=[view.clause for view in work.new],
        ambiguous_old=[view.clause for view in work.old if view.index in ambiguous_old],
        ambiguous_new=[view.clause for view in work.new if view.index in ambiguous_new],
    )


__all__ = [
    "AnchorMatch",
    "AnchorResolution",
    "display_anchor",
    "resolve_clause_anchors",
    "split_source_label",
]
