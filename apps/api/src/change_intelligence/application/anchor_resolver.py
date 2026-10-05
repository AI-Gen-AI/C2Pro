"""Clause anchor resolver for ADR-016 L1 structural diff.

TS-UT-CI-ANCH-001 / TS-UT-CI-IDENT-001

Cross-revision clause identity is resolved fail-closed:

1. ``exact_content`` - identical normalized clause text is deterministic
   continuity. Text that is identical apart from the source number in front of
   it is a renumbering, but only when that text occurs once in each revision.
   Duplicated text is paired only when both revisions hold the same number of
   identical copies, which asserts no change.
2. ``source_identifier`` - a clause number read from the clause's *own source
   text* (``4.2``, ``Clause 4.2``, ``Article 17``, ``Annex III.2``) is
   deterministic identity only when it occurs exactly once in each revision,
   the revision pair shows no renumbering, the two texts are still recognisably
   the same clause (similarity >= ``fuzzy_threshold``) and neither clause has
   any other similar candidate. Once any clause is observed renumbered, numbers
   are not identity for that pair. A heading number must be followed by a
   capitalised heading or sentence; amounts, percentages, list items and
   cross-references ("Clause 14.1 shall not apply...") are not identifiers.
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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import cached_property

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
# A heading number is followed by a heading or sentence, never by a unit or amount.
_NON_HEADING_START = frozenset("%‰€$£")


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
    # Set when similarity resolution was not attempted, e.g. the comparison budget ran out.
    unresolved_reason: str | None = None


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
        # "1.000.000" or "04.10" are amounts and dates, not clause numbering.
        if any(len(part) > 1 and part.startswith("0") for part in label.split(".")):
            return None, normalized
    # Folding can lengthen a prefix (e.g. ligatures); map the cut back onto the
    # original text. Labels are short, so this scans only a few characters.
    cut = 0
    while cut < len(normalized) and len(_fold(normalized[:cut])) < end:
        cut += 1
    body = _LABEL_TRAILER.sub("", normalized[cut:])
    # "Clause 14.1 shall not apply", "2) the contractor", "1.5 million", "12.5 %":
    # a reference, list item or quantity continues the sentence instead of
    # introducing a heading, so the number is not this clause's identifier.
    if body and (body[0].islower() or body[0] in _NON_HEADING_START):
        return None, normalized
    return label, body


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

    @cached_property
    def tokens(self) -> tuple[str, ...]:
        return tuple(self.body.split())


def _views(clauses: list[Clause]) -> list[_View]:
    """Parse each clause once; a number repeated inside a revision identifies nothing."""
    parsed = [split_source_label(clause.full_text) for clause in clauses]
    label_counts: dict[str, int] = defaultdict(int)
    for label, _ in parsed:
        if label:
            label_counts[label] += 1
    return [
        _View(
            index,
            clause,
            _normalize_text(clause.full_text),
            label if label and label_counts[label] == 1 else None,
            body,
        )
        for index, (clause, (label, body)) in enumerate(zip(clauses, parsed, strict=True))
    ]


# difflib's autojunk heuristic only engages for sequences of at least 200 items.
_AUTOJUNK_MIN_LENGTH = 200


def _symmetric_ratio(a: Sequence[str], b: Sequence[str], floor: float = 0.0) -> float:
    """Order-independent ``SequenceMatcher`` ratio (the lower of both directions).

    Returns 0.0 early when the symmetric upper bounds already fall below ``floor``.
    """
    if not a or not b:
        return 0.0
    forward = SequenceMatcher(None, a, b, autojunk=False)
    if forward.real_quick_ratio() < floor or forward.quick_ratio() < floor:
        return 0.0
    ratio = forward.ratio()
    if ratio < floor:  # the lower of both directions cannot exceed it
        return ratio
    return min(ratio, SequenceMatcher(None, b, a, autojunk=False).ratio())


def _may_reach(old: _View, new: _View, floor: float) -> bool:
    """Cheap symmetric upper bounds: False means the pair cannot reach ``floor``."""
    def bound(a: Sequence[str], b: Sequence[str]) -> float:
        if not a or not b:
            return 0.0
        matcher = SequenceMatcher(None, a, b, autojunk=False)
        return 0.0 if matcher.real_quick_ratio() < floor else matcher.quick_ratio()

    if bound(old.tokens, new.tokens) >= floor:
        return True
    short = len(old.body) < _AUTOJUNK_MIN_LENGTH and len(new.body) < _AUTOJUNK_MIN_LENGTH
    return short and bound(old.body, new.body) >= floor


def _ratio(old: _View, new: _View, floor: float = 0.0) -> float:
    """Symmetric similarity of two clause bodies, so diff(V1, V2) and diff(V2, V1) agree.

    The previous character-level ``SequenceMatcher`` treated frequent characters
    as junk from 200 characters on and was order-dependent: a near-identical long
    clause scored 0.46 one way and 0.20 the other. Long bodies are compared by
    words, which stays cheap and stable. Short bodies, which autojunk never
    touched, also keep their character-level score; a higher score can only add
    a review candidate or an ambiguity, never a deterministic pairing.
    """
    ratio = _symmetric_ratio(old.tokens, new.tokens, floor)
    if len(old.body) < _AUTOJUNK_MIN_LENGTH and len(new.body) < _AUTOJUNK_MIN_LENGTH:
        ratio = max(ratio, _symmetric_ratio(old.body, new.body, floor))
    return ratio


def _groups(views: list[_View], key: Callable[[_View], str | None]) -> dict[str, list[_View]]:
    grouped: dict[str, list[_View]] = defaultdict(list)
    for view in views:
        value = key(view)
        if value:
            grouped[value].append(view)
    return grouped


def _counts(views: list[_View], key: Callable[[_View], str | None]) -> dict[str, int]:
    return {value: len(group) for value, group in _groups(views, key).items()}


# Resource guard, not an identity threshold: at most this many full similarity
# computations per diff. Pairs pruned by the cheap upper bounds are free, so this is
# only reached when many unpaired clauses are mutually similar. Exceeding it never
# pairs anything; every unpaired clause is returned for review instead.
_MAX_FULL_COMPARISONS = 1000
_BUDGET_EXHAUSTED = (
    "too many mutually similar unpaired clauses to resolve identity within the "
    "comparison budget; no pairing is asserted and the change requires review"
)

_Edge = tuple[_View, _View, float]


def _candidates(old: list[_View], new: list[_View], threshold: float) -> list[_Edge] | None:
    """Similarity candidate edges over the unpaired clauses; None when over budget."""
    edges: list[_Edge] = []
    comparisons = 0
    for old_view in old:
        for new_view in new:
            if not _may_reach(old_view, new_view, threshold):
                continue
            comparisons += 1
            if comparisons > _MAX_FULL_COMPARISONS:
                return None
            ratio = _ratio(old_view, new_view, threshold)
            if ratio >= threshold:
                edges.append((old_view, new_view, ratio))
    return edges


def _degrees(edges: list[_Edge]) -> tuple[dict[int, int], dict[int, int]]:
    old_degree: dict[int, int] = defaultdict(int)
    new_degree: dict[int, int] = defaultdict(int)
    for old_view, new_view, _ in edges:
        old_degree[old_view.index] += 1
        new_degree[new_view.index] += 1
    return old_degree, new_degree


class _Pairing:
    """Mutable working set; each clause is paired at most once."""

    def __init__(self, old: list[Clause], new: list[Clause]) -> None:
        self.old = _views(old)
        self.new = _views(new)
        # Uniqueness of a body is judged over the whole revision, not what is left
        # after earlier passes: boilerplate repeated in a revision identifies nothing.
        self.old_body_counts = _counts(self.old, lambda view: view.body)
        self.new_body_counts = _counts(self.new, lambda view: view.body)
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
    for body, old_view, new_view in work.unique_pairs(lambda view: view.body):
        if work.old_body_counts.get(body) != 1 or work.new_body_counts.get(body) != 1:
            continue
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

    # The similarity graph over what is still unpaired, computed once.
    graph = _candidates(work.old, work.new, fuzzy_threshold)
    if graph is None:
        return AnchorResolution(
            matched=work.matched,
            unmatched_old=[view.clause for view in work.old],
            unmatched_new=[view.clause for view in work.new],
            ambiguous_old=[view.clause for view in work.old],
            ambiguous_new=[view.clause for view in work.new],
            unresolved_reason=_BUDGET_EXHAUSTED,
        )

    # 3. Source identifiers are identity only while numbering is demonstrably stable
    #    and the text is still recognisably the same clause.
    if not renumbered:
        old_degree, new_degree = _degrees(graph)
        uncontested = {
            (old_view.index, new_view.index)
            for old_view, new_view, _ in graph
            if old_degree[old_view.index] == 1 and new_degree[new_view.index] == 1
        }
        for label, old_view, new_view in work.unique_pairs(lambda view: view.label):
            # Any competing similar clause on either side means the number alone
            # cannot decide which clause continued (e.g. an inserted clause reusing it).
            if (old_view.index, new_view.index) not in uncontested:
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
    unpaired_old = {view.index for view in work.old}
    unpaired_new = {view.index for view in work.new}
    candidates = [
        edge for edge in graph if edge[0].index in unpaired_old and edge[1].index in unpaired_new
    ]
    old_counts, new_counts = _degrees(candidates)
    ambiguous_old: set[int] = set()
    ambiguous_new: set[int] = set()
    for old_view, new_view, ratio in candidates:
        duplicated = (
            work.old_body_counts.get(old_view.body, 0) > 1
            or work.new_body_counts.get(new_view.body, 0) > 1
        )
        if not duplicated and old_counts[old_view.index] == 1 and new_counts[new_view.index] == 1:
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
