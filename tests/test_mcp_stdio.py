from document_search.contracts import SearchScope, resource_key

TEST_SCOPE = SearchScope(mode="PREPARATION", source_scope_keys=("demo",))

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryFile
import unittest
from unittest.mock import patch

from fastmcp import Client
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from document_search.backend import SearchError
from document_search.server import create_server


ROOT = Path(__file__).resolve().parents[1]


class McpStdioTest(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_discovery_and_mock_search_return_fixture_content(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "document_search.server"],
            cwd="/tmp",
            env={"SEARCH_BACKEND": "mock", "PYTHONPATH": str(ROOT)},
        )
        with TemporaryFile(mode="w+") as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(read, write) as client:
                    await asyncio.wait_for(client.initialize(), timeout=5)
                    listing = await asyncio.wait_for(client.list_tools(), timeout=5)
                    self.assertEqual([tool.name for tool in listing.tools], ["search_documents"])
                    schema = listing.tools[0].inputSchema
                    self.assertEqual(schema["properties"]["query"]["type"], "string")
                    self.assertEqual(schema["properties"]["query"]["minLength"], 1)
                    self.assertEqual(schema["properties"]["k"]["type"], "integer")
                    self.assertEqual(schema["properties"]["k"]["minimum"], 1)
                    self.assertEqual(schema["properties"]["k"]["maximum"], 20)
                    output = listing.tools[0].outputSchema
                    self.assertEqual(set(output["required"]), {"documents"})
                    document = output["properties"]["documents"]["items"]
                    self.assertEqual(set(document["required"]), {"id", "text", "metadata", "score"})
                    self.assertEqual(document["properties"]["id"]["type"], "string")
                    self.assertEqual(document["properties"]["text"]["type"], "string")
                    self.assertEqual(document["properties"]["metadata"]["type"], "object")
                    self.assertEqual(document["properties"]["score"]["type"], "number")
                    self.assertEqual(output["properties"]["truncated"]["type"], "boolean")
                    result = await asyncio.wait_for(
                        client.call_tool("search_documents", {"scope": TEST_SCOPE.model_dump(mode="json"), **{"query": "deployment", "k": 1}}), timeout=5
                    )
                    self.assertFalse(result.isError)
                    self.assertEqual(result.structuredContent["documents"][0]["id"], "mock-technical")
                    self.assertEqual(
                        result.structuredContent["documents"][0]["metadata"]["source"], "technical-deployment-guide"
                    )
                    self.assertTrue(result.structuredContent["documents"][0]["metadata"]["synthetic"])

    async def test_stdio_invalid_input_is_an_error_response_without_leaking_values(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "document_search.server"],
            cwd="/tmp",
            env={"SEARCH_BACKEND": "mock", "PYTHONPATH": str(ROOT)},
        )
        with TemporaryFile(mode="w+") as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(read, write) as client:
                    await asyncio.wait_for(client.initialize(), timeout=5)
                    for arguments in (
                        {"query": {"value": "SENTINEL_PRIVATE"}, "k": 1},
                        {"k": "SENTINEL_PRIVATE"},
                        {"query": "deployment", "extra": "SENTINEL_PRIVATE"},
                    ):
                        with self.subTest(arguments=arguments):
                            result = await asyncio.wait_for(
                                client.call_tool("search_documents", {"scope": TEST_SCOPE.model_dump(mode="json"), **arguments}), timeout=5
                            )
                            content = "\n".join(
                                block.text for block in result.content if hasattr(block, "text")
                            )
                            self.assertTrue(result.isError)
                            self.assertIn("Search request failed", content)
                            self.assertNotIn("SENTINEL_PRIVATE", content)
            stderr.seek(0)
            self.assertNotIn("SENTINEL_PRIVATE", stderr.read())

    async def test_backend_failure_does_not_return_empty_result(self):
        backend = type("Backend", (), {
            "search_documents": lambda self, query, k, *, scope: (_ for _ in ()).throw(SearchError("SENTINEL_PRIVATE")),
            "close": lambda self: None,
        })()
        with patch("document_search.server.build_backend", return_value=backend):
            server = create_server({})
            async with Client(server) as client:
                result = await client.call_tool(
                    "search_documents", {"scope": TEST_SCOPE.model_dump(mode="json"), **{"query": "deployment", "k": 1}}, raise_on_error=False
                )
        content = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        self.assertTrue(result.is_error)
        self.assertIn("Search request failed", content)
        self.assertNotIn("SENTINEL_PRIVATE", content)
