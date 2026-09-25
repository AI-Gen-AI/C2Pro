-- =====================================================
-- Migration: 20260914000300_ir6_alerttype_audit_incomplete.sql
-- Date: 2026-09-14
-- Mirrors Alembic 20260914_0003 (IR-6).
-- AlertType.AUDIT_INCOMPLETE exists in the application vocabulary (TASK-COH-V1-06) but was never
-- added to the alerttype enum created by 20260315000200. Canonical code value added; nothing removed.
-- =====================================================

ALTER TYPE public.alerttype ADD VALUE IF NOT EXISTS 'audit_incomplete';
