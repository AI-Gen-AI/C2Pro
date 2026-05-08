# LangSmith Phase 2 - Gemini Implementation Report

## Summary

This report details the work completed for the EPIC-LANGSMITH-PHASE-2 instrumentation task and the blocking issue that prevents its completion. The core decorator and feedback endpoint have been implemented, but persistent authentication failures in the integration test environment are blocking further progress and validation.

## Completed Actions

1.  **Branch and Report Setup**:
    *   Created and switched to the `langsmith-phase2/gemini` branch.
    *   Created the `blackboard/langsmith-phase2/` directory for this report.

2.  **`@traced_llm_call` Decorator Implementation**:
    *   Created `apps/api/src/core/observability/langsmith_decorator.py` based on the reference implementation.
    *   Adapted the decorator to handle both `**kwargs` and `LLMRequest` objects, making it compatible with `LLMClient.generate`.
    *   Implemented helper functions (`_extract_tenant_id`, `_extract_prompt`, etc.) to pull data from the `LLMRequest` object.

3.  **LLMClient Instrumentation**:
    *   Modified `apps/api/src/core/ai/llm_client.py`:
        *   Instantiated `LangSmithClient` and `AIUsageLogger`.
        *   Applied the `@traced_llm_call(task_type="llm_generation")` decorator to the `LLMClient.generate` method.
        *   Added `project_id` to the `LLMRequest` dataclass.

4.  **EU-Residency Attribute Filtering**:
    *   Implemented `LLM_SPAN_ATTRIBUTE_ALLOWLIST` in `apps/api/src/core/ai/langsmith_client.py`.
    *   Modified the `build_metadata` method to filter attributes against this allowlist, ensuring only approved data is sent.

5.  **AI Feedback Endpoint (`/api/v1/ai/feedback`)**:
    *   The bounded context at `apps/api/src/ai_feedback/` was found to be partially implemented.
    *   Corrected the `AIFeedbackService` in `apps/api/src/ai_feedback/service.py` to correctly instantiate `LangSmithClient` and use its `enabled` property.
    *   Added a placeholder `create_feedback` method to `LangSmithClient`.
    *   Updated the main FastAPI app in `apps/api/src/main.py` to use the router from the `ai_feedback` bounded context and removed the conflicting old router.

6.  **Unit and Integration Tests**:
    *   Created `apps/api/tests/unit/core/observability/test_langsmith_decorator.py`.
    *   Created `apps/api/tests/integration/ai_feedback/test_feedback_endpoint.py`.
    *   Wrote several tests to cover the decorator's functionality and the feedback endpoint.

## Blocker: Persistent Test Authentication Failure

The primary blocker is a persistent `401 Unauthorized` error when running integration tests that require an authenticated user.

*   **Symptom**: `test_submit_feedback_success` consistently fails with `assert 401 == 202`.
*   **Root Cause**: The application's `TenantIsolationMiddleware` runs before the tests and attempts to validate the user's tenant by calling `lookup_tenant_by_id`. This function tries to query a non-existent `auth_bootstrap` schema in the test database.
*   **Log Evidence**: `tenant_validation_error        error=Auth bootstrap fallback blocked by policy` and `schema "auth_bootstrap" does not exist`.

### Unsuccessful Remediation Attempts

A significant amount of time was spent trying to resolve this testing issue, indicating a fundamental problem with the test environment setup that is beyond my current capabilities to diagnose. The attempts included:

1.  **Debugging `conftest.py`**:
    *   Fixed numerous initial errors: `Duplicated timeseries in CollectorRegistry`, `NameError`, `ImportError`, `ValueError` (password length), and `TypeError` (datetime timezone).
    *   Correctly configured the database connection to use `localhost` and to idempotently create the `c2pro_test` database.
2.  **Mocking Authentication (Failed Attempts)**:
    *   **Attempt 1: Mocking `bootstrap_lookup_user_by_email`**: This was too low-level and did not prevent the middleware from running its own lookups.
    *   **Attempt 2: Mocking `AuthService.get_current_user` with `app.dependency_overrides`**: This also failed, suggesting the middleware's execution path is not affected by this override in the test client's context.
    *   **Attempt 3: Mocking `lookup_tenant_by_id` in `tenant_isolation.py`**: My final attempt was to patch the function directly called by the middleware. This also failed with the same `401` error, indicating the patch was not being applied as expected before the middleware's execution.

## Open Questions for Expert Review

1.  What is the correct and intended way to set up an authenticated test environment that satisfies the `TenantIsolationMiddleware`?
2.  Is there a specific environment variable or test configuration flag to disable the `auth_bootstrap` schema lookup for integration tests?
3.  Can an example be provided of a working integration test that uses the `authenticated_client` fixture and successfully calls a protected endpoint?

The core implementation work is largely complete, but cannot be validated until this testing blocker is resolved.
