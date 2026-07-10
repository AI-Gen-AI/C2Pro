-- TASK-FRT-201: C2Pro pilot waitlist capture with fail-closed RLS.

CREATE TABLE IF NOT EXISTS public.waitlist_signups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    name text NOT NULL,
    company text NOT NULL,
    role text,
    email text NOT NULL,
    volume text CHECK (volume IS NULL OR volume IN ('under_20','20_100','over_100')),
    consent boolean NOT NULL,
    locale text,
    source text NOT NULL DEFAULT 'c2pro.io',
    user_agent text,
    CONSTRAINT uq_waitlist_signups_email UNIQUE (email)
);

ALTER TABLE public.waitlist_signups ENABLE ROW LEVEL SECURITY;
