from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "development"))

import validate_github_actions_storage_policy as policy


def test_actions_storage_policy_has_no_violations():
    assert policy.validate() == []


def test_storage_policy_bounds_transient_artifacts():
    assert policy.MAX_ARTIFACT_RETENTION_DAYS == 3


def test_storage_policy_does_not_admit_self_hosted_runner():
    assert "self-hosted" not in policy.STANDARD_PUBLIC_GITHUB_HOSTED_RUNNERS
