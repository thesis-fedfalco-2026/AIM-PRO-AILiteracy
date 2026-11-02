# SCN01 with real WP3/MCP retrieval — 2 November 2026

## Result

The local authoring pipeline completed with real PostgreSQL/MCP retrieval and
the configured free OpenRouter model, returning a pending local proposal.
AIM-PRO and the source export were unchanged. No human decision, application,
ResourceBinding, evidence, occurrence or learner state was created.

- Model: `nvidia/nemotron-3.5-super-vl:free`, no paid fallback.
- Source scope: `wp3`, explicitly authorized only in the example policy.
- Query: `"prompt engineering"`, k=1, MCP stdio with unlimited metadata/text.
- Retrieved resource: `wp3:32c2119d5504`.
- Version: `31057b5b35cfcfa5f31ee406f855477a`.
- Title: Prompt Engineering Fundamentals.
- Locator: <https://github.com/microsoft/generative-ai-for-beginners/blob/main/04-prompt-engineering-fundamentals/README.md>.
- Corpus licence assertion: MIT; not a local approval.
- Generation: 108.84 seconds; semantic review: 60.27 seconds, ACCEPT.
- Proposal: `proposal-62609be9f9e14503a73802d5799603ab`, version `1`, AWAITING_DECISION.

The draft contains five learner-facing activities with complete supporting
transcript/examples/worksheets and five citations to the exact retrieved
resource version and segment. Generated material candidates have `derivedFrom`
links to the corpus Resource candidate. Their provenance also preserves the
specific segment ids and supported claims. Original excerpts and complete
retrieval metadata remain in the proposed input-snapshot Resource.

The reviewer accepted material completeness, learner-activity relevance and
substantive citation support. This is a model judgment, not a teacher approval
or a general grounding-quality benchmark. The original source still lacks
LearningTarget resources and retains its D04 vocabulary findings; the local
corpus evidence does not rewrite that external source.

## What the live test exposed

A first request returned an otherwise structured draft but serialized the
combined resource key without JSON quotes. Exact-key validation rejected it
before semantic review or proposal storage. The local citation contract was
changed to request identity and version as separate fields; the host now
serializes the combined key. No malformed key is repaired or accepted by fuzzy
matching. The next explicit request succeeded. The original failed request is
preserved separately as `scn01-grounded/`; there was no automatic retry.

Read-only exploratory queries also illustrated lexical-search limitations:
`"prompt engineering"` returned relevant introductory Microsoft material,
while `"generative AI"` returned work on physical-object fabrication. Retrieved
presence and an open licence do not establish relevance to D04 or the SME task.

## Reproduce with an explicitly authorized local policy

Keep ordinary `propose` and `read` subject permissions for the context. Add a
source grant to the selected policy only when the operator intends this access:

```json
{
  "wp3": {
    "contexts": ["scn01-demo"],
    "subjects": ["demo-author"],
    "sources": ["wp3"],
    "operations": ["read"]
  }
}
```

This is the `scopes` section, not a complete policy. It does not authorize a
learner, a LEARNING resource key or an approved binding. Existing demo policies
are not automatically changed. Configure SEARCH_BACKEND and WP3_DATABASE_URL as
described in [the WP3 integration guide](../wp3/integration.md); the CLI loads
the repository `.env` explicitly before launching MCP.

```bash
.venv/bin/python -m learning \
  --db /path/to/state.sqlite --policy /path/to/policy.json \
  --subject demo-author --context scn01-demo \
  generate-aimpro docs/resources/aimpro-megamodel-2026-11-02.json \
  --request-id scn01-wp3-new --source-scope wp3 \
  --query '"prompt engineering"' --k 1
```

A new request invokes real retrieval and the model. Use the existing `decide`
and `apply` operations only after reviewing the exact candidates. Importing the
teaching draft does not create approved source bindings; the precise resource,
requirement, audience and usage scope need a separate reviewed configuration.
Actual learning still requires explicit resource-key permission and progression
rules. Topic-specific selection also needs the appropriate local configuration,
because canonical corpus subjects are preserved separately from generated
scenario outcome/topic projections.

## Local artifacts and verification

The successful run is under
`.cache/aimpro-examples/wp3/scn01-grounded-2/` (ignored by Git):

- `retrieval.json`: actual MCP response, untruncated, with the original segment.
- `model-calls.json`: returned draft and semantic verdict.
- `proposal.json`: exact proposal/candidates, including source version/provenance.
- `teaching-draft.md`: readable teacher-review material and analytic rubrics.
- `state.sqlite`, `policy.json`, `response.json`, `context.json`: isolated example state.

The full suite passes 337 tests with WP3_TEST_DATABASE_URL set, including real
PostgreSQL and MCP round-trip tests. New authoring tests cover scope denial,
metadata/truncation failures, exact resource/version/segment checks, empty
retrieval, replay without a second search, derived-resource provenance and reuse
of the same canonical corpus resource after importing an earlier proposal.

The example was run from the integration implementation recorded in this
repository. Raw model outputs and the example databases remain local, ignored
artifacts; configuration and reproduction instructions are versioned here.
