-- =====================================================
-- Migration: 20260914000200_ir6_clausetype_application_values.sql
-- Date: 2026-09-14
-- Mirrors Alembic 20260914_0002 (IR-6).
-- 20260310000100_add_documents_tables.sql creates clausetype with a legacy vocabulary that lacks
-- five values the application's ClauseType produces. Only canonical application values are added;
-- legacy DB-only labels stay (PostgreSQL cannot drop enum values) and no code writes them.
-- ADD VALUE IF NOT EXISTS is a no-op where the value already exists.
-- =====================================================

ALTER TYPE public.clausetype ADD VALUE IF NOT EXISTS 'milestone';
ALTER TYPE public.clausetype ADD VALUE IF NOT EXISTS 'responsibility';
ALTER TYPE public.clausetype ADD VALUE IF NOT EXISTS 'quality';
ALTER TYPE public.clausetype ADD VALUE IF NOT EXISTS 'termination';
ALTER TYPE public.clausetype ADD VALUE IF NOT EXISTS 'dispute';
