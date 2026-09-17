# CrewAI multi-agent orchestrator

This repository runs a fixed local topology: a CrewAI Lead agent, six checked-in
worker agents, one local vLLM generation service, one local vLLM embedding
service, Qdrant, and short-lived MCP document-search sessions.

## Prerequisites

- Docker Compose 2.20.3 or newer.
- Python 3 with a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

- Accepted Hugging Face licenses for `google/gemma-3-4b-it` and
  `google/embeddinggemma-300m`.

## Environment

Create `.env` directly with the values for this machine.

| Variable | Status | Example |
| --- | --- | --- |
| `GENERATION_MODEL_ID` | required | `google/gemma-3-4b-it` |
| `EMBEDDING_MODEL_ID` | required | `google/embeddinggemma-300m` |
| `VLLM_API_KEY` | required | `local-development` |
| `SEARCH_BACKEND` | required | `mock` |
| `HF_TOKEN` | provisioning-only | `hf_your_token` |
| `EMBEDDING_API_KEY` | required when `SEARCH_BACKEND=qdrant` | `local-embedding-development` |
| `QDRANT_URL` | required when `SEARCH_BACKEND=qdrant` | `http://127.0.0.1:6333` |
| `QDRANT_API_KEY` | optional, use only when Qdrant is configured with one | `local-qdrant-key` |
| `QDRANT_COLLECTION` | required when `SEARCH_BACKEND=qdrant` | `documents` |
| `EMBEDDING_URL` | required when `SEARCH_BACKEND=qdrant` | `http://127.0.0.1:9000/v1/embeddings` |
| `EMBEDDING_MODEL` | required when `SEARCH_BACKEND=qdrant` | `local-embedding` |
| `EMBEDDING_DIMENSIONS` | required when `SEARCH_BACKEND=qdrant` | `768` |

`HF_TOKEN` may be present locally for provisioning. It must be absent from
runtime containers; the Compose services do not pass it through.

## One-Time Model Download

Run this after accepting the model licenses. It populates the shared Hugging
Face cache volume used later by the offline services:

```bash
read -rsp "Hugging Face token: " HF_TOKEN && echo
export HF_TOKEN
GENERATION_MODEL_ID=google/gemma-3-4b-it \
EMBEDDING_MODEL_ID=google/embeddinggemma-300m \
docker compose run --rm --no-deps \
  -e HF_TOKEN \
  -e GENERATION_MODEL_ID \
  -e EMBEDDING_MODEL_ID \
  -e HF_HUB_OFFLINE=0 \
  --entrypoint python \
  vllm-generation \
  -c 'import os; from huggingface_hub import snapshot_download; [snapshot_download(repo_id=os.environ[name], token=os.environ["HF_TOKEN"]) for name in ("GENERATION_MODEL_ID", "EMBEDDING_MODEL_ID")]'
unset HF_TOKEN
```

## Startup

Normal runtime is offline with no `HF_TOKEN`:

```bash
docker compose up -d
```

The generation service listens on `127.0.0.1:8000`, the embedding service on
`127.0.0.1:9000`, Qdrant HTTP on `127.0.0.1:6333`, and Qdrant gRPC on
`127.0.0.1:6334`.

## Run

```bash
.venv/bin/python main.py "Plan a reliable document-processing service"
```

## Orchestration Flow

The Lead produces a structured plan, the application validates it, the
Orchestrator invokes MCP retrieval for approved retrieval steps, `TaskTool`
runs one worker at a time with supplied context, and the Lead synthesizes the
final answer from worker results.

The Lead is only the logical requester of retrieval. The technical invoker is
the Orchestrator, which opens a short MCP stdio session for each retrieval via
`python -m document_search.server`, passes only the allowed search environment,
and closes that session after the result.

`agent-v` and `agent-w` keep `tools: [search_documents]` only as authorization
metadata. Their prompts analyze retrieved context supplied in the task. The
other four workers declare `tools: []`.

## Retrieval Prompts

EmbeddingGemma query text is prefixed exactly once as:

```text
task: search result | query: ...
```

Documents in an external Qdrant collection should be embedded with:

```text
title: {title} | text: {content}
```

When no title exists, use:

```text
title: none | text: {content}
```

The external collection must use 768-dimensional vectors for
`google/embeddinggemma-300m`. This project never populates Qdrant; create and
load that collection outside this repository. Stored payloads must include
nonblank `text` and `metadata.source` fields so workers can cite sources.

## Limitations

The `mock` backend is synthetic and local. It is useful for tests and smoke
checks, not for real evidence.

Qdrant mode only queries a pre-existing external collection. Missing,
wrong-dimension, or poorly prompted embeddings will produce poor retrieval.

Runtime limits are intentionally small: generation has 8 CPUs and 12 GiB,
embedding has 2 CPUs and 2.25 GiB, and Qdrant has 1 CPU and 1 GiB. The two vLLM
services do not fit concurrently on the validated 16 GB development machine
without quantization; use the generation-only mock smoke command above. CPU
vLLM may fail or be slow on hosts without the expected x86_64 CPU features such
as AVX2. Worker execution is sequential, and the checked-in LLM timeout is 600
seconds.

## Tests And Smoke Checks

Automated tests:

```bash
.venv/bin/python -m unittest discover -v
```

Manual smoke checklist:

- `docker compose ps` shows `vllm-generation` healthy.
- `curl http://127.0.0.1:8000/health` returns success.
- The Lead returns a valid structured `ExecutionPlan`.
- `.venv/bin/python main.py "Summarize the mock deployment procedure"` returns
  an answer in `SEARCH_BACKEND=mock`, proving the mock pipeline runs end to end.
- Logs show no OOM kill, memory-limit exit, CPU feature failure, missing
  model-cache error, or authentication error.

## Cache Removal

`docker compose down` stops services and keeps caches. `docker compose down -v`
also deletes the Hugging Face, vLLM, and Qdrant volumes; after that, models must
be downloaded again before offline startup will work.
