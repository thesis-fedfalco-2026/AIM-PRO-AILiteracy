import unittest
from unittest.mock import patch

from document_search.contracts import SearchScope, resource_key
from document_search.backend import build_backend, SearchError


class ScopedRetrievalTest(unittest.TestCase):
    def test_filter_precedes_k(self):
        records = tuple({"id": name, "text": name, "vector": vector,
                         "metadata": {"source": name, "resource_key": resource_key(name, "1")}}
                        for name, vector in (("forbidden", [1.0, 0.0]), ("allowed", [0.2, 0.0])))
        backend = build_backend({"SEARCH_BACKEND": "mock"})
        scope = SearchScope(mode="LEARNING", resource_keys=(resource_key("allowed", "1"),))
        with patch("document_search.backend._MOCK_DOCUMENTS", records):
            result = backend.search_documents("deployment", 1, scope=scope)
        self.assertEqual([d["id"] for d in result["documents"]], ["allowed"])

    def test_empty_scope_never_searches_globally(self):
        backend = build_backend({"SEARCH_BACKEND": "mock"}, embed=lambda _: self.fail("No embedding for empty scope"))
        self.assertEqual(backend.search_documents("deployment", 1, scope=SearchScope(mode="LEARNING"))["documents"], [])

    def test_version_pairs_are_not_cross_combined(self):
        scope = SearchScope(mode="LEARNING", resource_keys=(resource_key("a", "1"), resource_key("b", "2")))
        self.assertFalse(scope.matches({"resource_key": resource_key("a", "2")}))
        self.assertFalse(scope.matches({"resource_key": resource_key("b", "1")}))
        self.assertTrue(scope.matches({"resource_key": resource_key("a", "1")}))

    def test_missing_mapping_is_rejected(self):
        backend = build_backend({"SEARCH_BACKEND": "mock"}, vector_search=lambda v, k, s: [
            {"id": "x", "text": "secret", "metadata": {"source": "x"}, "score": 1}])
        with self.assertRaises(SearchError):
            backend.search_documents("deployment", 1, scope=SearchScope(mode="LEARNING", resource_keys=(resource_key("x", "1"),)))

    def test_learning_cannot_discover_external_candidates(self):
        with self.assertRaises(ValueError):
            SearchScope(mode="LEARNING", source_scope_keys=("all",))

    def test_scope_is_required(self):
        with self.assertRaises(TypeError):
            build_backend({"SEARCH_BACKEND": "mock"}).search_documents("deployment", 1)
