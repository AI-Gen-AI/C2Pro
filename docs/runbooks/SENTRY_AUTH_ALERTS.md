# Runbook: Sentry Authentication Alerts

This document provides guidance for on-call engineers responding to Sentry alerts related to authentication failures in the C2Pro platform.

**Slack Channel:** [#c2pro-security-alerts](https://c2pro.slack.com/archives/c2pro-security-alerts)
**PagerDuty Service:** c2pro-oncall

## Alert Definitions

### 1. [Auth] High rate of auth failures for a single tenant

- **Description:** This alert fires when more than 50 authentication failures are detected for the same `tenant.id` within a 5-minute window.
- **Meaning:**
    - **High Priority:** Could indicate a targeted attack against a specific tenant (e.g., password spraying, credential stuffing).
    - **Medium Priority:** Could indicate a client-side bug (e.g., an expired token is not being refreshed correctly) affecting a single large tenant.
    - **Low Priority:** A misconfigured integration or a user script hammering an endpoint with invalid credentials.
- **Triage Steps:**
    1.  Check the Sentry issue for the affected `tenant.id`.
    2.  Examine the `auth.reason` tags associated with the events. Are they all the same?
        - `token_expired`: Likely a client-side refresh issue.
        - `tenant_inactive_or_missing`: The tenant may have been deactivated or deleted.
        - `invalid_authentication_credentials`: Possible credential stuffing.
    3.  Look at the IP addresses and user agents. Is the traffic coming from a single IP or distributed?
    4.  If a specific user account is involved (if that context is available), check their recent activity.
- **Escalation:**
    - If an attack is suspected (distributed IPs, credential stuffing patterns), escalate to the Security Lead immediately.
    - If it appears to be a bug, create a P1 ticket for the appropriate client-side team (e.g., `apps-web`).
    - If it's a misconfigured integration, attempt to contact the tenant's technical support contact.

### 2. [Auth] Bootstrap fallback blocked

- **Description:** This alert fires for **any single event** in the `production` environment with the `auth.reason` tag `auth_bootstrap_fallback_blocked`.
- **Meaning:**
    - **CRITICAL PRIORITY:** This is a high-severity event. It means a user who successfully authenticated with Clerk is being denied access because the system failed to look up their associated tenant, and the "first-time user" provisioning flow was blocked by security policy. This should be an extremely rare event and could signify a serious system state inconsistency or a novel attack vector.
- **Triage Steps:**
    1.  **IMMEDIATELY** open the Sentry issue.
    2.  Identify the `clerk_user_id` from the event context.
    3.  Check the application logs for `clerk_user_tenant_lookup_failed` for that user ID to understand why the database lookup failed. Was the database down? Was there a replication lag?
    4.  Check the user's status in the Clerk dashboard. Are they a new user? Are they part of an organization?
    5.  Check the production database `users` table. Does a record for this `clerk_user_id` exist? If so, what is its state?
- **Escalation:**
    - **Page the Head of Engineering and the Security Lead immediately.** This is a potential P0 incident. Do not resolve the alert until the root cause is understood.

### 3. [Auth] High rate of anonymous auth failures

- **Description:** This alert fires when more than 200 authentication failures with no associated `tenant.id` (`tenant.id:anonymous`) occur within a 5-minute window.
- **Meaning:**
    - **High Priority:** Likely indicates a large-scale, automated attack against the platform, such as vulnerability scanning, enumeration attempts, or a distributed credential stuffing attack against the login endpoints.
    - **Low Priority:** A major search engine crawler or a benign bot has started aggressively hitting authenticated endpoints.
- **Triage Steps:**
    1.  Go to the Sentry issue and examine the `http.path` tags. Which endpoints are being targeted?
    2.  Group the events by IP address. Is the traffic coming from a small number of IPs or is it highly distributed?
    3.  Check the user agents. Do they look like legitimate browsers or common bot/scripting agents (e.g., `python-requests`, `curl`)?
    4.  If the traffic appears malicious (e.g., targeting login endpoints from many IPs), work with the Infrastructure team to implement rate limiting or blocking at the edge (Cloudflare/WAF).
- **Escalation:**
    - If a large-scale attack is confirmed, escalate to the Infrastructure and Security teams to begin mitigation procedures.
    - If it appears to be a misbehaving bot, consider adding its user agent to a blocklist or adjusting `robots.txt`.
