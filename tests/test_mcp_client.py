from document_search.contracts import SearchScope, resource_key

TEST_SCOPE = SearchScope(mode="PREPARATION", source_scope_keys=("demo",))

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory, TemporaryFile
import unittest
from unittest.mock import patch

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from agent_system.config import ConfigurationError
from agent_system.mcp_runtime import (
    DocumentSearchClient,
    DocumentSearchError,
    build_document_search_params,
)


ROOT = Path(__file__).resolve().parents[1]


class McpClientTest(unittest.TestCase):
    def test_remote_flow_passes_text_policy_without_forwarding_credentials(self):
        params = build_document_search_params(
            ROOT, {"SEARCH_BACKEND": "mock", "OPENROUTER_API_KEY": "private"},
            unlimited_text=True,
        )
        self.assertEqual(params.env, {
            "LC_ALL": "C", "PYTHONPATH": str(ROOT), "SEARCH_BACKEND": "mock",
            "SEARCH_UNLIMITED_TEXT": "1",
        })

    def test_params_require_explicit_supported_backend(self):
        for environ in ({}, {"SEARCH_BACKEND": ""}, {"SEARCH_BACKEND": " "},
                        {"SEARCH_BACKEND": "unknown"}):
            with self.subTest(environ=environ), self.assertRaisesRegex(
                ConfigurationError, "^Invalid search backend$"
            ):
                build_document_search_params(ROOT, environ)

    def test_mock_params_use_fixed_command_and_minimal_environment(self):
        params = build_document_search_params(
            ROOT,
            {
                "SEARCH_BACKEND": "mock",
                "VLLM_API_KEY": "do-not-forward",
                "HF_TOKEN": "do-not-forward",
                "OPENAI_API_KEY": "do-not-forward",
                "QDRANT_URL": "do-not-forward-in-mock-mode",
            },
        )

        self.assertEqual(params.command, sys.executable)
        self.assertTrue(Path(params.command).is_absolute())
        separator = params.args.index("--")
        self.assertEqual(params.args[0], "-c")
        self.assertEqual(set(params.args[2:separator]), set(params.env))
        self.assertEqual(params.args[separator + 1:], ["-m", "document_search.server"])
        self.assertEqual(
            params.env,
            {"LC_ALL": "C", "PYTHONPATH": str(ROOT), "SEARCH_BACKEND": "mock"},
        )

    def test_qdrant_params_allow_only_search_configuration(self):
        params = build_document_search_params(
            ROOT,
            {
                "SEARCH_BACKEND": "qdrant",
                "QDRANT_URL": "http://qdrant",
                "QDRANT_API_KEY": "qdrant-secret",
                "QDRANT_COLLECTION": "documents",
                "EMBEDDING_URL": "http://embedder",
                "EMBEDDING_API_KEY": "embedding-secret",
                "EMBEDDING_MODEL": "embedding-model",
                "EMBEDDING_DIMENSIONS": "3",
                "VLLM_API_KEY": "do-not-forward",
                "HF_TOKEN": "do-not-forward",
                "OPENAI_API_KEY": "do-not-forward",
            },
        )

        self.assertEqual(
            params.env,
            {
                "LC_ALL": "C",
                "PYTHONPATH": str(ROOT),
                "SEARCH_BACKEND": "qdrant",
                "QDRANT_URL": "http://qdrant",
                "QDRANT_API_KEY": "qdrant-secret",
                "QDRANT_COLLECTION": "documents",
                "EMBEDDING_URL": "http://embedder",
                "EMBEDDING_API_KEY": "embedding-secret",
                "EMBEDDING_MODEL": "embedding-model",
                "EMBEDDING_DIMENSIONS": "3",
            },
        )

    def test_real_mock_server_returns_validated_document(self):
        client = DocumentSearchClient(
            build_document_search_params(ROOT, {"SEARCH_BACKEND": "mock"})
        )

        result = client.search("deployment", 1, scope=TEST_SCOPE)

        document = result["documents"][0]
        self.assertEqual(document["id"], "mock-technical")
        self.assertEqual(document["metadata"]["source"], "technical-deployment-guide")
        self.assertTrue(document["metadata"]["synthetic"])

    def test_real_mock_server_error_is_sanitized(self):
        client = DocumentSearchClient(
            build_document_search_params(ROOT, {"SEARCH_BACKEND": "mock"})
        )

        with self.assertRaisesRegex(
            DocumentSearchError, "^Document search failed$"
        ):
            client.search("", 1, scope=TEST_SCOPE)

    def test_invalid_server_output_is_sanitized(self):
        client = DocumentSearchClient(
            build_document_search_params(ROOT, {"SEARCH_BACKEND": "mock"})
        )

        with patch(
            "agent_system.mcp_runtime.SearchResponse.model_validate",
            side_effect=ValueError("SENTINEL_PRIVATE"),
        ):
            with self.assertRaisesRegex(
                DocumentSearchError, "^Document search failed$"
            ) as raised:
                client.search("deployment", 1, scope=TEST_SCOPE)

        self.assertNotIn("SENTINEL_PRIVATE", str(raised.exception))


class McpChildEnvironmentTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_child_receives_exact_approved_environment(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "document_search"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "server.py").write_text(
                """import json
import os
import sys

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    if request["method"] == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {},
            "serverInfo": {"name": "environment-probe", "version": "1"},
        }
    elif request["method"] == "tools/list":
        result = {"tools": [{
            "name": "child_environment",
            "description": "Report the process environment.",
            "inputSchema": {"type": "object", "properties": {}},
        }]}
    else:
        result = {
            "content": [],
            "structuredContent": {"environment": dict(os.environ)},
            "isError": False,
        }
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
""",
                encoding="utf-8",
            )
            params = build_document_search_params(
                root,
                {
                    "SEARCH_BACKEND": "mock",
                    "HF_TOKEN": "do-not-forward",
                    "OPENAI_API_KEY": "do-not-forward",
                },
            ).model_copy(update={"cwd": str(root)})

            with TemporaryFile(mode="w+") as stderr:
                try:
                    async with stdio_client(params, errlog=stderr) as (read, write):
                        async with ClientSession(read, write) as session:
                            await asyncio.wait_for(session.initialize(), timeout=5)
                            result = await asyncio.wait_for(
                                session.call_tool("child_environment", {}), timeout=5
                            )
                except BaseException:
                    stderr.seek(0)
                    self.fail(stderr.read())

            self.assertFalse(result.isError)
            self.assertEqual(
                result.structuredContent["environment"],
                {
                    "LC_ALL": "C",
                    "PYTHONPATH": str(root),
                    "SEARCH_BACKEND": "mock",
                },
            )


if __name__ == "__main__":
    unittest.main()
