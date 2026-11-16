"""WBS 2.1: bounded but lossless N4 source-window inventory."""
from __future__ import annotations

from hashlib import sha256

import pytest

from src.analysis.domain.n4_source_windows import plan_n4_source_windows


@pytest.mark.parametrize("size", [1, 17, 500, 13_000, 100_000])
def test_all_source_codepoints_are_covered_once_without_truncation(size: int):
    source = ("§2.5.5 complex exception shall apply; " * 5000)[:size]
    windows = plan_n4_source_windows(
        source, revision_id="document-revision-1",
        max_context_chars=1200, overlap_chars=60,
    )
    assert "".join(w.core_text for w in windows) == source
    assert all(w.context_chars <= 1200 for w in windows)
    assert all(w.revision_id == "document-revision-1" for w in windows)
    assert all(w.source_sha256 == sha256(source.encode()).hexdigest() for w in windows)
    assert all(w.core_start == (windows[i - 1].core_end if i else 0)
               for i, w in enumerate(windows))
    assert windows[-1].core_end == size
    assert all(w.context_text == source[w.context_start:w.context_end] for w in windows)


def test_context_overlaps_sections_at_seams_without_skipping_exception():
    source = "A" * 735 + "\n§9.6 ten percent versus (5%) exception applies\n" + "B" * 2000
    windows = plan_n4_source_windows(
        source, max_context_chars=500, overlap_chars=60,
    )
    assert "".join(w.core_text for w in windows) == source
    assert "§9.6" in "".join(w.core_text for w in windows)
    assert any("§9.6" in w.context_text for w in windows)
    assert len(windows) > 3


def test_deterministic_windows_allow_resume_by_digest_and_ordinal():
    source = "\n\n".join(
        f"Section {i}: The contractor shall comply with requirement {i}." for i in range(300)
    )
    a = plan_n4_source_windows(source, revision_id="r3", max_context_chars=1000)
    b = plan_n4_source_windows(source, revision_id="r3", max_context_chars=1000)
    assert a == b
    assert a[0].context_sha256 == sha256(a[0].context_text.encode()).hexdigest()
    assert a != plan_n4_source_windows(source + "new revision", revision_id="r4")


@pytest.mark.parametrize("bad", ["", "   \n\t", None])
def test_unreadable_text_never_becomes_empty_success(bad):
    with pytest.raises(ValueError, match="unavailable"):
        plan_n4_source_windows(bad)


@pytest.mark.parametrize("kwargs", [
    {"max_context_chars": 199},
    {"max_context_chars": 400, "overlap_chars": -1},
    {"max_context_chars": 400, "overlap_chars": 200},
])
def test_invalid_window_config_fails_closed(kwargs):
    with pytest.raises(ValueError):
        plan_n4_source_windows("contract source text", **kwargs)


def test_do_not_drop_one_long_unbroken_clause():
    source = "X" * 45_000
    windows = plan_n4_source_windows(source, max_context_chars=900, overlap_chars=80)
    assert "".join(w.core_text for w in windows) == source
    assert all(w.core_end > w.core_start for w in windows)
