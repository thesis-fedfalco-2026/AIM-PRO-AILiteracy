# Local TEI Smoke Design

## Goal

Make the existing local smoke execution usable on the validated Ryzen 5 5600G,
16 GiB RAM machine without quantization or cloud inference. Keep Gemma 3 4B for
generation, replace only the vLLM embedding runtime with a lighter persistent
Text Embeddings Inference (TEI) service, and retain short-lived MCP sessions.

## Scope

The change covers local container wiring, its structural test, and operating
instructions. It does not populate Qdrant, change the MCP protocol, alter the
orchestrator, introduce a new embedding model, or prove retrieval quality.

The smoke has three independent acceptance checks:

1. The multi-agent flow completes against `SEARCH_BACKEND=mock`.
2. TEI generates one real 768-dimensional EmbeddingGemma vector.
3. Qdrant responds to its health endpoint.

Real Qdrant retrieval remains dependent on an externally populated collection.

## Architecture

`vllm-generation` remains the local OpenAI-compatible generation service.
`tei-embedding` becomes the persistent local embedding service and runs
`google/embeddinggemma-300m` using the official CPU TEI image. Qdrant remains
unchanged. The application continues to start a short-lived FastMCP stdio
server for each retrieval call.

TEI exposes the OpenAI-compatible `/v1/embeddings` route already consumed by
`document_search.backend`. Therefore no Python production code or dependency
changes are required.

## Container Configuration

Replace the `vllm-embedding` Compose service with `tei-embedding`:

- Image: `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`.
- Model: `${EMBEDDING_MODEL_ID:?set EMBEDDING_MODEL_ID in .env}`.
- Data type: `float32`; EmbeddingGemma does not support `float16`.
- Host endpoint: `127.0.0.1:9000`, mapped to container port `80`.
- Cache: existing `huggingface_cache`, mounted at `/data`.
- Runtime: `HF_HUB_OFFLINE=1`, with no `HF_TOKEN` passed to the service.
- Limits: 2 CPUs and 2.25 GiB RAM.
- Health check: `curl http://localhost/health` with the existing bounded retry
  policy.

Remove the embedding-only vLLM cache volume and vLLM-specific environment,
shared-memory, capability, and security settings. Preserve restart and bounded
local logging settings.

`vllm-generation`, Qdrant, the shared Hugging Face cache, and the one-time model
download stay unchanged.

## Configuration Contract

Local configuration continues to use:

```dotenv
GENERATION_MODEL_ID=google/gemma-3-4b-it
EMBEDDING_MODEL_ID=google/embeddinggemma-300m
EMBEDDING_URL=http://127.0.0.1:9000/v1/embeddings
EMBEDDING_MODEL=text-embeddings-inference
EMBEDDING_DIMENSIONS=768
```

`EMBEDDING_API_KEY` remains a local placeholder required by the current backend
schema. TEI runs without authentication but accepts the unused authorization
header on the loopback-only endpoint. Changing this schema would expand the
diff without improving the smoke.

## Data Flow

The real retrieval path remains:

1. Lead produces a validated retrieval step.
2. Orchestrator opens a short MCP stdio session.
3. MCP `search_documents` prefixes the query once.
4. Backend posts the query to TEI `/v1/embeddings`.
5. TEI returns a 768-dimensional vector.
6. Backend queries the pre-existing Qdrant collection.
7. MCP returns bounded structured documents to the orchestrator.

The accepted smoke stops short of steps 4-7 as one combined retrieval because
the repository deliberately owns no collection data. It validates TEI and
Qdrant separately, while the existing mock validates orchestration and MCP end
to end.

## Failure Handling

Existing backend sanitization remains responsible for embedding and Qdrant
errors. Compose health checks expose service startup failures. Smoke validation
must inspect container restart counts and OOM state, not only HTTP status.

Initial implementation does not tune generation memory. If concurrent services
cause an OOM, replace the 1 GiB CPU KV-cache setting with vLLM's exact
`--kv-cache-memory-bytes 536870912` option, then repeat the complete smoke. No
quantization, cloud fallback, or swap-based workaround is allowed.

## Verification

Tests must first fail against the current vLLM embedding Compose definition,
then pass after the replacement. Verification includes:

- structural Compose assertions for TEI and removal of vLLM embedding settings;
- `docker compose config --quiet`;
- existing automated tests;
- generation, TEI, and Qdrant health checks;
- one TEI embedding request with exactly 768 finite values;
- one direct `main.py` execution with `SEARCH_BACKEND=mock`;
- restart, OOM, and memory inspection during the smoke.

## Files

- Modify `docker-compose.yml` for the service replacement.
- Modify `tests/test_system.py` for the Compose contract.
- Modify `README.md` for provisioning, startup, and smoke instructions.

No other project files should change unless measured runtime evidence requires
the documented 512 MiB generation KV-cache contingency.
