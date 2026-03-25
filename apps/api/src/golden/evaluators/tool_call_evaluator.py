"""Tool call evaluator for validating tool invocations.

Validates that tools were called with correct arguments
and within specified call count bounds.
"""

from dataclasses import dataclass
from typing import Any

from golden.evaluators.base import EvaluationResult
from golden.schemas import ToolCallAssertion


@dataclass
class ActualToolCall:
    """Represents an actual tool call made during workflow execution.

    Attributes:
        tool_name: Name of the tool that was called
        arguments: Dictionary of arguments passed to the tool
    """

    tool_name: str
    arguments: dict[str, Any]


class ToolCallEvaluator:
    """Evaluator for tool call validation.

    Checks that:
    - Expected tools were called the required number of times
    - Required arguments were present
    - Forbidden arguments were not present
    - Call counts are within specified bounds
    """

    def evaluate(
        self,
        assertions: list[ToolCallAssertion],
        actual_calls: list[ActualToolCall],
    ) -> EvaluationResult:
        """Evaluate actual tool calls against expected assertions.

        Args:
            assertions: List of tool call assertions from the golden case
            actual_calls: List of actual tool calls made during execution

        Returns:
            EvaluationResult with pass/fail status and details
        """
        failures: list[str] = []
        assertion_results: list[dict[str, Any]] = []

        for assertion in assertions:
            result = self._evaluate_single_assertion(assertion, actual_calls)
            assertion_results.append(result)
            failures.extend(result["failures"])

        # Calculate score
        if not assertions:
            score = 1.0
        else:
            passed_assertions = sum(
                1 for r in assertion_results if not r["failures"]
            )
            score = passed_assertions / len(assertions)

        details = {
            "total_assertions": len(assertions),
            "total_actual_calls": len(actual_calls),
            "assertion_results": assertion_results,
        }

        return EvaluationResult(
            passed=len(failures) == 0,
            score=score,
            failures=failures,
            details=details,
        )

    def _evaluate_single_assertion(
        self,
        assertion: ToolCallAssertion,
        actual_calls: list[ActualToolCall],
    ) -> dict[str, Any]:
        """Evaluate a single tool call assertion.

        Args:
            assertion: The tool call assertion to check
            actual_calls: All actual tool calls

        Returns:
            Dictionary with assertion evaluation details and failures
        """
        failures: list[str] = []

        # Find all calls to this tool
        matching_calls = [
            call for call in actual_calls if call.tool_name == assertion.tool_name
        ]
        call_count = len(matching_calls)

        # Check call count bounds
        if call_count < assertion.min_calls:
            failures.append(
                f"Tool '{assertion.tool_name}' called {call_count} times, "
                f"minimum required is {assertion.min_calls}"
            )

        if assertion.max_calls is not None and call_count > assertion.max_calls:
            failures.append(
                f"Tool '{assertion.tool_name}' called {call_count} times, "
                f"maximum allowed is {assertion.max_calls}"
            )

        # Check arguments for each matching call
        for i, call in enumerate(matching_calls):
            arg_failures = self._check_arguments(assertion, call, i)
            failures.extend(arg_failures)

        return {
            "tool_name": assertion.tool_name,
            "expected_min_calls": assertion.min_calls,
            "expected_max_calls": assertion.max_calls,
            "actual_call_count": call_count,
            "failures": failures,
        }

    def _check_arguments(
        self,
        assertion: ToolCallAssertion,
        call: ActualToolCall,
        call_index: int,
    ) -> list[str]:
        """Check that a tool call has required args and lacks forbidden args.

        Args:
            assertion: The assertion defining required/forbidden args
            call: The actual tool call to check
            call_index: Index of this call (for error messages)

        Returns:
            List of failure messages for argument violations
        """
        failures = []
        actual_args = set(call.arguments.keys())

        # Check required arguments
        for required_arg in assertion.required_args:
            if required_arg not in actual_args:
                failures.append(
                    f"Tool '{assertion.tool_name}' call #{call_index + 1} "
                    f"missing required argument '{required_arg}'"
                )

        # Check forbidden arguments
        for forbidden_arg in assertion.forbidden_args:
            if forbidden_arg in actual_args:
                failures.append(
                    f"Tool '{assertion.tool_name}' call #{call_index + 1} "
                    f"contains forbidden argument '{forbidden_arg}'"
                )

        return failures
