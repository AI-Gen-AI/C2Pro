DO $$
DECLARE
    v_vector_available BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_available_extensions
        WHERE name = 'vector'
    ) INTO v_vector_available;

    IF NOT v_vector_available THEN
        RAISE NOTICE 'Migración 009_rag_setup.sql omitida: extensión vector no disponible';
        RETURN;
    END IF;

    EXECUTE 'CREATE EXTENSION IF NOT EXISTS vector';

    EXECUTE $sql$
        CREATE TABLE IF NOT EXISTS public.document_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
            project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            content text NOT NULL,
            embedding vector(1536) NOT NULL,
            metadata jsonb DEFAULT '{}'::jsonb,
            created_at timestamptz DEFAULT now()
        );
    $sql$;

    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON public.document_chunks (document_id)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_document_chunks_project_id ON public.document_chunks (project_id)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding ON public.document_chunks USING ivfflat (embedding vector_cosine_ops)';

    EXECUTE $sql$
        CREATE OR REPLACE FUNCTION public.match_documents(
            p_project_id uuid,
            p_embedding vector(1536),
            match_count int DEFAULT 5
        )
        RETURNS TABLE (
            content text,
            metadata jsonb,
            distance float
        )
        LANGUAGE sql
        STABLE
        AS $func$
            SELECT
                document_chunks.content,
                document_chunks.metadata,
                (document_chunks.embedding <=> p_embedding) AS distance
            FROM public.document_chunks
            WHERE document_chunks.project_id = p_project_id
            ORDER BY document_chunks.embedding <=> p_embedding
            LIMIT match_count;
        $func$;
    $sql$;
END $$;
