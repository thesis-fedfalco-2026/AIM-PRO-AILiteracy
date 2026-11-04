import json
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from agent_system.mcp_runtime import DocumentSearchClient, build_document_search_params
from document_search.backend import ConfigurationError, build_backend
from document_search.contracts import PreparationDocumentRef, SearchScope, resource_key
from learning.outputs import discovered_resources


class WP3ConfigurationTest(unittest.TestCase):
    def test_missing_dsn_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            build_backend({"SEARCH_BACKEND": "postgres"})

    def test_empty_scope_does_not_connect(self):
        backend = build_backend({"SEARCH_BACKEND": "postgres", "WP3_DATABASE_URL": "invalid"})
        self.assertEqual(backend.search_documents("science", scope=SearchScope(mode="LEARNING")),
                         {"documents": [], "truncated": False})

    def test_mcp_only_forwards_reader_configuration(self):
        params = build_document_search_params(Path.cwd(), {
            "SEARCH_BACKEND": "postgres", "WP3_DATABASE_URL": "reader-dsn",
            "WP3_ADMIN_PASSWORD": "secret", "OPENROUTER_API_KEY": "secret"})
        self.assertEqual(params.env["WP3_DATABASE_URL"], "reader-dsn")
        self.assertNotIn("WP3_ADMIN_PASSWORD", params.env)
        self.assertNotIn("OPENROUTER_API_KEY", params.env)

    def test_chunks_create_one_versioned_resource(self):
        task = SimpleNamespace(specialization=SimpleNamespace(fields={"topics": []}))
        metadata = {"source": "wp3:r1", "title": "Real title", "source_scope": "wp3",
                    "resource_key": resource_key("wp3:r1", "v1"), "uri": "https://example.org/r1",
                    "licence": "MIT", "licence_verdict": "open"}
        documents = [{"text": text, "metadata": metadata} for text in ("first", "second", "first")]
        result = discovered_resources(task, {"documents": documents})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "wp3:r1")
        self.assertEqual(result[0].version, "v1")
        self.assertEqual(result[0].fields["title"], "Real title")
        self.assertEqual(result[0].fields["contentOrLocator"], "https://example.org/r1\n\nfirst\n\nsecond")
        self.assertIn("MIT", result[0].fields["usageConditions"])


@unittest.skipUnless(os.environ.get("WP3_TEST_DATABASE_URL"), "Requires restored WP3 database")
class WP3IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.environ = {"SEARCH_BACKEND": "postgres", "WP3_DATABASE_URL": os.environ["WP3_TEST_DATABASE_URL"]}
        self.backend = build_backend(self.environ)
        self.scope = SearchScope(mode="PREPARATION", source_scope_keys=("wp3",))

    def test_real_search_exact_version_and_mcp(self):
        result = self.backend.search_documents("learning", 3, scope=self.scope)
        self.assertTrue(result["documents"])
        first = result["documents"][0]
        self.assertFalse(first["metadata"]["synthetic"])
        key = first["metadata"]["resource_key"]
        learning_scope = SearchScope(mode="LEARNING", resource_keys=(key,))
        bound = self.backend.search_documents("learning", 1, scope=learning_scope)
        self.assertTrue(bound["documents"])
        self.assertTrue(all(d["metadata"]["resource_key"] == key for d in bound["documents"]))
        identity, _ = json.loads(key)
        missing = SearchScope(mode="LEARNING", resource_keys=(resource_key(identity, "old"),))
        self.assertEqual(self.backend.search_documents("learning", scope=missing)["documents"], [])
        denied = SearchScope(mode="PREPARATION", source_scope_keys=("demo",))
        self.assertEqual(self.backend.search_documents("learning", scope=denied)["documents"], [])
        client = DocumentSearchClient(build_document_search_params(Path.cwd(), self.environ))
        self.assertTrue(client.search("learning", 1, scope=learning_scope)["documents"])

    def test_reader_cannot_access_private_tables_or_write(self):
        import psycopg
        with psycopg.connect(self.environ["WP3_DATABASE_URL"], autocommit=True) as conn:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM public.auth_user")
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                conn.execute("CREATE TABLE public.wp3_write_probe (id int)")

    def test_real_exact_preparation_fetch_through_mcp(self):
        backend = build_backend({**self.environ,'SEARCH_UNLIMITED_TEXT':'1'})
        self.addCleanup(backend.close)
        document = backend.search_documents('prompt',1,scope=self.scope)['documents'][0]
        identity,version = json.loads(document['metadata']['resource_key'])
        selection = PreparationDocumentRef(resource_id=identity,resource_version=version,
            document_id=document['id'],content_sha256=hashlib.sha256(document['text'].encode()).hexdigest())
        client = DocumentSearchClient(build_document_search_params(Path.cwd(),self.environ,unlimited_text=True))
        result = client.fetch_preparation_documents([selection],scope=self.scope)
        self.assertFalse(result['truncated'])
        self.assertEqual(result['documents'][0]['text'],document['text'])
        with self.assertRaises(ValueError):
            client.fetch_preparation_documents([selection],scope=SearchScope(mode='LEARNING',resource_keys=(resource_key(identity,version),)))
