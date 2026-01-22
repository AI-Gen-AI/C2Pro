# Sprint 1 Plan: Plataforma Foundation

**Main Goal:** By the end of this sprint, a user should be able to register, log in, view their project dashboard, and create a new project.

---

## Backend Tasks (API)

### 1. Project Data Model Finalization
*   **Description:** Finalize the SQLAlchemy model in `apps/api/src/modules/projects/models.py`.
*   **Details:** Ensure the `Project` model includes, at a minimum: `id`, `name`, `description`, `created_at`, and a foreign key (`user_id`) relating it to the owner user.

### 2. Authentication Endpoints
*   **Description:** Implement the business logic in `apps/api/src/modules/auth/service.py` and the endpoints in `router.py`.
*   **Endpoints to Create:**
    *   `POST /api/v1/auth/register`: For registering a new user. Passwords must be hashed before saving.
    *   `POST /api/v1/auth/login`: For authenticating a user and returning a JWT.

### 3. Project CRUD Endpoints
*   **Description:** Implement the services and routes for project management.
*   **Endpoints to Create:**
    *   `POST /api/v1/projects`: To create a new project. This must be a protected route requiring authentication.
    *   `GET /api/v1/projects`: To retrieve the list of projects belonging to the authenticated user.

---

## Frontend Tasks (Web)

### 1. Authentication Logic
*   **Description:** Connect the registration and login forms to the API.
*   **Files to Modify:** `apps/web/app/(auth)/register/page.tsx` and `login/page.tsx`.
*   **Details:** Make calls to the API endpoints and handle responses (success or error).

### 2. Client-Side Session Management
*   **Description:** Implement logic to securely store and manage the JWT (e.g., in an HttpOnly cookie).
*   **Files to Modify:** `apps/web/lib/auth.ts` and the `api-client` to send the token in authenticated request headers.
*   **Details:** Create a React hook or context (e.g., `useAuth`) for components to easily access the user's authentication state.

### 3. Project Management Interface
*   **Description:** Develop pages for listing and creating projects.
*   **Pages to Develop:**
    *   `apps/web/app/(dashboard)/projects/page.tsx`: Should fetch and display the list of projects for the user.
    *   `apps/web/app/(dashboard)/projects/new/page.tsx`: Should contain a form to submit new project information to the API.

---

## Quality Assurance & Testing Tasks (QA)

### 1. API Tests
*   **Description:** Write unit and integration tests in `apps/api/tests/` for all new authentication and project endpoints.

### 2. UI Tests
*   **Description:** Create basic component tests for the new registration, login, and project creation forms.
