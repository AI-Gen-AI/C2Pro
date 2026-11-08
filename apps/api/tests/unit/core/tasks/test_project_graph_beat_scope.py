"""Pilot Beat must dispatch only #714 ProjectGraph recovery when explicitly enabled."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from src.core.tasks.celery_app import select_beat_schedule

_KEY = "project-graph-trusted-projection-reconcile"


def test_default_schedule_is_unmodified():
    schedule = {
        _KEY: {"task": "project_graph.reconcile_trusted_projections", "schedule": 300.0},
        "hitl-resume-reconcile": {"task": "hitl_resume.reconcile", "schedule": 60.0},
    }
    assert select_beat_schedule(schedule, project_graph_only=False) is schedule


def test_pilot_schedule_only_contains_projectgraph_recovery():
    schedule = {
        _KEY: {"task": "project_graph.reconcile_trusted_projections", "schedule": 300.0},
        "hitl-resume-reconcile": {"task": "hitl_resume.reconcile", "schedule": 60.0},
    }
    actual = select_beat_schedule(schedule, project_graph_only=True)
    assert list(actual) == [_KEY]
    assert actual[_KEY]["schedule"] == 300.0
    assert schedule["hitl-resume-reconcile"]["schedule"] == 60.0


def test_pilot_schedule_fails_closed_without_required_entry():
    with pytest.raises(RuntimeError, match="PROJECT_GRAPH_BEAT_ENTRY_MISSING"):
        select_beat_schedule({"hitl": {}}, project_graph_only=True)


def test_pilot_environment_actually_restricts_loaded_celery_app():
    code = (
        "from src.core.tasks.celery_app import celery_app; "
        "print('BEAT_KEYS=' + ','.join(sorted(celery_app.conf.beat_schedule)))"
    )
    env = dict(os.environ, C2PRO_BEAT_PROJECTGRAPH_ONLY="1")
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=35,
    )
    keys = [
        line.split("=", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("BEAT_KEYS=")
    ]
    assert keys == [_KEY]
