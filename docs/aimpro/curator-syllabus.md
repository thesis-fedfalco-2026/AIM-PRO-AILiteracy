# Delegated Curator syllabus authoring — issue #8

`generate-aimpro-syllabus` delegates syllabus generation to the configured
`syllabus-designer` Curator and uses a separate Lead call for semantic review.
It reads the unchanged AIM-PRO project and explicitly authorized WP3 evidence.
The result is a pending ALM proposal, with no teacher decision inferred from a
model's ACCEPT. The existing combined `generate-aimpro` teaching-draft route is
still available independently.

## Generate in an isolated preparation context

Use a new local directory, a trusted policy and a PREPARATION/DRAFT context.
The subject needs `read`, `propose` and explicit source-scope permission. Initial
bootstrap additionally requires an ADMINISTRATOR with `bootstrap` permission.
Human review/application require their separate `decide`/`apply` grants and roles.

For example, create a policy file for a synthetic authoring-only context:

```json
{
  "policy_ref": {"type": "PolicySet", "id": "scn01-syllabus-policy", "version": "1"},
  "subjects": {
    "syllabus-author": {
      "roles": ["ADMINISTRATOR", "CONTENT_RESPONSIBLE"],
      "actions": {
        "scn01-syllabus": ["read", "bootstrap", "propose", "decide", "apply"]
      }
    }
  },
  "scopes": {
    "wp3": {
      "contexts": ["scn01-syllabus"],
      "subjects": ["syllabus-author"],
      "sources": ["wp3"],
      "operations": ["read"]
    }
  }
}
```

Save it as `/path/to/new-run/policy.json`. These are local synthetic identities,
not remote authentication. No learner is needed. Use the approved reader
configuration in `.env` from [the WP3 guide](../wp3/integration.md); never print
credentials. Run from the repository root:

```bash
export SCN01_SYLLABUS_DIR=/path/to/new-run
.venv/bin/python -m learning \
  --db "$SCN01_SYLLABUS_DIR/state.sqlite" --policy "$SCN01_SYLLABUS_DIR/policy.json" \
  --subject syllabus-author --context scn01-syllabus bootstrap

.venv/bin/python -m learning \
  --db "$SCN01_SYLLABUS_DIR/state.sqlite" --policy "$SCN01_SYLLABUS_DIR/policy.json" \
  --subject syllabus-author --context scn01-syllabus \
  generate-aimpro-syllabus docs/resources/aimpro-megamodel-2026-11-02.json \
  --request-id scn01-syllabus-01 --source-scope wp3 \
  --query '"prompt engineering"' --k 1
```

Both source scope and query are mandatory. Missing permission fails before source
reading, MCP or model construction. Empty, truncated, out-of-scope or incomplete
retrieval does not fall back to ungrounded generation. Source diagnostics remain
visible; supplying corpus evidence does not repair the external scenario.

## Contracts, delegation and persistence

The registry under `agents/authoring/` is separate from the learner worker
registry. The Curator inherits category settings and skills and uses its own
configured profile. Its explicit authoring dispatcher allows only the registered
typed output contract. It receives full evidence supplied by application control,
no MCP client or direct search tool, and no implicit delegation capability.
The existing learner `WorkerOutput` contract and proposal restrictions remain.

`SyllabusDraft` is an application transport type. Each ordered unit has a unique
local key, exact source target/competency/practice ids, a learning purpose, planned
EXPLAIN/PRACTICE/ASSESS intents, and resource/version/segment citations with
supported claims. Multiple distinct units may address one target; all supplied
targets must be covered. Source and metamodel fingerprints must match exactly.
The output can declare gaps; deterministic source findings are retained even if
the model omits them.

The Curator output is checked before the Lead reviews it. The review must return
ACCEPT with both source alignment and substantive citation support confirmed.
REJECT, UNCERTAIN or either false flag produces no proposal. The Lead reviews;
it never replaces a failed Curator's syllabus. A semantic ACCEPT remains a model
judgment requiring human review, not proof of pedagogical quality.

The host maps accepted output to existing ALM entities: Topics, LearningOutcomes,
Strategies, a LearningDesign with a PHASE and ordered draft UNIT nodes, and
Resources preserving the typed syllabus artifact and full source/evidence
snapshot. A versioned provenance link associates the exact design with its
syllabus Resource; the artifact associates unit keys with exact ProcessNode refs.
This introduces no AIM-PRO or ALM metamodel class and changes neither source file.

Generation reserves a request before retrieval/model execution. Candidates, the
proposal and the terminal request result are saved atomically against the context
revision. An identical completed replay returns the recorded result without
another MCP/model call. Changing source, subject, query, scope or limit under the
same request identity conflicts. A pending interrupted request needs the existing
administrator `abandon` workflow and a new request id. There is no application
retry or paid-model fallback. Local character budgets apply separately to the
Curator and Lead profiles; full inputs are never truncated.

## Human review and the downstream handoff

Use the existing `decide` CLI to inspect the exact proposal and candidates and
record an explicit APPROVE, REJECT or REQUEST_REVISION. `apply` is a separate
operation. Neither generation nor application activates the design. UNIT nodes
have no executable activities, so readiness checks continue to block activation.
No resources are bound, and no learner evidence, evaluations, acquisition or
completion is created.

After approval and application, read the current design reference from `show`
and resolve the downstream handoff without a model or retrieval call:

```bash
.venv/bin/python -m learning \
  --db "$SCN01_SYLLABUS_DIR/state.sqlite" --policy "$SCN01_SYLLABUS_DIR/policy.json" \
  --subject syllabus-author --context scn01-syllabus \
  show-aimpro-syllabus '<current LearningDesign EntityRef JSON>'
```

The resolver requires authoring (`propose`) permission and reads one SQLite
snapshot. It verifies the current exact design, context identity, typed artifact,
source/citation checks, reviewed candidate payloads, current reviewer authority,
the proposal's latest APPLIED status, and the corresponding decision and
StateChange. Pending, rejected, approved-but-unapplied, foreign and superseded
outlines are rejected. Recorded provenance is not an independent authentication
of the original source or pedagogical equivalence.

For authoring beyond the original outline, initialize an explicit approved
project selection using [the production project commands](../architecture/authoring-projects.md).
`show-project-syllabus` preserves access to the exact original Curator approval
as assessment and instructional definitions evolve. Project initialization and
each revision still require separate human review/application.

This approved outline is the integration entry point for the dedicated Evaluator
work in #9 and Teacher/Trainer authoring from an approved syllabus in #10. Those
generators remain separate work; the learner-side demo does not implement them.
Future revisions of the outline or payload require their own reviewed proposal.

## Verification

```bash
.venv/bin/python -m aimpro.generate --check
.venv/bin/python -m unittest tests.test_aimpro_authoring tests.test_aimpro_syllabus tests.test_aimpro_runtime -v
```

The focused tests cover registry/profile/category enforcement, typed delegation,
exact source/version/segment checks, review rejection and uncertainty, explicit
approval/application, stale/foreign/revoked approval rejection, read-only
resolution, replay, rollback, abandonment, concurrent revisions and the CLI.
Tests use synthetic model outputs; a real-model run must be reported separately.
See [the real SCN01 Curator trial](scn01-curator-example.md) for the pending
two-unit proposal, exact WP3 version, replay check and manual review limitation.
