# ALM prototype with CrewAI agents

Local application for managing an ALM learning context with state and tracking in SQLite. A Lead agent plans tasks, specialized agents produce responses, and code checks permissions, sources and results. Generation uses OpenRouter by default; search uses the WP3 PostgreSQL corpus through MCP, with mock data for synthetic tests and optional Qdrant/TEI retrieval.

- [ALM metamodel 1.0.0](docs/resources/metamodello-agnostico-apprendimento.json)
- [Domain specification](docs/resources/2026-10-27-specifica.md)

Work on the AIM-PRO integration starts with the [SCN01 integration review and issue dependency path](docs/aimpro/scn01-conceptual-review.md).
The [2 November 2026 jjodel project](docs/resources/aimpro-megamodel-2026-11-02.json)
is preserved as exported. Run `python3 -m aimpro.audit` to inspect `SCN01` and
`elena_usecase_competencies`; this inspection does not migrate the ALM runtime.
The AIM-PRO metamodel is externally owned and remains unchanged. Run
`.venv/bin/python -m aimpro.adapter` to export the resolved scenario closure for
authoring review, preserving raw values, source identities and diagnostics.
This envelope is for authoring review and does not authorize learning execution.
Generated Pydantic domain classes preserve the external declarations, including
free-text fields. Run `.venv/bin/python -m aimpro.generate --check` to verify the
checked-in concrete schemas and fingerprint, or `.venv/bin/python -m aimpro.validation`
to inspect the scenario against those contracts. Validation reports source gaps
and records scalar/list transport conversions while retaining the original data.
Run `.venv/bin/python -m aimpro.lead` to prepare the Lead input without calling
a model. Add `--run` to request a structured review from the configured Lead.
This path builds only the Lead, preserves deterministic findings in its result,
and does not invoke workers, retrieval, approvals or SQLite writes. It uses the
Lead profile and credentials from the existing configuration and `.env`.

To generate teaching units, materials, activities and proposed analytic rubrics,
use `python -m learning` with the required `--db`, `--policy`, `--subject` and
`--context` options, followed by
`generate-aimpro docs/resources/aimpro-megamodel-2026-11-02.json --request-id teaching-1`.
This requires `propose` permission and a `PREPARATION/DRAFT` context. The configured
Lead generates and semantically reviews a draft, then the service stores a
pending proposal in the existing SQLite lifecycle. Review it through `decide`
and apply it through `apply`; neither operation starts learning or records
learner achievement. Required resources and progression rules remain explicit
gaps before activation. See the [integration workflow](docs/aimpro/scn01-conceptual-review.md#teaching-generation-and-local-execution-state).
For WP3-backed drafting, append `--source-scope wp3 --query '"prompt engineering"' --k 1`.
The policy must explicitly authorize read access to source `wp3` for that subject
and context. Retrieval uses the existing MCP client with full metadata, retains
exact resource versions and excerpt citations, and proposes source resources
without approving bindings. Empty or truncated retrieval does not silently
fall back to ungrounded generation.

## Installation

Python 3 is required, along with Docker Compose 2.20.3 or later only for real search.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configuration

For the real WP3 corpus, follow the [WP3 setup and architecture decision](docs/wp3/integration.md): `SEARCH_BACKEND=postgres` and `docker compose up -d --wait wp3-postgres`. PostgreSQL persists the restored dump in a named volume and search uses the existing local MCP server.

Create `.env` in the project root. For testing with synthetic documents, set `OPENROUTER_API_KEY` and `SEARCH_BACKEND=mock`. This mode does not require Docker. Do not add the key to the repository.

The Lead and specialized agents select their profiles in `control/lead.md` and `agents/*.md`, respectively. `model.properties` defines the provider, model and credential variable name; `runtime.properties` defines the Lead, generation parameters and limits. The included OpenRouter model ends in `:free` and does not automatically switch to a paid model. Using a paid model requires `allow_paid = true` in its profile.

To search real documents, set `SEARCH_BACKEND=qdrant` and configure the following variables in `.env`:

| Variable | Purpose |
| --- | --- |
| `EMBEDDING_MODEL_ID` | Model loaded by TEI, such as `google/embeddinggemma-300m` |
| `QDRANT_URL`, `QDRANT_COLLECTION` | Qdrant endpoint and collection |
| `EMBEDDING_URL`, `EMBEDDING_MODEL` | Endpoint and model name for embedding requests |
| `EMBEDDING_DIMENSIONS`, `EMBEDDING_API_KEY` | Vector dimension and credential sent to the embedding endpoint |
| `QDRANT_API_KEY` | Optional, only if required by Qdrant |

After accepting the embedding model license, populate the shared cache once before starting TEI offline.

`HF_TOKEN` is needed only for the initial download and is not passed to running services. Start vector services with `docker compose --profile vector up -d tei-embedding qdrant`; TEI listens on `127.0.0.1:9000` and Qdrant on `127.0.0.1:6333` (HTTP) and `6334` (gRPC).

This project **does not create or populate** the Qdrant collection. Document ingestion is external: EmbeddingGemma requires 768-dimensional vectors and data with `text`, `metadata.source` and `metadata.source_scope` for PREPARATION, or `metadata.resource_key` for LEARNING. PREPARATION search requires an authorized source scope; LEARNING requires bound, approved resources with exact versions.

## Local ALM workflow

Orchestration uses a new CrewAI Flow for every request: `@start` prepares and authorizes the plan, `@router` selects steps in dependency order, and `@listen` executes them and starts final synthesis. Each executable step is a CrewAI `Task` (`DelegatedTask`) with `output_pydantic=WorkerOutput` and a guardrail applying semantic review and the checks in `learning/`. The adapter preserves delegation through `TaskTool`, without automatic retries after rejection. Steps depending on failed results are skipped; independent steps continue.

The Flow keeps only an execution cursor in CrewAI state; automatic memory and Flow persistence are disabled. Permissions, snapshots, results and changes remain under the control of `learning/` and the existing SQLite service.

Operational `python -m learning` commands require `--db`, `--policy`, `--subject` and `--context` before the subcommand. Use `--help` to see `bootstrap`, `propose`, `decide`, `apply`, `abandon`, `ask`, `submit` and `show`.

The CLI is intended for a trusted local operator: `--subject` selects a person; it **does not authenticate** a remote person. Protect the policy file and database at the host level. A generated response neither approves proposals nor automatically assigns learner progress.

`bootstrap` rejects an existing context: use a new database to repeat the example. If `ask` is interrupted after reserving `demo-ask-1`, an authorized administrator may run `alm abandon demo-ask-1`; the next attempt requires a new ID. `submit` records an observed response, but an evaluation must be proposed, approved and applied separately.

## Data and verification

The SQLite path is always the one supplied with `--db`; there is no default database. Opening a schema v1 database creates a private `.v1.bak` copy (or `.v1.N.bak` if one already exists) and migrates it to v2: stop other writers before opening it. The previous application version cannot read v2; restoring the v1 backup after new writes discards those writes.

Legacy specialization names are not migrated automatically: `teacher` → `lesson-explainer`, `trainer` → `guided-practice-coach`, `socratic` → `reasoning-questioner`. For `curator`, choose `lesson-support-summarizer` in LEARNING or `resource-candidate-researcher` in PREPARATION; for `evaluator`, choose `learner-response-evaluator` in LEARNING or `assessment-designer` in PREPARATION. Update specializations through an authorized proposal, review and application, preserving historical versions.

`docker compose down` preserves volumes. **`docker compose down -v` also deletes Qdrant data and model caches**: do not use it without saving the required data.

```bash
.venv/bin/python -m unittest discover -q
.venv/bin/python smoke.py --runs 1
```

Automated tests use synthetic data. `smoke.py` actually calls the free OpenRouter model and uses the MCP protocol, but selects `mock` search: it does not verify the Qdrant collection, TEI or local vLLM.

## Langfuse tracing (optional)

Telemetry is disabled by default. When `LANGFUSE_ENABLED` is absent or `false`, the module neither imports Langfuse/OpenInference nor sends data. Dependencies are included in `requirements.txt` so integration tests with an in-memory exporter can also run.

To start observability alone, without Qdrant, TEI or vLLM:

```bash
docker compose -f compose.local.yml --profile observability up -d
```

The main configuration includes the same profile: `docker compose --profile observability up -d` also starts Qdrant and TEI and requires their configuration. The Langfuse stack includes web, worker, Postgres, ClickHouse, Redis and MinIO, with dedicated volumes. Only web (`127.0.0.1:3000`) and MinIO (`127.0.0.1:9090`, for media) expose host ports; it does not occupy TEI/Qdrant ports. Langfuse images follow major version 4 of the upstream configuration: pin validated digests for persistent installations.

### Initial setup and complete test

1. Install dependencies with `.venv/bin/python -m pip install -r requirements.txt` and start the stack with the preceding command.
2. Open <http://127.0.0.1:3000>. There are no default credentials: choose **Sign up** and create an account, organization and project.
3. In the project, open **Settings → API Keys** and create a Public Key (`pk-lf-...`) and Secret Key (`sk-lf-...`) pair. These differ from the login password.
4. Create a key in [OpenRouter API settings](https://openrouter.ai/settings/keys).
5. Run `openssl rand -hex 32`: copy the result into `LANGFUSE_HASH_SALT`. This value is generated locally, not provided by Langfuse.
6. Create or update `.env` in the repository root with actual values replacing the placeholders:

```dotenv
OPENROUTER_API_KEY=your-openrouter-key
SEARCH_BACKEND=mock
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://127.0.0.1:3000
LANGFUSE_HASH_SALT=your-openssl-result
LANGFUSE_SYNTHETIC_DATA_ONLY=true
```

The preceding block is for testing with synthetic fixtures. Keep `.env` local: do not commit keys or passwords. For a persistent installation, also use private random values for `LF_NEXTAUTH_SECRET`, `LF_SALT`, `LF_ENCRYPTION_KEY` (64 hexadecimal digits), `LF_POSTGRES_PASSWORD`, `LF_CLICKHOUSE_PASSWORD`, `LF_REDIS_PASSWORD` and `LF_MINIO_PASSWORD` (at least 8 characters). Compose defaults are exclusively for local tests with synthetic data. Keep the salt stable to correlate the same person; changing it changes pseudonymous identifiers.

Each `Orchestrator.run` produces a `learning.request` root, grouped by ExecutionContext, with request and response. Beneath the root are Lead generations, plan authorization, steps, client-side MCP search, worker calls, semantic reviews and deterministic checks. OpenInference CrewAI and OpenAI spans nest inside current observations. The OpenAI instrumentor captures prompts, completions, model and tokens, including native streaming OpenRouter calls; structured conversion calls and additional attempts remain visible as separate calls. Span duration measures latency. Monetary costs depend on the model pricing catalog/configuration in Langfuse; the prototype does not estimate them.

Semantic outcomes are categorical scores `ACCEPT` / `REJECT` / `UNCERTAIN`; checks and steps also record `SUCCEEDED` / `FAILED` / `SKIPPED`. The trace includes request ID, metamodel version and fingerprint, per-agent profiles, roles, modes and Git commit. The `python -m learning`, `main.py` and `smoke.py` programs flush the queue before exiting, including on error.

7. Check the configuration, run tests and test the free model. Smoke uses synthetic documents through MCP and requires neither Qdrant nor TEI:

```bash
docker compose -f compose.local.yml --profile observability config --quiet
.venv/bin/python -m unittest tests.test_telemetry -v
LANGFUSE_ENABLED=false .venv/bin/python -m unittest discover -q
.venv/bin/python smoke.py --runs 1
```

8. Wait for `PASS 1/1`: the live test may take a few minutes. Return to the Langfuse project, open **Tracing** and refresh the list. Open the latest `learning.request`: it must contain `lead.call`, `authorize_plan`, a step with `document_search` and `worker.call`, `semantic_review` reviews, synthesis and `check_final_response`. OpenAI/OpenRouter calls show model, tokens and duration; outcomes are visible as scores.

### Diagnosing a failed test

- If no trace appears, check `LANGFUSE_ENABLED=true`, the local endpoint and a key pair from the same project. The process sends observations before exiting.
- `Plan rejected (ValueError)` means checks blocked the plan before task execution: open `authorize_plan` in the trace and read `status_message` and the input plan. `step.agent` is the worker name (`lesson-explainer`); `specialization` is the exact reference with `type: AgentSpecialization`, `id: teacher-demo`, `version: 1` in the smoke fixture. They are not interchangeable.
- If a worker is rejected, read the verdict and reason in `semantic_review` (stage `WORKER`) and codes in `check_worker_output`. Semantic rejection produces a failure outcome even if the model returned text.
- The `app.crewai.com` link belongs to CrewAI's native collector, separate from Langfuse. The prototype disables it; use your local instance to inspect traces.
- The test uses a free model and does not switch to a paid model on errors or unavailability. A successful test verifies integration on synthetic fixtures; it does not guarantee every future generation's outcome.

### Data and retention

Do not use Langfuse Cloud with real data. To also view LEARNING fixture content in smoke, set `LANGFUSE_SYNTHETIC_DATA_ONLY=true`: this declaration disables LEARNING content redaction while retaining pseudonymization. Endpoints under `*.langfuse.com` require explicit `LANGFUSE_SYNTHETIC_DATA_ONLY=true`, to be set only for synthetic fixtures. For real data, use the project's instance. `subject_key` becomes an HMAC SHA-256 with a private salt; masking also covers identities embedded in prompts. In LEARNING mode, all input/output content is conservatively redacted, including automatically captured messages, to prevent learner instructions and evidence from resurfacing through prompts or synthesis. Structure, outcomes, check codes and token metrics remain available. PREPARATION retains content for debugging: do not include unnecessary personal data.

The intended retention window is 30 days. Native automatic deletion requires Langfuse Self Hosted Enterprise: configure the license and `Project Settings → Data Retention = 30`. Headless provisioning supports `LANGFUSE_INIT_ORG_ID/NAME`, `LANGFUSE_INIT_PROJECT_ID/NAME`, `LANGFUSE_INIT_USER_EMAIL/PASSWORD` and project keys: `LANGFUSE_INIT_PROJECT_RETENTION` receives `LANGFUSE_RETENTION_DAYS` (default 30). It does not modify existing projects. Without a license, native retention does not activate: provide an administrative deletion procedure and verify it before collecting real data. `down` preserves data; volume deletion is irreversible and must be planned separately.

References: [CrewAI integration](https://langfuse.com/integrations/frameworks/crewai), [span masking](https://langfuse.com/docs/observability/features/masking), [Compose installation](https://langfuse.com/self-hosting/deployment/docker-compose), [retention and licensing requirements](https://langfuse.com/docs/administration/data-retention).

The prototype disables CrewAI's native cloud collector and stores negative consent in its own `.cache/crewai`, without changing the user's global preferences. Application traces remain directed only to the configured Langfuse endpoint. In the plan, `step.agent` must be the worker's `registryName` (e.g. `lesson-explainer`); `specialization` is the exact `AgentSpecialization` reference (e.g. `teacher-demo`). The prompt explicitly presents authorized pairs; validation continues to reject incorrect references.
