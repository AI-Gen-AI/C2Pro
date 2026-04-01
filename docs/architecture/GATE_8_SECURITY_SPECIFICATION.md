# Gate 8: Document Security Specification

**Version:** 1.0.0
**Status:** ✅ COMPLETED
**Date:** 2026-04-01

## 1. Overview
Gate 8 (Document Security) ensures the protection of sensitive information within the C2Pro platform through a multi-layered security approach including PII anonymization, mandatory legal disclosures, encrypted storage, and data retention policies.

## 2. PII Anonymization (Anonymizer Service)
To protect sensitive data before it is processed by external Large Language Models (LLMs), C2Pro implements a robust anonymization pipeline.

### 2.1 Implementation
- **Core Service:** `AnonymizationService` (`apps/api/src/anonymizer/application/anonymization_service.py`)
- **Detection:** `PiiDetectorService` (`apps/api/src/anonymizer/domain/pii_detector_service.py`)
- **Strategies:**
  - `REDACT`: Replaces sensitive values with a fixed placeholder (`[REDACTED]`).
  - `HASH`: Replaces values with a deterministic SHA-256 hash.
  - `PSEUDONYMIZE`: Replaces values with consistent pseudonyms (e.g., `[PERSON_001]`).
- **Workflow:**
  1. Detect PII types (Email, Person, Phone, Location, etc.).
  2. Apply selected strategy based on tenant-specific configuration.
  3. Ensure no PII is transmitted to external providers (e.g., Anthropic/Claude).

## 3. Legal Disclaimer Enforcement
Every user must explicitly acknowledge the C2Pro Legal Disclaimer to ensure transparency regarding the AI-assisted nature of the platform.

### 3.1 Components
- **Frontend Gate:** `LegalDisclaimerModal.tsx` (`apps/web/components/features/compliance/`)
- **Backend Persistence:** `frontend_support` router (`apps/api/src/core/frontend_support/router.py`)
- **Persistence Logic:**
  - Status Check: `GET /api/v1/projects/{project_id}/gates/gate-8/disclaimer/status`
  - Acceptance Log: `POST /api/v1/projects/{project_id}/gates/gate-8/disclaimer/accept`
- **Scope:** Acceptance is scoped by `tenant_id`, `user_id`, and `disclaimer_version`.

## 4. Document Encryption (R2 Storage)
All project documents are stored in Cloudflare R2 with encryption at rest.

### 4.1 Architecture
- **Adapter:** `R2StorageService` (`apps/api/src/documents/adapters/storage/r2_storage_service.py`)
- **Encryption:** Uses Cloudflare R2's default **Server-Side Encryption (SSE)**.
- **Resilience:** Protected by a `CircuitBreaker` to prevent cascading failures if the storage provider is unreachable.

## 5. Data Retention & Soft Delete
C2Pro implements data lifecycle management to satisfy legal and audit requirements.

### 5.1 Policies
- **Soft Delete:** Key entities (`Tenant`, `User`, `Project`, `Document`) use an `is_active` flag or `deleted_at` timestamp to prevent permanent data loss during audit windows.
- **Retention Timing:** Database migrations include a `retention_until` column to track the mandatory hold period for legal records.
- **Auditability:** All major tables include `created_at` and `updated_at` timestamps to ensure a verifiable data lineage.

## 6. Verification
Compliance with Gate 8 is verified through:
- **E2E Tests:** `S3-08-legal-disclaimer.spec.ts` (Frontend)
- **Security Tests:** `test_gate4_traceability.py` (Backend timestamps and soft-delete verification)
- **Unit Tests:** `test_i14_safety_hardening.py` (Disclaimer injection verification)
