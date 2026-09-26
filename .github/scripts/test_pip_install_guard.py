import pathlib
import tempfile
import yaml
from pip_install_guard import is_allowed

def test_unpinned_package_reject():
    assert not is_allowed(".github/workflows/ci.yml", "pip install foo")

def test_ranged_ad_hoc_reject():
    assert not is_allowed(".github/workflows/ci.yml", 'pip install "foo>=1.0"')

def test_exact_pinned_baseline_allowed():
    assert is_allowed(".github/workflows/c2pro-product-control-guard.yml", 'python -m pip install --disable-pip-version-check "pyyaml==6.0.3"')

def test_same_exception_copied_reject():
    # Same command in different file should be rejected
    assert not is_allowed(".github/workflows/other.yml", 'python -m pip install --disable-pip-version-check "pyyaml==6.0.3"')

def test_requirements_install_allow():
    assert is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt")

def test_requirements_with_constraints_allow():
    assert is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt -c constraints.txt")

def test_editable_local_path_no_false_positive():
    # Editable install should not be flagged as ad-hoc
    assert is_allowed(".github/workflows/ci.yml", "pip install -e .")

def test_pip_bootstrap_classified():
    assert is_allowed(".github/workflows/ci.yml", "python -m pip install --upgrade pip")

def test_multiline_not_detected_by_simple_check():
    # Our simple scanner looks at raw lines; multiline may be split
    # We just ensure is_allowed works
    assert is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt")

def test_pinned_direct_url_allowlisted():
    assert is_allowed(".github/workflows/ci.yml", 'pip install "https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl"')

if __name__ == "__main__":
    import sys
    tests = [
        test_unpinned_package_reject,
        test_ranged_ad_hoc_reject,
        test_exact_pinned_baseline_allowed,
        test_same_exception_copied_reject,
        test_requirements_install_allow,
        test_requirements_with_constraints_allow,
        test_editable_local_path_no_false_positive,
        test_pip_bootstrap_classified,
        test_multiline_not_detected_by_simple_check,
        test_pinned_direct_url_allowlisted,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed.append((t.__name__, e))
    if failed:
        for name, e in failed:
            print(f"FAIL {name}: {e}")
        sys.exit(1)
    print("ALL TESTS PASS")
