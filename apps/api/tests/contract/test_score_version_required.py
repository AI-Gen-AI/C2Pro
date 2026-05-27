"""
CI contract test — every Coherence Pydantic model must carry
score_version typed as Literal["coherence-v1", "coherence-v2"].

Suite ID: TS-CONTRACT-COH-VERSION-001
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Literal, get_args, get_origin

import pytest
import pydantic


def _collect_coherence_models() -> list[type[pydantic.BaseModel]]:
    """
    Walk src.coherence.** and collect all non-abstract Pydantic BaseModel
    subclasses whose __name__ contains 'Coherence' or 'Dashboard'.

    Uses identity deduplication to avoid collecting the same class multiple
    times when it is imported from multiple modules.
    """
    import src.coherence as coherence_pkg

    found: list[type[pydantic.BaseModel]] = []

    # Walk all submodules
    pkg_path = getattr(coherence_pkg, "__path__", [])
    for _finder, modname, _ispkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix="src.coherence.",
        onerror=lambda _name: None,
    ):
        try:
            module = importlib.import_module(modname)
        except Exception:
            continue

        # Only collect from the primary models module and its direct ancestors.
        # Domain sub-modules (rules, rule_engine) define their own CoherenceResult
        # stubs that are not the public API surface — exclude them.
        # The canonical models are in src.coherence.models.
        _CANONICAL_MODULES = {
            "src.coherence.models",
        }
        if modname not in _CANONICAL_MODULES:
            # Still collect DashboardSummary from wherever it's defined
            pass

        for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
            # Only look at classes defined in this specific module (not re-imports)
            if obj.__module__ != modname:
                continue
            if (
                issubclass(obj, pydantic.BaseModel)
                and obj is not pydantic.BaseModel
                and not obj.__name__.startswith("_")
                and ("Coherence" in obj.__name__ or "Dashboard" in obj.__name__)
            ):
                found.append(obj)

    # Deduplicate by identity
    seen: set[int] = set()
    unique: list[type[pydantic.BaseModel]] = []
    for cls in found:
        if id(cls) not in seen:
            seen.add(id(cls))
            unique.append(cls)

    return unique


_MODELS = _collect_coherence_models()

if not _MODELS:
    pytest.skip(
        "No Coherence/Dashboard Pydantic models discovered — check src.coherence package path.",
        allow_module_level=True,
    )

# Modules that contain internal/domain-only CoherenceResult classes
# that are NOT the public API surface — they don't carry score_version.
_INTERNAL_MODULES: frozenset[str] = frozenset(
    {
        "src.coherence.domain.coherence_rule_engine",
        "src.coherence.domain.legal_rules",
        "src.coherence.domain.quality_rules",
    }
)

# Models that are exempt from the score_version requirement
# (they're not result-carrier models — they're request/command models or sub-payloads)
_EXEMPT_MODELS: frozenset[str] = frozenset(
    {
        "CoherenceCalculationResult",  # uses legacy int scores — Phase G
        "CalculateCoherenceCommand",
        "CategoryBreakdown",
        "CoherenceCategory",
        "CoherenceSpanAttributes",
        "CoherenceAlertSpanAttributes",
        "CategoryV2",
        "GlobalV2",
        "CoherenceV2Payload",
        "CoherenceGraphState",
        "EvaluationConfig",
    }
)

# The two canonical score_version Literal values
_EXPECTED_LITERAL_VALUES: frozenset[str] = frozenset({"coherence-v1", "coherence-v2"})

# Models that must specifically have score_version (result-carrier models)
_MUST_HAVE_SCORE_VERSION: frozenset[str] = frozenset(
    {
        "CoherenceResult",
        "EnrichedCoherenceResult",
        "DashboardSummary",
    }
)


@pytest.mark.parametrize("model_cls", _MODELS, ids=lambda c: c.__name__)
def test_coherence_model_score_version_field(
    model_cls: type[pydantic.BaseModel],
) -> None:
    """
    TS-CONTRACT-COH-VERSION-001: Any Coherence/Dashboard Pydantic model that is
    a result carrier MUST have score_version typed as
    Literal["coherence-v1", "coherence-v2"] (or Literal[...] | None for nullable).

    Models not in _MUST_HAVE_SCORE_VERSION are skipped (they may be command/sub-models).
    """
    name = model_cls.__name__

    # Skip internal domain-only models that are not the public API surface
    model_module = getattr(model_cls, "__module__", "")
    if model_module in _INTERNAL_MODULES:
        pytest.skip(
            f"{name} from {model_module} is an internal domain model — skip score_version check"
        )

    if name not in _MUST_HAVE_SCORE_VERSION:
        pytest.skip(f"{name} is not a result-carrier model — skip score_version check")

    fields = model_cls.model_fields
    assert "score_version" in fields, (
        f"{name} is missing a 'score_version' field. "
        "All result-carrier Coherence models must carry score_version."
    )

    annotation = fields["score_version"].annotation
    literal_values = _extract_literal_values(annotation)

    assert literal_values is not None, (
        f"{name}.score_version annotation {annotation!r} is not a Literal type. "
        "Must be Literal['coherence-v1', 'coherence-v2'] or that union with None."
    )

    assert literal_values >= _EXPECTED_LITERAL_VALUES, (
        f"{name}.score_version Literal values {literal_values!r} must include "
        f"both 'coherence-v1' and 'coherence-v2'. "
        f"Legacy values like 'v0_flag_based' or 'v1_exponential_decay' are not allowed."
    )

    # Ensure legacy values are NOT in the type
    legacy_values = {"v0_flag_based", "v1_exponential_decay", "v1", "v2_evidence_aware"}
    overlap = literal_values & legacy_values
    assert not overlap, (
        f"{name}.score_version still contains legacy values: {overlap!r}. "
        "Remove all legacy values; use only 'coherence-v1' and 'coherence-v2'."
    )


def _extract_literal_values(annotation: object) -> frozenset[str] | None:
    """
    Given an annotation that may be Literal[...] or Literal[...] | None,
    return the frozenset of string literal values, or None if not a Literal.
    """
    if annotation is None:
        return None

    # Handle X | None (Union)
    origin = get_origin(annotation)
    args = get_args(annotation)

    # typing.Union[Literal[...], None] or X | None in Python 3.10+
    if origin is type(None):
        return None

    if args:
        # Could be Union (include None) or Literal
        if get_origin(annotation) is Literal:
            return frozenset(a for a in args if isinstance(a, str))

        # Union-like: collect from non-None branches
        collected: set[str] = set()
        found_literal = False
        for arg in args:
            if arg is type(None):
                continue
            if get_origin(arg) is Literal:
                found_literal = True
                collected.update(a for a in get_args(arg) if isinstance(a, str))
            elif arg is type(None):
                pass
            else:
                # Direct Literal check for Python 3.10+ union syntax
                sub_origin = get_origin(arg)
                if sub_origin is Literal:
                    found_literal = True
                    collected.update(a for a in get_args(arg) if isinstance(a, str))

        if found_literal:
            return frozenset(collected)

    # Check if it's directly Literal
    if get_origin(annotation) is Literal:
        return frozenset(a for a in get_args(annotation) if isinstance(a, str))

    return None
