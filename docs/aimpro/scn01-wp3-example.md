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

## Explicit binding follow-up

The local follow-up prepared five explicit selections from the already cited
WP3 resource, one for each generated activity's resource requirement. It created
fresh proposal `proposal-fdc51b7737124c1297e7fa8b1b2b6f3c`, version `1`, containing
the teaching design and five proposed ResourceBindings. The original teaching
proposal was unchanged. `binding-selections.json` and `binding-proposal.json`
record the exact mappings and candidates beside the other local artifacts.

Current state after preparation: PREPARATION/DRAFT, zero active bindings and
zero human decisions. No approval/application or learner transition took place.
The follow-up code is separate from the two integration commits; it exercises
the new `propose-aimpro-bindings` path without another model or MCP call.

### Owner confirmation and application

On 2 November 2026 the repository owner explicitly confirmed the five bindings.
The host checked that the stored candidates and review payload hash exactly
matched the displayed `binding-proposal.json`, backed up the test database, then
recorded decision `decision-1d332f48ae79467abd83078dc90179f3` and applied the new
combined proposal through the normal service. StateChange:
`change-64b54bcc615645caaf366cb018ee3d4d`.

The example now has five active bindings with valid human approval. The context
remains PREPARATION/DRAFT, with zero evidence, activity occurrences or learning
states. The local receipt is `binding-application.json`; the pre-operation backup
is `state.before-binding-approval.sqlite`. The earlier original teaching-only
proposal was not applied separately.

Activation checks still find missing process completion rules. No operational
AgentSpecialization is configured, and the current test policy does not grant
the learner WP3 access or enumerate the exact resource key for LEARNING. These
remain separate configuration work; approval of bindings does not supply them.

### Execution configuration proposal

The next local operation prepared proposal
`proposal-ea183d1b7da94111b730303187be3a60`, version `1`, without applying it. The
preview is `execution-policy-preview.json`; the full result is
`execution-setup.json` and the readable summary is `execution-review.md`.

The proposed scope `scn01-learning` grants demo-learner and the local author
read-only access to the one exact approved resource key for this context's five
activities. Its source-scope list is empty. The author's separate `wp3` source
scope is preserved, and no general corpus access or human decision authority is
granted to the learner. The two proposed operational workers resolve to
the existing Teacher/Trainer registry entries.

Two proposed process completion rules require every direct child to be
explicitly COMPLETED, with no acquisition or numerical grading. Five binding
versions are revised to the new learner scope; their old decisions are not
carried across the changed audience. The preview accordingly reports pending
resource approval (R08), not missing process rules (R06).

Current actual state remains PREPARATION/DRAFT with the five originally approved
bindings and current policy intact. No execution-configuration decision,
activation, attempt or learning state was recorded by this preparation. Applying
the new configuration would require its own human decision and a subsequent
switch to the exact proposed policy version. The local code and report updates
for this step remain uncommitted.

### Execution configuration approved and applied

The repository owner explicitly approved the displayed execution configuration
on 2 November 2026. The host verified the exact stored candidate payload/review
hash and the complete trusted-policy preview, backed up the test database, and
recorded decision `decision-c3b07b290a3047468acd6d97408e61e1` followed by StateChange
`change-b05926c9330549c6aab477300bc592da`.

The current policy is now available locally as `active-policy.json`, with
PolicySet version `6a20225f0a9f43e09b87b113f32060af`. The original `policy.json`
is preserved for audit and no longer matches the current context policy version.
The receipt is `execution-application.json`; the pre-operation backup is
`state.before-execution-setup.sqlite`.

Verified after application: five valid approved learner-scope bindings, two
eligible Teacher/Trainer workers, two bound completion handlers, zero readiness
findings and no general WP3 corpus permission for the learner. Current state is
still PREPARATION/DRAFT, with zero occurrences or learning states. No model call
was made by this configuration change.

A separate pending activation proposal is available in `activation-proposal.json`
and `activation-review.md`; it changes only context mode/status to LEARNING/ACTIVE
and the context revision/provenance. It is not yet approved or applied.

### Activation confirmed and applied

The owner subsequently confirmed that exact activation proposal on
2 November 2026. After verifying the candidate payload/hash and that its only
substantive changes were context mode/status, the host recorded HumanDecision
`decision-7d31c5306def4d74a8808aee3116beec` and StateChange
`change-eb19d492f3db4e4783fba77771bb8d30` through the normal local service.

The example context is now LEARNING/ACTIVE with five valid approved bindings
and zero readiness findings. Its existing model, policy, worker profiles and
completion configuration were preserved. There are still zero activity
occurrences, evidence or learning states: activation made no model call and did
not simulate learner activity or completion.

The local receipt is `activation-application.json`, and the backup is
`state.before-activation.sqlite`. Further commands use the approved
`active-policy.json`, not the historical initial policy file.

### Interaction-intent mismatch found before the learner trial

While preparing the first Teacher command, inspection found that the real model
had labelled all five generated activities ASSESS. The configured workers support
EXPLAIN and PRACTICE, and `authorize_plan` correctly rejects a mismatched activity
intent. The earlier readiness checks covered resources/process structure but
missed this role-coverage gap; they did not establish end-to-end worker readiness.

A fresh local proposal, `proposal-7deb53c9da6641b292f64ab1546664b5`, changes the
two demonstrations to EXPLAIN and the three learner exercises to PRACTICE. It
preserves materials, analytic rubrics/specifications, requirements, approved
bindings, policy and learner state while versioning/rewiring the local activity,
assessment and path references. The raw AIM-PRO export is unchanged. The proposal
is pending review; current active definitions are not silently rewritten.

The generation/review prompts now distinguish instructional intent from the
presence of analytic feedback criteria. Execution setup additionally rejects
activities whose intents are not covered by its proposed Teacher/Trainer roles.
Local artifacts: `interaction-alignment-review.md`,
`interaction-alignment-proposal.json` and `interaction-alignment-summary.json`.

### First Teacher interaction completed

The owner explicitly approved the interaction-intent correction and requested
the first Teacher example with fictional payment-reminder data. The host checked
the exact saved payload/hash, recorded decision
`decision-3954d75a90f14f58b145a0b0dfecd0ba` and applied StateChange
`change-b7b6134cb927419391a64fba869c93a7`. Active definitions now have two EXPLAIN
and three PRACTICE activities. Source bindings retain their valid approvals.

The real request `scn01-teacher-first-1` completed through the normal
LearningService/Orchestrator flow, using synthetic participant `demo-learner`:

- One authorized Teacher step: `lesson-explainer`, EXPLAIN, exact activity ref.
- Real MCP retrieval in LEARNING mode: one exact approved resource key, no
  source-scope keys, five retrieved segments and no truncation.
- Worker TaskResult: SUCCEEDED; worker semantic review: ACCEPT.
- Final response: ANSWER in Italian, one citation to the exact WP3 resource
  version; final semantic review: ACCEPT.
- End-to-end latency: 186.70 seconds. Four recorded Lead invocations cover the
  plan, worker review, synthesis and final review; the worker generation is an
  additional call. Provider retries/conversions are not counted as separate
  HTTP calls by this instrumentation.
- Replaying the same recorded request returned the identical response without
  constructing an orchestrator or making another model/MCP call.

The answer demonstrates a weak prompt, a deliberately worse version, and an
improved prompt with explicit role, fictional customer/invoice details, tone,
constraints and maximum length, followed by the prompting choices and citation.
Manual review still found an unsupported assertion of a one-hour workshop: the
source specifies one evening, not that duration. The response also exposes
unnecessary internal metadata in its learner-facing text. Both semantic reviews
accepted it, so ACCEPT is not proof that all content and presentation are correct.

Current context remains LEARNING/ACTIVE with zero activity occurrences, learner
evidence or learning states. Asking for an explanation records an interaction,
not a submitted performance or acquired competency. Raw request, response,
answer, retrievals, structured Lead outputs, task records, summary and replay are
local under `teacher-trial/`. A demo-only timeout of 180 seconds per model call
and one-step limit were used; normal configuration files were unchanged.

### Trainer feedback and reproducible colleague demo

The operator submitted an explicitly labelled synthetic payment-reminder prompt
with two explained choices. Submission created one LearningEvidence and one
IN_PROGRESS ActivityOccurrence; it did not represent a real learner performance.

The first Trainer request, `scn01-trainer-first-1`, failed after 102.43 seconds:
it returned proposals forbidden for a Trainer and deterministic rule R16 rejected
them. Semantic review accepted framing-only text despite missing requested
feedback. The Trainer instructions now require substantive GUIDED_PRACTICE
feedback with empty proposals; semantic review explicitly checks completeness.

The second real request, `scn01-trainer-first-2`, returned ANSWER after 116.29
seconds. It used guided-practice-coach, the exact submitted evidence reference,
and real MCP retrieval restricted to the approved resource version. Worker and
final reviews accepted the response. Feedback identified fictional data and
specific invoice context as strengths, suggested separating instructions/context
and specifying output structure or an example, and asked a concrete revision
question. Raw artifacts remain under `trainer-trial-2/` in the local example run.
The context still has one IN_PROGRESS occurrence, zero evaluations and zero
LearningStates. Request success does not establish learner completion.

For another operator, use the [step-by-step colleague runbook](../demo/scn01-colleague-runbook.md)
and `python -m aimpro.demo`. The checked-in fixture contains domain configuration
and synthetic material, not historical approvals, learners or completed attempts.
A fresh isolated run requires explicit import and activation decisions, checks
the real MCP source, and resolves current activity/evidence references itself.
Fresh initialization, review/application, activation, real MCP checking and
synthetic submission were rehearsed successfully. The helper's live Teacher and
Trainer commands use the established orchestrator path; the observed model
outputs above came from the original run, not a new helper model rehearsal.

Validation: 356 tests passed, including PostgreSQL and MCP integration tests.
The original AIM-PRO source export remains unchanged.
