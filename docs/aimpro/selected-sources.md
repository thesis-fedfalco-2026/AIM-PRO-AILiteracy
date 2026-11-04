# Prepare exact Curator sources before model authorization

This local, unpublished increment separates model-free source preparation from
syllabus generation. It uses real scoped multi-query MCP discovery, exact
document deduplication and content-pinned excerpt fetches. The original
single-query route remains available. Preparation is neither source-use approval
nor a generated syllabus. No external model is called by the preparation command.

For explicit source-anchored planning obligations and deterministic action
coverage, see [the coverage extension](syllabus-coverage.md). Empty extensions
preserve the hashes of earlier packets; new requirements need a new preparation.

## Plan and retrieval

Use an isolated PREPARATION/DRAFT context. The operator needs read/propose and
ADMINISTRATOR or CONTENT_RESPONSIBLE in both policy and recorded participant,
plus explicit source-scope permission. Authorization precedes source reading,
client construction and retrieval. Worker tools/permissions are unchanged.

The strict `SourcePlan` contains `format: aimpro-source-plan`, `format_version: 1`,
the exact scenario-export `source_sha256`, `source_scope`, 1–20 distinct queries
(each with k=1–20), and 1–20 selected excerpts. Each excerpt specifies
`resource_id`, exact `resource_version`, `document_id`, SHA-256 of its original
UTF-8 text, purpose and limitations. `min_resources` and
`max_documents_per_resource` make the intended distribution explicit.

Selected ids/content hashes must be unique, with one version per resource.
Diversity counts resource identities, not independent authors/source families;
translations and related routes still need human selection. Exact repeated
query hits are deduplicated, and conflicting text/metadata fails. Scores may
differ across queries. Top-k is a chunk limit, not full-corpus coverage.

Every selected resource/version must appear in an actual recorded discovery
response. A known exact excerpt from that resource can then be fetched even if
that particular excerpt did not rank in top-k. The PostgreSQL-only MCP operation
`fetch_preparation_documents` accepts an explicit PREPARATION source scope and
at most 20 exact refs/hashes. LEARNING/empty scopes fail before connecting.
SQL is parameterized and read-only; missing ids, versions, hashes or changed
metadata fail closed. No worker registry gains this operation, and unsupported
backends have no fallback to unpinned search.

Exact excerpt text, including whitespace and line endings, survives into the
snapshot and model input. Blank text is rejected. Fetch scores are zero, not
semantic relevance scores. Purposes/limitations are operator context requiring
Lead/human review, not verified pedagogical conclusions.

## Two operations

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m learning \
  --db /path/to/new-run/state.sqlite --policy /path/to/new-run/policy.json \
  --subject author --context preparation \
  prepare-aimpro-syllabus-sources docs/resources/aimpro-megamodel-2026-11-02.json \
  --plan /path/to/new-run/source-plan.json --request-id sources-01 \
  > /path/to/new-run/source-preparation.json
```

Success returns `SOURCE_PREPARATION`: context, exact prepared LeadInput and a
RetrievalTrace containing the plan, complete discovery results, selected excerpts
and duplicate counts. Reservation records context/source/plan before retrieval;
there is no SQLite write lock during MCP. Final storage rechecks current
authority/scope/context/source and atomically finishes the request. Complete
replay avoids retrieval; altered identities conflict. Failures stay failures;
interrupted pending requests need administrative abandonment and a new id.

After reviewing that packet and authorizing model/provider transmission:

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m learning \
  --db /path/to/new-run/state.sqlite --policy /path/to/new-run/policy.json \
  --subject author --context preparation \
  generate-aimpro-syllabus docs/resources/aimpro-megamodel-2026-11-02.json \
  --source-scope wp3 --prepared-sources sources-01 --request-id curator-01
```

Generation consumes a completed same-subject/context preparation from the host
requests store, not an externally supplied JSON response. It reserves the exact
model input and preparation digest before building models and performs no new
retrieval. Only selected excerpts and their query/purpose/limitation summary go
to the models. Unselected discovery text remains in the local audit.

Final-lock checks cover authority, scope, context, source export, pending
reservation and unchanged preparation. Proposal/candidates/result persist
atomically. REJECT/UNCERTAIN, abandonment or partial persistence leaves no
accepted proposal. Complete replay remains exact after application. A separate
ALM Resource preserves the full audit and is linked from the source snapshot;
the proposal records its digest. All selected corpus resources belong to the
joint reviewed input, including assessment context not cited by a particular
syllabus unit, so downstream Evaluator tasks can use that exact approved context.
Human decisions/application, project initialization and learner resource bindings
remain separate. No schema migration or external metamodel/export edits occur.

## SCN01 package prepared on 3 November 2026

Ignored directory: `.cache/aimpro-examples/curator/scn01-selected-sources-1/`.
Context `scn01-selected-syllabus`, subject `syllabus-author`, PREPARATION/DRAFT.
Three actual queries (`"prompt engineering"`, `rubric OR rubrics`, `prompt teaching`,
k=20 each) produced 60 hits: 57 distinct document ids and three repeats.

| Exact resource/version | Selected chunk suffixes | Intended use / limitation |
| --- | --- | --- |
| `wp3:32c2119d5504` / `31057b5b35cfcfa5f31ee406f855477a` | 3, 4, 6, 7 | Prompt construction, examples/context/clarity; notebook/API setup and illustrative lengths are not SCN01 requirements. |
| `wp3:12ce471a0269` / `1111cea0926dac4935b24bdf54ea8a55` | 2, 4 | Conditional reflection/feedback/rubric background; grades 6–12 perspective, not a validated adult-SME instrument. Do not import points/passing rules. |
| `wp3:4868ba8731b3` / `7ace1e7ee4f206b3ef9f729cb1f6efaa` | 0 | Validity/accountability context; no SCN01 instrument or threshold. |

Preparation `scn01-sources-01` failed closed when the old CorpusDocument transport
stripped whitespace, conflicting with raw excerpt hashes. That normalization was
corrected and regression-tested; the failed record is preserved. Preparation
**`scn01-sources-02`** succeeded via real MCP/PostgreSQL, and its completed replay
was verified with retrieval/model factories forbidden.

`source-preparation-02.json` is the full packet, `model-input.json` the exact
Curator data, `source-replay.json` the replay evidence and `RUN_REVIEW.md` the
proposed live command/transmission scope. The subsequent owner-authorized
[real Curator run](scn01-selected-curator-example.md) produced a draft rejected
by the Lead for missing learner practice: no proposal or human decision/application
was persisted. The original trial remains unchanged/pending.

## Verification

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m unittest \
  tests.test_source_selection tests.test_aimpro_syllabus tests.test_aimpro_retrieval \
  tests.test_authoring_generators tests.test_authoring_projects tests.test_authoring_cycle \
  tests.test_mcp_client tests.test_document_search tests.test_learning_cli -v
.venv/bin/python -m aimpro.generate --check
git diff --check
```

The source-selection suite blocks sockets/DNS and uses temporary databases and
synthetic responses. It covers authorization, deduplication/conflicts, exact
content fidelity, missing/changed selections, reservation, replay, stale source/
context, rollback, abandonment, review rejection/uncertainty, CLI separation and
retained assessment-context sources. Full regression also enables the real
read-only PostgreSQL/MCP tests and exact-fetch round trip. Remote CI is narrower;
no remote result is claimed for this uncommitted increment.

Observed local validation on 3 November 2026: **454 full-regression tests pass,
with no skips and the real PostgreSQL/MCP reader enabled**, including the new
exact-fetch round trip and whitespace-fidelity regression. Generated-contract and whitespace
checks pass. No external model, approval, commit or push was used for validation.
