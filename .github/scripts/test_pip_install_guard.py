import pathlib
import tempfile
import yaml
from pip_install_guard import is_allowed, scan_file

def test_unpinned_package_reject():
    assert not is_allowed(".github/workflows/ci.yml", "pip install foo")

def test_ranged_ad_hoc_reject():
    assert not is_allowed(".github/workflows/ci.yml", 'pip install "foo>=1.0"')

def test_exact_pinned_baseline_allowed():
    assert is_allowed(".github/workflows/c2pro-product-control-guard.yml", 'python -m pip install --disable-pip-version-check "pyyaml==6.0.3"')

def test_same_exception_copied_reject():
    assert not is_allowed(".github/workflows/other.yml", 'python -m pip install --disable-pip-version-check "pyyaml==6.0.3"')

def test_requirements_install_allow():
    assert is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt")

def test_requirements_with_constraints_allow():
    assert is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt -c constraints.txt")

def test_requirements_append_bypass_reject():
    assert not is_allowed(".github/workflows/ci.yml", "pip install -r requirements.txt evil-package")

def test_constraint_bypass_reject():
    assert not is_allowed(".github/workflows/ci.yml", "pip install evil-package -c constraints.txt")

def test_baseline_substring_bypass_reject():
    # exact baseline is pip install python-magic, adding evil-package should reject
    assert not is_allowed(".github/actions/setup-python-backend/action.yml", "pip install python-magic evil-package")

def test_editable_local_allowed():
    assert is_allowed(".github/workflows/ci.yml", "pip install -e .")
    assert is_allowed(".github/workflows/ci.yml", "pip install -e ./package")

def test_editable_remote_reject():
    assert not is_allowed(".github/workflows/ci.yml", "pip install -e git+https://github.com/example/repo.git")
    assert not is_allowed(".github/workflows/ci.yml", "pip install -e https://example.com/pkg.tar.gz")

def test_pip_bootstrap_classified():
    assert is_allowed(".github/workflows/ci.yml", "python -m pip install --upgrade pip")

def test_pinned_direct_url_allowlisted():
    assert is_allowed(".github/workflows/ci.yml", 'pip install "https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl"')

def test_multiline_ad_hoc_red():
    yaml_content = """
name: test
on: push
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pip install foo
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(yaml_content)
        f_path = pathlib.Path(f.name)
    try:
        findings, parse_err = scan_file(f_path)
        assert not parse_err
        assert len(findings) == 1
        # Should be detected as violation via is_allowed
        line = findings[0][1]
        assert not is_allowed("temp.yml", line)
    finally:
        f_path.unlink()

def test_multiline_continuation_red():
    yaml_content = """
name: test
on: push
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pip install \\
            foo
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(yaml_content)
        f_path = pathlib.Path(f.name)
    try:
        findings, parse_err = scan_file(f_path)
        assert not parse_err
        # The run contains pip install \\ foo, should still detect
        # At minimum, findings non-empty
        assert len(findings) >= 1
    finally:
        f_path.unlink()

def test_multiline_canonical_green():
    yaml_content = """
name: test
on: push
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pip install -r requirements.txt
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(yaml_content)
        f_path = pathlib.Path(f.name)
    try:
        findings, parse_err = scan_file(f_path)
        assert not parse_err
        assert len(findings) == 1
        line = findings[0][1]
        assert is_allowed("temp.yml", line)
    finally:
        f_path.unlink()

if __name__ == "__main__":
    import sys
    tests = [
        test_unpinned_package_reject,
        test_ranged_ad_hoc_reject,
        test_exact_pinned_baseline_allowed,
        test_same_exception_copied_reject,
        test_requirements_install_allow,
        test_requirements_with_constraints_allow,
        test_requirements_append_bypass_reject,
        test_constraint_bypass_reject,
        test_baseline_substring_bypass_reject,
        test_editable_local_allowed,
        test_editable_remote_reject,
        test_pip_bootstrap_classified,
        test_pinned_direct_url_allowlisted,
        test_multiline_ad_hoc_red,
        test_multiline_continuation_red,
        test_multiline_canonical_green,
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
