from src.coherence.graph.state import merge_coverage


def test_merge_coverage_or_semantics():
    a = {"LEGAL": False, "SCOPE": True}
    b = {"LEGAL": True, "BUDGET": False}
    merged = merge_coverage(a, b)
    assert merged["LEGAL"] is True
    assert merged["SCOPE"] is True
    assert merged["BUDGET"] is False


def test_merge_coverage_handles_empty():
    assert merge_coverage({}, {"TIME": True}) == {"TIME": True}
    assert merge_coverage({"TIME": True}, {}) == {"TIME": True}
