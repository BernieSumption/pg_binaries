CREATE EXTENSION vector;

CREATE TABLE pilot_vectors (
    id integer PRIMARY KEY,
    embedding vector(3) NOT NULL
);
INSERT INTO pilot_vectors VALUES
    (1, '[1,0,0]'),
    (2, '[0,1,0]'),
    (3, '[0,0,1]');
CREATE INDEX pilot_vectors_hnsw
    ON pilot_vectors USING hnsw (embedding vector_l2_ops);

DO $$
BEGIN
    IF (SELECT extversion FROM pg_extension WHERE extname = 'vector') <> '0.8.7' THEN
        RAISE EXCEPTION 'unexpected pgvector version';
    END IF;
    IF (SELECT vector_dims(embedding) FROM pilot_vectors WHERE id = 2) <> 3 THEN
        RAISE EXCEPTION 'vector dimension mismatch';
    END IF;
    IF (SELECT id FROM pilot_vectors
        ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 1) <> 1 THEN
        RAISE EXCEPTION 'nearest vector result mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class index_relation
        JOIN pg_am access_method ON access_method.oid = index_relation.relam
        WHERE index_relation.oid = 'pilot_vectors_hnsw'::regclass
          AND access_method.amname = 'hnsw'
    ) THEN
        RAISE EXCEPTION 'HNSW index or access method missing';
    END IF;
END
$$;
