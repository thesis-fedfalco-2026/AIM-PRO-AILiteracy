"""Read-only WP3 full-text retrieval through the existing scoped MCP contract."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from document_search.backend import (
    ConfigurationError, Document, SearchError, SearchResponse,
    _bounded_documents, _validate_k, _validate_query,
)
from document_search.contracts import SearchScope, preparation_selection, resource_key


class PostgresBackend:
    def __init__(self, dsn: str, *, unlimited_text: bool = False):
        self._dsn = dsn
        self._unlimited_text = unlimited_text

    def search_documents(self, query: str, k: int = 5, *, scope: SearchScope) -> dict[str, Any]:
        _validate_query(query)
        _validate_k(k)
        scope = SearchScope.model_validate(scope)
        if not scope.keys:
            return SearchResponse(documents=[]).model_dump()
        try:
            import psycopg
            from psycopg.rows import dict_row

            # The field is selected from a closed set, never from user input.
            predicate = ("metadata->>'resource_key' = ANY(%s)" if scope.mode == "LEARNING"
                         else "metadata->>'source_scope' = ANY(%s)")
            with psycopg.connect(self._dsn, connect_timeout=5, row_factory=dict_row,
                                 options="-c default_transaction_read_only=on -c statement_timeout=10000") as conn:
                rows = conn.execute(
                    "SELECT id, text, metadata, ts_rank_cd(search_vector, q) AS score "
                    "FROM wp3_search.documents, websearch_to_tsquery('simple', %s) q "
                    "WHERE search_vector @@ q AND " + predicate +
                    " ORDER BY score DESC, id LIMIT %s",
                    (query.strip(), list(scope.keys), k),
                ).fetchall()
            documents = [Document.model_validate(row) for row in rows]
            if any(not scope.matches(document.metadata) for document in documents):
                raise SearchError("Search failed")
            if self._unlimited_text:
                bounded, truncated = [d.model_dump() for d in documents], False
            else:
                bounded, truncated = _bounded_documents(documents)
            return SearchResponse(documents=bounded, truncated=truncated).model_dump()
        except Exception:
            raise SearchError("Search failed") from None

    def close(self) -> None:
        pass

    def fetch_preparation_documents(self, selections, *, scope):
        refs, scope = preparation_selection(selections, scope)
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self._dsn, connect_timeout=5, row_factory=dict_row,
                    options='-c default_transaction_read_only=on -c statement_timeout=10000') as conn:
                rows = conn.execute(
                    "SELECT id, text, metadata, 0.0 AS score FROM wp3_search.documents "
                    "WHERE metadata->>'source_scope' = ANY(%s) AND id = ANY(%s)",
                    (list(scope.keys), [r.document_id for r in refs])).fetchall()
            by_id = {row['id']: Document.model_validate(row) for row in rows}
            if set(by_id) != {r.document_id for r in refs}:
                raise SearchError('Exact source selection unavailable')
            documents = []
            for ref in refs:
                doc = by_id[ref.document_id]
                if (not scope.matches(doc.metadata) or doc.metadata['source'] != ref.resource_id or
                        doc.metadata.get('resource_key') != resource_key(ref.resource_id, ref.resource_version) or
                        hashlib.sha256(doc.text.encode()).hexdigest() != ref.content_sha256):
                    raise SearchError('Exact source selection changed')
                documents.append(doc)
            if self._unlimited_text:
                return SearchResponse(documents=documents).model_dump()
            bounded, truncated = _bounded_documents(documents)
            return SearchResponse(documents=bounded, truncated=truncated).model_dump()
        except Exception:
            raise SearchError('Exact source selection failed') from None


def build_postgres_backend(environ: Mapping[str, str]) -> PostgresBackend:
    dsn = environ.get("WP3_DATABASE_URL", "").strip()
    if not dsn:
        raise ConfigurationError("WP3_DATABASE_URL is required for PostgreSQL search")
    return PostgresBackend(dsn, unlimited_text=environ.get("SEARCH_UNLIMITED_TEXT") == "1")
