# Local TEI Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run local Gemma generation, EmbeddingGemma inference, Qdrant, and mock-backed multi-agent smoke concurrently on validated 16 GiB machine without quantization or cloud inference.

**Architecture:** Keep vLLM generation, Qdrant, MCP, and Python production code unchanged. Replace only vLLM embedding container with CPU Text Embeddings Inference (TEI), preserving OpenAI-compatible `/v1/embeddings` contract used by `document_search.backend`.

**Tech Stack:** Docker Compose, vLLM CPU 0.28.0, Hugging Face TEI CPU 1.9, EmbeddingGemma 300M, Qdrant 1.19.0, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-18-local-tei-smoke-design.md`

## Global Constraints

- Work only on branch `dev`; do not push.
- Keep `google/gemma-3-4b-it` and `google/embeddinggemma-300m` unquantized.
- Use no cloud inference service.
- Do not populate production Qdrant collection.
- Keep `document_search/`, `agent_system/`, `requirements.txt`, and `model.properties` unchanged.
- Initial implementation changes only `docker-compose.yml`, `tests/test_system.py`, and `README.md`.
- Keep runtime offline; never pass `HF_TOKEN` into runtime containers.
- Preserve `EMBEDDING_URL=http://127.0.0.1:9000/v1/embeddings` and `EMBEDDING_DIMENSIONS=768`.
- Apply 512 MiB generation KV-cache contingency only after observed OOM evidence.

---

### Task 1: Replace embedding container with TEI

**Files:**
- Modify: `tests/test_system.py:752-805`
- Modify: `docker-compose.yml:60-117`

**Interfaces:**
- Consumes: existing `${EMBEDDING_MODEL_ID}` and `huggingface_cache`.
- Produces: `http://127.0.0.1:9000/v1/embeddings` and health endpoint on container port `80`.

- [ ] **Step 1: Rewrite Compose contract test for TEI**

Replace embedding assertions in `ApplicationTest.test_compose_defines_offline_gemma_generation_embedding_and_qdrant`; keep generation and Qdrant assertions:

```python
self.assertEqual(set(compose["services"]), {"vllm-generation", "tei-embedding"})
generation = compose["services"]["vllm-generation"]
embedding = compose["services"]["tei-embedding"]
generation_command = generation["command"]
embedding_command = embedding["command"]

# Keep existing generation command assertions unchanged.

self.assertEqual(
    embedding["image"],
    "ghcr.io/huggingface/text-embeddings-inference:cpu-1.9",
)
self.assertEqual(embedding_command, [
    "--model-id",
    "${EMBEDDING_MODEL_ID:?set EMBEDDING_MODEL_ID in .env}",
    "--dtype",
    "float32",
])
self.assertEqual(generation["ports"], ["127.0.0.1:8000:8000"])
self.assertEqual(embedding["ports"], ["127.0.0.1:9000:80"])

self.assertEqual(generation["environment"]["HF_HUB_OFFLINE"], "1")
self.assertNotIn("HF_TOKEN", generation["environment"])
self.assertEqual(generation["mem_limit"], "12g")
self.assertEqual(generation["cpus"], 8)
self.assertIn("huggingface_cache:/root/.cache/huggingface", generation["volumes"])
self.assertEqual(generation["environment"]["VLLM_API_KEY"], "${VLLM_API_KEY:-}")
self.assertIn("vllm_generation_cache:/root/.cache/vllm", generation["volumes"])

self.assertEqual(embedding["environment"]["HF_HUB_OFFLINE"], "1")
self.assertNotIn("HF_TOKEN", embedding["environment"])
self.assertFalse(any(key.startswith("VLLM_") for key in embedding["environment"]))
self.assertEqual(embedding["mem_limit"], "2.25g")
self.assertEqual(embedding["cpus"], 2)
self.assertEqual(embedding["volumes"], ["huggingface_cache:/data"])
self.assertNotIn("shm_size", embedding)
self.assertNotIn("cap_add", embedding)
self.assertEqual(embedding["security_opt"], ["no-new-privileges:true"])
self.assertEqual(
    set(compose["volumes"]),
    {"huggingface_cache", "vllm_generation_cache"},
)
```

- [ ] **Step 2: Run focused test and verify RED**

```bash
.venv/bin/python -m unittest tests.test_system.ApplicationTest.test_compose_defines_offline_gemma_generation_embedding_and_qdrant -v
```

Expected: failure because current Compose contains `vllm-embedding`.

- [ ] **Step 3: Replace Compose service**

```yaml
  tei-embedding:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
    platform: linux/amd64
    command:
      - --model-id
      - ${EMBEDDING_MODEL_ID:?set EMBEDDING_MODEL_ID in .env}
      - --dtype
      - float32
    environment:
      HF_HUB_DISABLE_TELEMETRY: "1"
      HF_HUB_OFFLINE: "1"
    ports:
      - "127.0.0.1:9000:80"
    volumes:
      - huggingface_cache:/data
    cpus: 2
    mem_limit: 2.25g
    healthcheck:
      test: ["CMD", "curl", "--fail", "--silent", "http://localhost/health"]
      interval: 15s
      timeout: 10s
      retries: 20
      start_period: 10m
    init: true
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    logging:
      driver: local
      options:
        max-size: "10m"
        max-file: "3"
```

Delete `vllm_embedding_cache:` from top-level volumes. Do not alter generation or `compose.databases.yml`.

- [ ] **Step 4: Verify GREEN**

```bash
docker compose config --quiet
.venv/bin/python -m unittest tests.test_system.ApplicationTest.test_compose_defines_offline_gemma_generation_embedding_and_qdrant -v
.venv/bin/python -m unittest tests.test_system.ApplicationTest -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml tests/test_system.py
git commit -m "build: serve embeddings with TEI"
```

---

### Task 2: Document provisioning and smoke boundaries

**Files:**
- Modify: `README.md:3-5`
- Modify: `README.md:25-38`
- Modify: `README.md:64-74`
- Modify: `README.md:123-160`

**Interfaces:**
- Consumes: TEI service from Task 1.
- Produces: exact offline startup, health, embedding, and mock MAS commands.

- [ ] **Step 1: Update topology and environment examples**

Change topology to “one local TEI embedding service”. Change:

```markdown
| `EMBEDDING_MODEL` | required when `SEARCH_BACKEND=qdrant` | `text-embeddings-inference` |
```

Keep model IDs, URL, dimensions, and provisioning-only `HF_TOKEN`.

- [ ] **Step 2: Update startup and limits**

Keep `docker compose up -d`. Document limits: generation 8 CPUs/12 GiB, TEI 2 CPUs/2.25 GiB, Qdrant 1 CPU/1 GiB. State target is validated 16 GiB machine and smoke must inspect restart/OOM state. Keep AVX2, sequential execution, and 600-second timeout warnings.

- [ ] **Step 3: Add exact smoke checks**

```bash
docker compose ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:9000/health
curl --fail http://127.0.0.1:6333/healthz
```

Real embedding check, without `jq`:

```bash
.venv/bin/python -c 'import json, math, urllib.request; request=urllib.request.Request("http://127.0.0.1:9000/v1/embeddings", data=json.dumps({"input":"task: search result | query: deployment", "model":"text-embeddings-inference"}).encode(), headers={"Content-Type":"application/json"}); vector=json.load(urllib.request.urlopen(request, timeout=120))["data"][0]["embedding"]; assert len(vector) == 768 and all(math.isfinite(value) for value in vector); print("embedding ok: 768 finite values")'
```

MAS smoke:

```bash
SEARCH_BACKEND=mock .venv/bin/python main.py \
  "Summarize the mock deployment procedure"
```

State mock validates orchestration and MCP. Real Qdrant retrieval requires external data.

- [ ] **Step 4: Fix cache wording**

Change “Hugging Face, vLLM, and Qdrant volumes” to “Hugging Face, generation vLLM, and Qdrant volumes”. Do not add obsolete-volume cleanup.

- [ ] **Step 5: Verify and commit**

```bash
.venv/bin/python -m unittest tests.test_system.ApplicationTest.test_readme_does_not_put_literal_hf_token_in_shell_history -v
docker compose config --quiet
git diff --check
git add README.md
git commit -m "docs: add local TEI smoke steps"
```

Expected: checks pass before commit.

---

### Task 3: Prove stack on current machine

**Files:**
- No source changes expected.
- Conditional modify: `tests/test_system.py:763-778`
- Conditional modify: `docker-compose.yml:16-32`

**Interfaces:**
- Consumes: cached models, TEI image, Compose services, `.env`, Python environment.
- Produces: health, embedding, MAS, restart, OOM, and memory evidence.

- [ ] **Step 1: Confirm prerequisites without exposing secrets**

```bash
git branch --show-current
docker compose config --quiet
docker image inspect ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
```

Expected: `dev`, valid Compose. If image missing:

```bash
docker compose pull tei-embedding
```

This downloads runtime software, not cloud inference. Never print `.env` or tokens.

- [ ] **Step 2: Start services**

```bash
docker compose up -d --remove-orphans vllm-generation tei-embedding qdrant
```

Expected: local cache used; no runtime `HF_TOKEN`.

- [ ] **Step 3: Wait for bounded health convergence**

Poll `docker compose ps` at intervals shorter than 60 seconds, maximum 10 minutes. Then:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:9000/health
curl --fail http://127.0.0.1:6333/healthz
```

Expected: all succeed.

- [ ] **Step 4: Validate embedding and MAS**

Run README embedding command. Expected:

```text
embedding ok: 768 finite values
```

Run README MAS smoke. Expected: valid plan, optional MCP mock retrieval, sequential workers, non-empty final answer, no cloud call.

- [ ] **Step 5: Capture failure evidence**

```bash
docker stats --no-stream
docker inspect "$(docker compose ps -q vllm-generation)" --format '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}}'
docker inspect "$(docker compose ps -q tei-embedding)" --format '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}}'
docker inspect "$(docker compose ps -q qdrant)" --format '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}}'
```

Expected each: restart `0`, OOM `false`, status `running`.

- [ ] **Step 6: Run full verification**

```bash
timeout 15m .venv/bin/python -m unittest discover -v
git diff --check
git status --short
```

Expected: suite and diff check pass; only intentional changes remain.

---

### Task 4: Reduce generation KV cache only if Task 3 proves OOM

**Condition:** Skip unless evidence shows `vllm-generation` OOM-killed while TEI and Qdrant run.

**Files:**
- Modify: `tests/test_system.py:763-778`
- Modify: `docker-compose.yml:16-32`

**Interfaces:**
- Consumes: OOM evidence from Task 3.
- Produces: exact 512 MiB CPU KV cache instead of 1 GiB environment setting.

- [ ] **Step 1: Add failing assertions**

```python
self.assertNotIn("VLLM_CPU_KVCACHE_SPACE", generation["environment"])
self.assertEqual(
    generation_command[generation_command.index("--kv-cache-memory-bytes") + 1],
    "536870912",
)
```

Run focused Compose test. Expected: RED.

- [ ] **Step 2: Apply exact cache setting**

Delete:

```yaml
VLLM_CPU_KVCACHE_SPACE: "1"
```

Add to generation command:

```yaml
- --kv-cache-memory-bytes
- "536870912"
```

- [ ] **Step 3: Verify and repeat runtime smoke**

```bash
docker compose config --quiet
.venv/bin/python -m unittest tests.test_system.ApplicationTest -v
docker compose up -d --force-recreate vllm-generation
```

Repeat Task 3 Steps 3-6. Accept only with healthy services, zero OOM kills, completed MAS smoke.

- [ ] **Step 4: Commit only when contingency used**

```bash
git add docker-compose.yml tests/test_system.py
git commit -m "fix: reduce local generation KV cache"
```

