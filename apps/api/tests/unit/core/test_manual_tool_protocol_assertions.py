"""Regression coverage for manual Tool protocol assertion semantics."""

import pytest

from tests.manual.test_tools_implementation import _assert_tool_protocol


class IncompleteTool:
    async def execute(self):
        return None

    def __call__(self):
        return None


def test_manual_tool_protocol_assertions_propagate():
    with pytest.raises(AssertionError):
        _assert_tool_protocol(IncompleteTool())
