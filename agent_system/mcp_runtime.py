import asyncio
from collections.abc import Mapping
from pathlib import Path
import sys
from tempfile import TemporaryFile
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent_system.config import ConfigurationError
from document_search.backend import SearchResponse
from document_search.contracts import SearchScope


SEARCH_TOOL_NAME = "search_documents"
_QDRANT_ENV_KEYS = (
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "EMBEDDING_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
)
_EXEC_WITH_APPROVED_ENV = (
    "import os,sys; i=sys.argv.index('--'); "
    "env={key:os.environ[key] for key in sys.argv[1:i]}; "
    "os.execve(sys.executable,[sys.executable,*sys.argv[i+1:]],env)"
)


class DocumentSearchError(RuntimeError):
    """A safe document-search error."""


def build_document_search_params(
    base_dir: Path, environ: Mapping[str, str], *, unlimited_text: bool = False,
) -> StdioServerParameters:
    backend = environ.get("SEARCH_BACKEND")
    if backend not in {"mock", "qdrant"}:
        raise ConfigurationError("Invalid search backend")
    server_env = {
        "LC_ALL": "C",
        "PYTHONPATH": str(base_dir.resolve()),
        "SEARCH_BACKEND": backend,
    }
    if unlimited_text:
        server_env["SEARCH_UNLIMITED_TEXT"] = "1"
    if backend == "qdrant":
        server_env.update(
            (key, environ[key]) for key in _QDRANT_ENV_KEYS if environ.get(key)
        )
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-c",
            _EXEC_WITH_APPROVED_ENV,
            *server_env,
            "--",
            "-m",
            "document_search.server",
        ],
        env=server_env,
    )


class DocumentSearchClient:
    def __init__(self, params: StdioServerParameters):
        self.params = params

    def search(self, query: str, k: int, *, scope: SearchScope) -> dict[str, Any]:
        async def call() -> dict[str, Any]:
            with TemporaryFile(mode="w+") as errlog:
                async with stdio_client(self.params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            SEARCH_TOOL_NAME,
                            {"query": query, "k": k, "scope": scope.model_dump(mode="json")},
                        )
            if result.isError or result.structuredContent is None:
                raise DocumentSearchError("Document search failed")
            return SearchResponse.model_validate(
                result.structuredContent
            ).model_dump()

        try:
            return asyncio.run(call())
        except DocumentSearchError:
            raise
        except Exception:
            raise DocumentSearchError("Document search failed") from None
