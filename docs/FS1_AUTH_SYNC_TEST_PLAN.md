# Frontend Sprint 1 - Test Plan: AuthSync Component

**Component:** `AuthSync` Provider
**Objective:** Validate the component's contract and behavior for synchronizing authentication state from Clerk to the application's global state, resolving critical architectural flags (FLAG-1, FLAG-2, FLAG-4).
**Methodology:** TDD (Red -> Green -> Refactor)

---

## Test Cases (Red Phase)

The following tests will be written first to drive the implementation of the `AuthSync` component.

*   **[TEST-FS1-01] (State Sync on Mount):** An integration test to verify that on initial render with a signed-in user, the `AuthSync` component correctly retrieves a token from the mocked Clerk `useAuth` hook and populates the `useAuthStore` (Zustand) with the token and tenant ID.

*   **[TEST-FS1-02] (Cache Invalidation on Org Switch):** An integration test to verify that when the Clerk `useOrganization` hook reports a change in the organization ID, the `AuthSync` component triggers `queryClient.clear()` to prevent cross-tenant data leakage.

*   **[TEST-FS1-03] (State Clear on Sign-out):** A unit test to verify that if the Clerk `useAuth` hook reports the user is signed out (`isSignedIn: false`), the `AuthSync` component calls the `clear()` method on the `useAuthStore`.

*   **[TEST-FS1-04] (Initial Load Behavior):** A test to verify that the component does **not** clear the query cache on the initial load, only on a subsequent change of organization ID.

---