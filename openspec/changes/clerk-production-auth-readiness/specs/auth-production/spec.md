# Production Authentication Specification

## Purpose

Define the requirements for closing production Clerk authentication readiness tasks in C2Pro and for validating the system as a user-facing production authentication flow.

## Requirements

### Requirement: Production Clerk Project

The production authentication workflow MUST use a Clerk Production project rather than a development/test Clerk instance.

#### Scenario: Live Clerk project is required

- GIVEN an operator is preparing C2Pro for production authentication
- WHEN the Clerk environment is reviewed for `TASK-1174`
- THEN the active project MUST be a Clerk Production project and SHALL NOT rely on `accounts.dev`

#### Scenario: Development markers block completion

- GIVEN any authentication email shows `[Development]` or `accounts.dev`
- WHEN the operator evaluates production readiness
- THEN `TASK-1174` MUST remain open

### Requirement: Live Credential Contract

Production authentication MUST use live Clerk credentials and MUST keep those credentials outside version-controlled files.

#### Scenario: Live keys are provisioned in deployment systems

- GIVEN the frontend and backend are being configured for production
- WHEN environment variables are reviewed
- THEN the publishable and secret keys SHALL be `pk_live_...` and `sk_live_...`

#### Scenario: Test keys fail readiness

- GIVEN any checked runtime environment uses `pk_test_...` or `sk_test_...`
- WHEN readiness is assessed
- THEN the production auth rollout MUST be marked incomplete

### Requirement: Production URL Configuration

The production Clerk configuration MUST define the final production domain and the allowed sign-in/sign-up redirect URLs used by the application.

#### Scenario: Redirect URLs match the deployed app

- GIVEN the deployed frontend serves `/sign-in` and `/sign-up`
- WHEN Clerk production redirect settings are reviewed
- THEN the configured URLs MUST match the deployed production domain and application routes

#### Scenario: Missing production redirect configuration blocks completion

- GIVEN production Clerk settings omit the deployed domain or auth routes
- WHEN the operator attempts production sign-in or sign-up validation
- THEN `TASK-1176` MUST remain open

### Requirement: Production Email Delivery

The production authentication workflow MUST use a verified production sender and SHOULD prove sign-up and reset emails arrive without development markers.

#### Scenario: Production sender is verified

- GIVEN the operator performs sign-up or reset-password validation in production
- WHEN email is delivered
- THEN the sender SHALL be a production sender and the subject SHALL NOT include `[Development]`

#### Scenario: Development sender blocks closure

- GIVEN production auth emails still arrive from `accounts.dev`
- WHEN the rollout is reviewed
- THEN `TASK-1177` MUST remain open

### Requirement: Production Deployment Wiring

The frontend and backend production deployments MUST be configured with consistent Clerk and API environment variables.

#### Scenario: Frontend production deployment is configured

- GIVEN the frontend is deployed to production
- WHEN the deployed app is validated
- THEN the frontend MUST load Clerk sign-in and sign-up flows with production configuration and SHALL NOT run in demo mode

#### Scenario: Backend production deployment is configured

- GIVEN the backend is deployed to production
- WHEN the backend runtime is validated
- THEN Clerk issuer and JWKS settings MUST resolve correctly and authenticated requests SHALL succeed

### Requirement: Closure Evidence

Closing `TASK-1174` MUST require explicit evidence for `TASK-1175`, `TASK-1176`, `TASK-1177`, `TASK-1178`, and `TASK-1179`.

#### Scenario: Dependent task evidence is complete

- GIVEN the operator claims production auth is ready
- WHEN the closure checklist is reviewed
- THEN each dependent task SHALL have corresponding execution evidence and pass/fail outcome

#### Scenario: Missing dependent evidence blocks aggregate closure

- GIVEN one or more dependent tasks lack evidence
- WHEN `TASK-1174` is evaluated
- THEN `TASK-1174` MUST remain open
