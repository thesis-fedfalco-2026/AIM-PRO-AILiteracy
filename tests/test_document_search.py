from document_search.contracts import SearchScope, resource_key

TEST_SCOPE = SearchScope(mode="PREPARATION", source_scope_keys=("demo",))

import json
import traceback
import unittest
from unittest.mock import patch


class DocumentSearchTest(unittest.TestCase):
    def test_remote_flow_preserves_full_documents(self):
        from document_search.backend import build_backend

        document = {"id": "long", "text": "text " * 2000,
                    "metadata": {"source_scope": "demo", "source": "test", "extra": "preserved"}, "score": 1.0}
        backend = build_backend(
            {"SEARCH_BACKEND": "mock", "SEARCH_UNLIMITED_TEXT": "1"},
            vector_search=lambda vector, k, scope: [document],
        )
        self.addCleanup(backend.close)
        self.assertEqual(backend.search_documents("deployment", scope=TEST_SCOPE), {
            "documents": [document], "truncated": False,
        })

    def test_mock_deployment_query_returns_literal_synthetic_document(self):
        from document_search.backend import build_backend

        backend = build_backend({"SEARCH_BACKEND": "mock"})
        self.addCleanup(backend.close)
        self.assertEqual(backend.search_documents("deployment", 1, scope=TEST_SCOPE), {
            "documents": [{
                "id": "mock-technical",
                "text": "Technical deployment guide (synthetic): The approved release procedure is to verify the approved release tag, deploy the service through the approved pipeline, and check the service health endpoint. If the health check fails, roll back to the previous approved release.",
                "metadata": {"source_scope": "demo", "resource_key": resource_key('technical-deployment-guide', "1"), "source": "technical-deployment-guide", "synthetic": True},
                "score": 1.0,
            }],
            "truncated": False,
        })

    def test_valid_query_with_no_matches_returns_empty_documents(self):
        from document_search.backend import build_backend

        backend = build_backend({"SEARCH_BACKEND": "mock"})
        self.addCleanup(backend.close)
        self.assertEqual(
            backend.search_documents("unmatched", 5, scope=TEST_SCOPE),
            {"documents": [], "truncated": False},
        )

    def test_embedding_runs_before_vector_search(self):
        from document_search.backend import build_backend

        events = []
        backend = build_backend(
            {"SEARCH_BACKEND": "mock"},
            embed=lambda query: events.append(("embed", query)) or [1.0, 0.0],
            vector_search=lambda vector, k, scope: events.append(("search", vector, k)) or [{
                "id": "literal", "text": "Literal technical result", "metadata": {"source_scope": "demo", "source": "literal"}, "score": 0.5,
            }],
        )
        self.addCleanup(backend.close)
        self.assertEqual(backend.search_documents("deployment", 1, scope=TEST_SCOPE)["documents"][0]["id"], "literal")
        self.assertEqual(events, [
            ("embed", "task: search result | query: deployment"),
            ("search", [1.0, 0.0], 1),
        ])

    def test_formatted_retrieval_query_is_embedded_once(self):
        from document_search.backend import build_backend

        queries = []
        backend = build_backend(
            {"SEARCH_BACKEND": "mock"},
            embed=lambda query: queries.append(query) or [1.0, 0.0],
        )
        self.addCleanup(backend.close)
        backend.search_documents("task: search result | query: deployment", 1, scope=TEST_SCOPE)
        self.assertEqual(queries, ["task: search result | query: deployment"])

    def test_prefix_only_query_is_rejected_before_embedding(self):
        from document_search.backend import build_backend

        queries = []
        backend = build_backend(
            {"SEARCH_BACKEND": "mock"},
            embed=lambda query: queries.append(query) or [1.0, 0.0],
        )
        self.addCleanup(backend.close)
        with self.assertRaisesRegex(ValueError, "query must not be blank"):
            backend.search_documents("task: search result | query:   ", 1, scope=TEST_SCOPE)
        self.assertEqual(queries, [])

    def test_invalid_inputs_and_untrusted_backend_fail_without_leaking_values(self):
        from document_search.backend import SearchError, build_backend

        backend = build_backend(
            {"SEARCH_BACKEND": "mock"},
            embed=lambda query: [float("nan"), 0.0],
        )
        self.addCleanup(backend.close)
        for query, k in (("", 1), (" \t", 1), ("topic", 0), ("topic", 21), ("topic", True)):
            with self.subTest(query=query, k=k):
                with self.assertRaises((ValueError, SearchError)) as raised:
                    backend.search_documents(query, k, scope=TEST_SCOPE)
                self.assertNotIn("SENTINEL_PRIVATE", str(raised.exception))
        with self.assertRaisesRegex(SearchError, "Invalid embedding vector"):
            backend.search_documents("topic", 1, scope=TEST_SCOPE)

        for embedding in ([1.0], [1.0, "wrong"], [True, 0.0]):
            with self.subTest(embedding=embedding):
                invalid_embedding = build_backend({"SEARCH_BACKEND": "mock"}, embed=lambda query: embedding)
                self.addCleanup(invalid_embedding.close)
                with self.assertRaisesRegex(SearchError, "Invalid embedding vector"):
                    invalid_embedding.search_documents("topic", 1, scope=TEST_SCOPE)

        failing = build_backend(
            {"SEARCH_BACKEND": "mock"},
            vector_search=lambda vector, k, scope: (_ for _ in ()).throw(RuntimeError("SENTINEL_PRIVATE")),
        )
        self.addCleanup(failing.close)
        with self.assertRaisesRegex(SearchError, "Search failed") as raised:
            failing.search_documents("deployment", 1, scope=TEST_SCOPE)
        self.assertNotIn("SENTINEL_PRIVATE", str(raised.exception))

    def test_malformed_source_and_metadata_are_rejected_safely(self):
        from document_search.backend import SearchError, build_backend

        for metadata in ({"source_scope": "demo", "source": 123}, {"source_scope": "demo", "source": " \t"}, {}):
            with self.subTest(metadata=metadata):
                backend = build_backend(
                    {"SEARCH_BACKEND": "mock"},
                    vector_search=lambda vector, k, scope: [{
                        "id": "bad", "text": "evidence", "metadata": metadata, "score": 1.0,
                    }],
                )
                self.addCleanup(backend.close)
                with self.assertRaisesRegex(SearchError, "Search failed"):
                    backend.search_documents("deployment", 1, scope=TEST_SCOPE)

        unserializable = build_backend(
            {"SEARCH_BACKEND": "mock"},
            vector_search=lambda vector, k, scope: [{
                "id": "bad", "text": "evidence", "metadata": {"source_scope": "demo", "source": "source", "value": object()}, "score": 1.0,
            }],
        )
        self.addCleanup(unserializable.close)
        with self.assertRaisesRegex(SearchError, "Search failed"):
            unserializable.search_documents("deployment", 1, scope=TEST_SCOPE)

    def test_response_evidence_is_serialized_within_budget(self):
        from document_search.backend import MAX_RESPONSE_CHARS, build_backend

        backend = build_backend(
            {"SEARCH_BACKEND": "mock"},
            vector_search=lambda vector, k, scope: [{
                "id": "large-source",
                "text": "meaningful evidence " * 1000,
                "metadata": {"source_scope": "demo", "source": "large-source", "note": "unneeded " * 1000},
                "score": 1.0,
            }],
        )
        self.addCleanup(backend.close)
        result = backend.search_documents("deployment", 1, scope=TEST_SCOPE)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["documents"][0]["id"], "large-source")
        self.assertTrue(result["documents"][0]["text"].strip())
        self.assertLessEqual(len(json.dumps(result["documents"], ensure_ascii=False)), MAX_RESPONSE_CHARS)
        self.assertLess(len(result["documents"][0]["text"]), len("meaningful evidence " * 1000))

    def test_qdrant_settings_reject_unknown_or_incomplete_backends_without_values(self):
        from document_search.backend import ConfigurationError, build_backend

        for environ in (
            {},
            {"SEARCH_BACKEND": ""},
            {"SEARCH_BACKEND": " "},
            {"SEARCH_BACKEND": "unknown"},
            {"SEARCH_BACKEND": "qdrant", "QDRANT_URL": "SENTINEL_PRIVATE"},
        ):
            with self.subTest(environ=environ):
                with self.assertRaises(ConfigurationError) as raised:
                    build_backend(environ)
                self.assertNotIn("SENTINEL_PRIVATE", str(raised.exception))

    def test_explicit_empty_environment_does_not_read_process_settings(self):
        from document_search.backend import ConfigurationError, build_backend

        with patch.dict("document_search.backend.os.environ", {"SEARCH_BACKEND": "unknown"}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "^Invalid search backend$"):
                build_backend({})

    def test_qdrant_constructor_failure_is_sanitized_and_closes_http_client(self):
        from document_search.backend import ConfigurationError, build_backend

        events = []

        def close_http_client():
            events.append("http-close")
            raise RuntimeError("CLOSE_SENTINEL")

        http_client = type("HttpClient", (), {"close": lambda self: close_http_client()})()
        environ = {
            "SEARCH_BACKEND": "qdrant",
            "QDRANT_URL": "https://SENTINEL_PRIVATE@example.test",
            "QDRANT_COLLECTION": "documents",
            "EMBEDDING_URL": "https://embedding.example.test",
            "EMBEDDING_MODEL": "embedding",
            "EMBEDDING_DIMENSIONS": "2",
            "EMBEDDING_API_KEY": "key",
        }
        with self.assertRaisesRegex(ConfigurationError, "Unable to initialize Qdrant search") as raised:
            build_backend(
                environ,
                qdrant_factory=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("SENTINEL_PRIVATE")),
                http_client_factory=lambda **kwargs: http_client,
            )
        self.assertNotIn("SENTINEL", "".join(traceback.format_exception(raised.exception)))
        self.assertEqual(events, ["http-close"])

    def test_qdrant_constructor_rollback_attempts_both_closes(self):
        from document_search.backend import ConfigurationError, build_backend

        events = []

        def resource(name):
            def close():
                events.append(name)
                raise RuntimeError(f"{name.upper()}_CLOSE_SENTINEL")

            return type("Resource", (), {"close": lambda self: close()})()

        environ = {
            "SEARCH_BACKEND": "qdrant",
            "QDRANT_URL": "https://qdrant.example.test",
            "QDRANT_COLLECTION": "documents",
            "EMBEDDING_URL": "https://embedding.example.test",
            "EMBEDDING_MODEL": "embedding",
            "EMBEDDING_DIMENSIONS": "2",
            "EMBEDDING_API_KEY": "key",
        }
        with patch("document_search.backend.SearchBackend", side_effect=RuntimeError("CONSTRUCTOR_SENTINEL")):
            with self.assertRaisesRegex(ConfigurationError, "Unable to initialize Qdrant search") as raised:
                build_backend(
                    environ,
                    qdrant_factory=lambda **kwargs: resource("qdrant"),
                    http_client_factory=lambda **kwargs: resource("http"),
                )
        self.assertEqual(events, ["qdrant", "http"])
        self.assertNotIn("SENTINEL", "".join(traceback.format_exception(raised.exception)))

    def test_qdrant_search_then_cleanup_uses_both_clients(self):
        from document_search.backend import build_backend

        events = []

        class HttpResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"embedding": [1.0, 0.0]}]}

        class HttpClient:
            def post(self, url, *, headers, json):
                events.append(("embed", url, json))
                return HttpResponse()

            def close(self):
                events.append("http-close")

        class QdrantClient:
            def query_points(self, collection, *, query, limit, with_payload, query_filter):
                events.append(("query", collection, query, limit, with_payload))
                point = type("Point", (), {
                    "id": 7,
                    "payload": {"text": "Qdrant evidence", "metadata": {"source_scope": "demo", "source": "qdrant-source"}},
                    "score": 0.75,
                })()
                return type("Result", (), {"points": [point]})()

            def close(self):
                events.append("qdrant-close")

        environ = {
            "SEARCH_BACKEND": "qdrant",
            "QDRANT_URL": "https://qdrant.example.test",
            "QDRANT_COLLECTION": "documents",
            "EMBEDDING_URL": "https://embedding.example.test",
            "EMBEDDING_MODEL": "embedding",
            "EMBEDDING_DIMENSIONS": "2",
            "EMBEDDING_API_KEY": "key",
        }
        backend = build_backend(
            environ,
            qdrant_factory=lambda **kwargs: QdrantClient(),
            http_client_factory=lambda **kwargs: HttpClient(),
        )
        result = backend.search_documents("deployment", 1, scope=TEST_SCOPE)
        backend.close()

        self.assertEqual(result, {
            "documents": [{
                "id": "7",
                "text": "Qdrant evidence",
                "metadata": {"source_scope": "demo", "source": "qdrant-source"},
                "score": 0.75,
            }],
            "truncated": False,
        })
        self.assertEqual(events, [
            ("embed", "https://embedding.example.test", {
                "input": "task: search result | query: deployment", "model": "embedding",
            }),
            ("query", "documents", [1.0, 0.0], 1, True),
            "qdrant-close",
            "http-close",
        ])

    def test_successful_qdrant_initialization_sanitizes_both_close_failures(self):
        from document_search.backend import SearchError, build_backend

        events = []

        def resource(name):
            def close():
                events.append(name)
                raise RuntimeError(f"{name.upper()}_CLOSE_SENTINEL")

            return type("Resource", (), {"close": lambda self: close()})()

        environ = {
            "SEARCH_BACKEND": "qdrant",
            "QDRANT_URL": "https://qdrant.example.test",
            "QDRANT_COLLECTION": "documents",
            "EMBEDDING_URL": "https://embedding.example.test",
            "EMBEDDING_MODEL": "embedding",
            "EMBEDDING_DIMENSIONS": "2",
            "EMBEDDING_API_KEY": "key",
        }
        backend = build_backend(
            environ,
            qdrant_factory=lambda **kwargs: resource("qdrant"),
            http_client_factory=lambda **kwargs: resource("http"),
        )
        with self.assertRaisesRegex(SearchError, "Unable to close search backend") as raised:
            backend.close()

        self.assertEqual(events, ["qdrant", "http"])
        self.assertNotIn("SENTINEL", "".join(traceback.format_exception(raised.exception)))
