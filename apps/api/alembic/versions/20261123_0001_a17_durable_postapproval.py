"""A17: durable post-approval Score obligation in the already committed HITL row.

Revision ID: 20261123_0001
Revises: 20261118_0001

No new queue or privileged table. PostgreSQL stamps the obligation inside the
same transaction that changes a review to APPROVED, including raw-SQL resume
paths. Existing historical approvals are intentionally NOT backfilled.
"""

from __future__ import annotations

from alembic import op

revision = "20261123_0001"
down_revision = "20261118_0001"
branch_labels = None
depends_on = None

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.a17_stamp_postapproval_obligation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    old_obligation jsonb;
BEGIN
    old_obligation := coalesce(OLD.review_metadata, '{}'::jsonb)
                      -> 'a17_score_obligation';
    IF NEW.current_status = 'APPROVED'
       AND OLD.current_status IS DISTINCT FROM NEW.current_status
       AND NEW.project_id IS NOT NULL
       AND NEW.approved_at IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM public.projects p
            WHERE p.id = NEW.project_id AND p.tenant_id = NEW.tenant_id
       ) THEN
        -- Never trust a client-generated job marker. The source of truth is
        -- the database transition, review's real PK and tenant-bound project.
        NEW.review_metadata := coalesce(NEW.review_metadata, '{}'::jsonb)
            || jsonb_build_object(
                'a17_score_obligation',
                jsonb_build_object(
                    'state', 'pending',
                    'review_id', NEW.id::text,
                    'attempts', 0,
                    'retry_after', NULL,
                    'created_at', clock_timestamp()
                )
            );
    ELSIF old_obligation IS NOT NULL THEN
        -- ORM updates must not erase this durable obligation or downgrade
        -- a completed outcome to pending using a stale metadata copy.
        IF NEW.review_metadata IS NULL
           OR NOT (NEW.review_metadata ? 'a17_score_obligation')
           OR old_obligation ->> 'state' = 'done' THEN
            NEW.review_metadata := coalesce(NEW.review_metadata, '{}'::jsonb)
                || jsonb_build_object('a17_score_obligation', old_obligation);
        END IF;
    END IF;
    RETURN NEW;
END;
$$
"""
CREATE_TRIGGER_SQL = """
CREATE TRIGGER tr_a17_stamp_postapproval_obligation
BEFORE UPDATE OF current_status, review_metadata ON public.review_items
FOR EACH ROW
EXECUTE FUNCTION public.a17_stamp_postapproval_obligation()
"""


def upgrade() -> None:
    op.execute(FUNCTION_SQL)
    op.execute(CREATE_TRIGGER_SQL)


def downgrade() -> None:
    # Do not erase obligations or human decisions.
    op.execute("DROP TRIGGER IF EXISTS tr_a17_stamp_postapproval_obligation ON public.review_items")
    op.execute("DROP FUNCTION IF EXISTS public.a17_stamp_postapproval_obligation()")
