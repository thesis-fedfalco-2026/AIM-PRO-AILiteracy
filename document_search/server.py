from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Annotated, Any, AsyncIterator, Mapping

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from pydantic import Field

from document_search.backend import SearchBackend, SearchError, SearchResponse, build_backend


class _SearchArgumentMiddleware(Middleware):
    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        arguments = context.message.arguments or {}
        if context.message.name == "search_documents" and (
            "query" not in arguments or arguments.keys() - {"query", "k"}
        ):
            raise ToolError("Search request failed")
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

    @server.tool(name="search_documents", description="Search synthetic mock documents or the configured Qdrant collection.")
    def search_documents(
        query: Annotated[Any, Field(json_schema_extra={"type": "string", "minLength": 1})],
        k: Annotated[Any, Field(json_schema_extra={"type": "integer", "minimum": 1, "maximum": 20})] = 5,
    ) -> SearchResponse:
        try:
            return SearchResponse.model_validate(backend.search_documents(query, k))
        except (SearchError, ValueError):
            raise ToolError("Search request failed") from None

    return server


if __name__ == "__main__":
    create_server(os.environ).run(transport="stdio", show_banner=False)
