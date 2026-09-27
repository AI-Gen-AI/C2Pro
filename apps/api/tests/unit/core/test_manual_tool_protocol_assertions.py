"""Regression coverage for manual Tool protocol assertion semantics."""

import pytest

from tests.manual.test_tools_implementation import _assert_tool_protocol


def test_manual_tool_protocol_assertions_propagate():
    def incomplete_tool():
        return "unused"

    incomplete_tool.execute = incomplete_tool  # type: ignore[attr-defined]

    with pytest.raises(AssertionError):
        _assert_tool_protocol(incomplete_tool)
