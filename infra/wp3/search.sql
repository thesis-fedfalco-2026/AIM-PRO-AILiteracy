-- Derived search projection: refresh after changing the restored WP3 corpus.
CREATE SCHEMA IF NOT EXISTS wp3_search;
CREATE MATERIALIZED VIEW IF NOT EXISTS wp3_search.documents AS
WITH resources AS (
    SELECT r.*, 'wp3:' || resource_id AS identity,
           md5(jsonb_build_array(title, description, summary, body_md, canonical_uri,
               uri, licence_spdx, licence_verdict, metadata_only, language, keywords)::text) AS version
    FROM public.corpus_resource r
), chunks AS (
    SELECT r.*, n AS chunk,
           concat_ws(E'\n\n', nullif(title, ''), nullif(description, ''), nullif(summary, ''),
               nullif(substr(body_md, n * 5500 + 1, 6000), '')) AS text
    FROM resources r
    CROSS JOIN LATERAL generate_series(0, greatest(0, (length(body_md) - 1) / 5500)) n
)
SELECT identity || ':' || version || ':' || chunk AS id,
       identity, version, text,
       jsonb_build_object('source', identity, 'source_scope', 'wp3',
           'resource_key', '[' || to_json(identity)::text || ',' || to_json(version)::text || ']',
           'synthetic', false, 'title', title, 'uri', coalesce(nullif(canonical_uri, ''), uri),
           'language', language, 'licence', licence_spdx, 'licence_verdict', licence_verdict,
           'metadata_only', metadata_only, 'chunk', chunk) AS metadata,
       to_tsvector('simple', text) AS search_vector
FROM chunks WHERE btrim(text) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS wp3_documents_id ON wp3_search.documents (id);
CREATE INDEX IF NOT EXISTS wp3_documents_fts ON wp3_search.documents USING gin (search_vector);
CREATE INDEX IF NOT EXISTS wp3_documents_resource_key ON wp3_search.documents ((metadata->>'resource_key'));
ANALYZE wp3_search.documents;
