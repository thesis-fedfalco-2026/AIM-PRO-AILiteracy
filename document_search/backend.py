from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
import json
import math
import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from document_search.contracts import SearchScope, resource_key


MAX_RESULTS = 20
MAX_RESPONSE_CHARS = 4000
RETRIEVAL_QUERY_PREFIX = "task: search result | query: "


class ConfigurationError(RuntimeError):
    """A safe configuration error."""


class SearchError(RuntimeError):
    """A safe search error."""


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    id: str
    text: str = Field(min_length=1)
    metadata: dict[str, Any]
    score: float

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("score")
    @classmethod
    def score_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value

    @field_validator("metadata")
    @classmethod
    def source_must_be_meaningful(cls, value: dict[str, Any]) -> dict[str, Any]:
        source = value.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a nonblank string")
        return value


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    documents: list[Document]
    truncated: bool = False


class QdrantSettings(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    qdrant_url: str = Field(repr=False, min_length=1)
    qdrant_collection: str = Field(min_length=1)
    qdrant_api_key: SecretStr | None = None
    embedding_url: str = Field(repr=False, min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_dimensions: int = Field(gt=0)
    embedding_api_key: SecretStr


def _validate_query(query: str) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be blank")


def _retrieval_query(query: str) -> str:
    stripped = query.strip()
    marker = RETRIEVAL_QUERY_PREFIX.rstrip()
    if stripped.startswith(marker):
        content = stripped.removeprefix(marker).strip()
        if not content:
            raise ValueError("query must not be blank")
        return f"{RETRIEVAL_QUERY_PREFIX}{content}"
    return f"{RETRIEVAL_QUERY_PREFIX}{stripped}"


def _validate_k(k: int) -> None:
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= MAX_RESULTS:
        raise ValueError("k must be an integer between 1 and 20")


def _vector(value: Sequence[float], dimensions: int) -> list[float]:
    try:
        values = list(value)
    except TypeError:
        raise SearchError("Invalid embedding vector") from None
    if len(values) != dimensions or not all(
        isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in values
    ):
        raise SearchError("Invalid embedding vector")
    return [float(item) for item in values]


def _serialized_size(documents: list[dict[str, Any]]) -> int:
    return len(json.dumps(documents, ensure_ascii=False))


def _bounded_documents(documents: list[Document]) -> tuple[list[dict[str, Any]], bool]:
    bounded: list[dict[str, Any]] = []
    truncated = False
    for document in documents:
        candidate = document.model_dump()
        if _serialized_size(bounded + [candidate]) <= MAX_RESPONSE_CHARS:
            bounded.append(candidate)
            continue
        truncated = True
        metadata = candidate["metadata"]
        candidate["metadata"] = {key: metadata[key] for key in
                                 ("source", "resource_key", "source_scope", "synthetic") if key in metadata}
        if _serialized_size(bounded + [candidate]) <= MAX_RESPONSE_CHARS:
            bounded.append(candidate)
            continue
        text = candidate["text"]
        low, high = 1, len(text)
        best = 0
        while low <= high:
            middle = (low + high) // 2
            candidate["text"] = text[:middle]
            if _serialized_size(bounded + [candidate]) <= MAX_RESPONSE_CHARS:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best and candidate["text"][:best].strip():
            candidate["text"] = candidate["text"][:best]
            bounded.append(candidate)
    return bounded, truncated


class SearchBackend:
    def __init__(
        self,
        *,
        embed: Callable[[str], Sequence[float]],
        vector_search: Callable[[list[float], int, SearchScope], Sequence[Mapping[str, Any]]],
        dimensions: int,
        unlimited_text: bool = False,
        close: Callable[[], None] = lambda: None,
    ):
        self._embed = embed
        self._vector_search = vector_search
        self._dimensions = dimensions
        self._unlimited_text = unlimited_text
        self._close = close

    def search_documents(self, query: str, k: int = 5, *, scope: SearchScope) -> dict[str, Any]:
        _validate_query(query)
        _validate_k(k)
        retrieval_query = _retrieval_query(query)
        scope = SearchScope.model_validate(scope)
        if not scope.keys:
            return SearchResponse(documents=[]).model_dump()
        try:
            vector = _vector(self._embed(retrieval_query), self._dimensions)
            raw_documents = self._vector_search(vector, k, scope)
            documents = [Document.model_validate(document) for document in raw_documents]
            if len(documents) > k or any(not scope.matches(document.metadata) for document in documents):
                raise SearchError("Search failed")
        except SearchError:
            raise
        except Exception:
            raise SearchError("Search failed") from None
        try:
            if self._unlimited_text:
                documents, truncated = [document.model_dump() for document in documents], False
            else:
                documents, truncated = _bounded_documents(documents)
        except Exception:
            raise SearchError("Search failed") from None
        return SearchResponse(documents=documents, truncated=truncated).model_dump()

    def close(self) -> None:
        try:
            self._close()
        except Exception:
            raise SearchError("Unable to close search backend") from None


_MOCK_DOCUMENTS = (
    {
        "id": "mock-technical",
        "text": "Technical deployment guide (synthetic): The approved release procedure is to verify the approved release tag, deploy the service through the approved pipeline, and check the service health endpoint. If the health check fails, roll back to the previous approved release.",
        "metadata": {"source": "technical-deployment-guide", "synthetic": True,
                     "resource_key": resource_key("technical-deployment-guide", "1"), "source_scope": "demo"},
        "vector": [1.0, 0.0],
    },
    {
        "id": "mock-reimbursement",
        "text": "Business reimbursement procedure: submit approved expense receipts within 30 days.",
        "metadata": {"source": "business-reimbursement-procedure", "synthetic": True,
                     "resource_key": resource_key("business-reimbursement-procedure", "1"), "source_scope": "demo"},
        "vector": [0.0, 1.0],
    },
)


def _mock_embed(query: str) -> list[float]:
    words = set(query.lower().split())
    if words & {"deployment", "deploy", "technical", "release"}:
        return [1.0, 0.0]
    if words & {"reimbursement", "expense", "receipt", "business"}:
        return [0.0, 1.0]
    return [0.0, 0.0]


def _mock_vector_search(vector: list[float], k: int, scope: SearchScope) -> list[dict[str, Any]]:
    scored = []
    for document in _MOCK_DOCUMENTS:
        if not scope.matches(document["metadata"]):
            continue
        score = sum(left * right for left, right in zip(vector, document["vector"], strict=True))
        if score > 0:
            scored.append({
                "id": document["id"], "text": document["text"], "metadata": document["metadata"], "score": score,
            })
    return sorted(scored, key=lambda document: (-document["score"], document["id"]))[:k]


def _qdrant_settings(environ: Mapping[str, str]) -> QdrantSettings:
    fields = {
        "QDRANT_URL": "qdrant_url",
        "QDRANT_COLLECTION": "qdrant_collection",
        "QDRANT_API_KEY": "qdrant_api_key",
        "EMBEDDING_URL": "embedding_url",
        "EMBEDDING_MODEL": "embedding_model",
        "EMBEDDING_DIMENSIONS": "embedding_dimensions",
        "EMBEDDING_API_KEY": "embedding_api_key",
    }
    try:
        return QdrantSettings(**{field: environ[key] for key, field in fields.items() if environ.get(key)})
    except (ValidationError, ValueError):
        raise ConfigurationError("Invalid Qdrant search configuration") from None


def _http_embedder(settings: QdrantSettings, client: httpx.Client) -> Callable[[str], Sequence[float]]:
    def embed(query: str) -> Sequence[float]:
        try:
            response = client.post(
                settings.embedding_url,
                headers={"Authorization": f"Bearer {settings.embedding_api_key.get_secret_value()}"},
                json={"input": query, "model": settings.embedding_model},
            )
            response.raise_for_status()
            embedding = response.json()["data"][0]["embedding"]
            if not isinstance(embedding, list):
                raise TypeError
            return embedding
        except httpx.HTTPError:
            raise SearchError("Embedding request failed") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise SearchError("Invalid embedding response") from None

    return embed


def build_backend(
    environ: Mapping[str, str] | None = None,
    *,
    embed: Callable[[str], Sequence[float]] | None = None,
    vector_search: Callable[[list[float], int, SearchScope], Sequence[Mapping[str, Any]]] | None = None,
    qdrant_factory: Callable[..., Any] | None = None,
    http_client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> SearchBackend:
    environ = os.environ if environ is None else environ
    backend = environ.get("SEARCH_BACKEND")
    if backend == "postgres":
        from document_search.postgres import build_postgres_backend

        return build_postgres_backend(environ)
    if backend == "mock":
        return SearchBackend(
            embed=embed or _mock_embed,
            vector_search=vector_search or _mock_vector_search,
            dimensions=2,
            unlimited_text=environ.get("SEARCH_UNLIMITED_TEXT") == "1",
        )
    if backend != "qdrant":
        raise ConfigurationError("Invalid search backend")
    settings = _qdrant_settings(environ)
    http_client = None
    client = None
    try:
        http_client = http_client_factory(timeout=10.0)
        if qdrant_factory is None:
            from qdrant_client import QdrantClient

            qdrant_factory = QdrantClient
        args: dict[str, Any] = {"url": settings.qdrant_url, "check_compatibility": False}
        if settings.qdrant_api_key is not None:
            args["api_key"] = settings.qdrant_api_key.get_secret_value()
        client = qdrant_factory(**args)

        def qdrant_search(vector: list[float], k: int, scope: SearchScope) -> list[dict[str, Any]]:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchAny
                points = client.query_points(
                    settings.qdrant_collection, query=vector, limit=k, with_payload=True,
                    query_filter=Filter(must=[FieldCondition(key=f"metadata.{scope.metadata_key}",
                                                           match=MatchAny(any=list(scope.keys)))])
                ).points
                return [
                    {"id": str(point.id), "text": point.payload["text"], "metadata": dict(point.payload.get("metadata", {})), "score": point.score}
                    for point in points
                ]
            except Exception:
                raise SearchError("Search failed") from None

        def close() -> None:
            try:
                if callable(client_close := getattr(client, "close", None)):
                    client_close()
            finally:
                http_client.close()

        return SearchBackend(
            embed=embed or _http_embedder(settings, http_client),
            vector_search=vector_search or qdrant_search,
            dimensions=settings.embedding_dimensions,
            unlimited_text=environ.get("SEARCH_UNLIMITED_TEXT") == "1",
            close=close,
        )
    except Exception:
        with suppress(Exception):
            if callable(client_close := getattr(client, "close", None)):
                client_close()
        with suppress(Exception):
            if http_client is not None:
                http_client.close()
        raise ConfigurationError("Unable to initialize Qdrant search") from None
