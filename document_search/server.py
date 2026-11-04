from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Annotated, Any, AsyncIterator, Mapping

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from pydantic import Field

from document_search.backend import SearchBackend, SearchError, SearchResponse, build_backend
from document_search.contracts import PreparationDocumentRef, SearchScope


class _SearchArgumentMiddleware(Middleware):
    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        arguments = context.message.arguments or {}
        if context.message.name == "search_documents" and (
            "query" not in arguments or "scope" not in arguments or arguments.keys() - {"query", "k", "scope"}
        ):
            raise ToolError("Search request failed")
        if context.message.name == 'fetch_preparation_documents' and (
                not {'selections', 'scope'} <= arguments.keys() or arguments.keys() - {'selections', 'scope'}):
            raise ToolError('Exact source selection failed')
        return await call_next(context)


def create_server(environ: Mapping[str, str] | None = None) -> FastMCP:
    backend: SearchBackend = build_backend(environ)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            backend.close()

    server = FastMCP(
        "Document Search",
        lifespan=lifespan,
        mask_error_details=True,
        strict_input_validation=False,
        middleware=[_SearchArgumentMiddleware()],
    )

    @server.tool(name="search_documents", description="Search authorized WP3 PostgreSQL resources or the configured search backend.")
    def search_documents(
        query: Annotated[Any, Field(json_schema_extra={"type": "string", "minLength": 1})],
        scope: SearchScope,
        k: Annotated[Any, Field(json_schema_extra={"type": "integer", "minimum": 1, "maximum": 20})] = 5,
    ) -> SearchResponse:
        try:
            return SearchResponse.model_validate(backend.search_documents(query, k, scope=scope))
        except (SearchError, ValueError):
            raise ToolError("Search request failed") from None

    # This host-only operation is never added to worker registries. Unsupported
    # backends do not expose a fallback to unpinned discovery.
    if callable(fetch := getattr(backend, 'fetch_preparation_documents', None)):
        @server.tool(name='fetch_preparation_documents', description='Fetch exact content-pinned excerpts under a PREPARATION source scope.')
        def fetch_preparation_documents(selections: list[PreparationDocumentRef], scope: SearchScope) -> SearchResponse:
            try:
                return SearchResponse.model_validate(fetch(selections, scope=scope))
            except (SearchError, ValueError):
                raise ToolError('Exact source selection failed') from None

    return server


if __name__ == "__main__":
    create_server(os.environ).run(transport="stdio", show_banner=False)
