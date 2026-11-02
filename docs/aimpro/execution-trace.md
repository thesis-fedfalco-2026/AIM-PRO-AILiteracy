# AIM-PRO execution-state trace

Issue #7 is implemented as an **ALM sidecar** under the repository owner's
constraint that the externally owned jjodel/AIM-PRO metamodel and project must
remain unchanged. The original request to put runtime records inside AIM-PRO is
not claimed: the supplied definitions have no learner evidence, evaluation,
proposal, human-decision or state-change classes. `Activities.Activity.evidenceType`
is an expected-evidence descriptor, not a submitted response; design-time
assessments are not runtime evaluations.

The sidecar associates existing ALM records with exact source objects without
inventing AIM-PRO types or changing their meaning. It is an audit export, not a
jjodel project or an importable AIM-PRO instance graph.

## Export

For the existing isolated example, from the repository root:

```bash
.venv/bin/python -m learning \
  --db .cache/aimpro-examples/wp3/scn01-grounded-2/state.sqlite \
  --policy .cache/aimpro-examples/wp3/scn01-grounded-2/active-policy.json \
  --subject demo-author --context scn01-demo \
  export-aimpro-trace docs/resources/aimpro-megamodel-2026-11-02.json \
  > .cache/aimpro-examples/wp3/scn01-grounded-2/execution-trace.json
```

For a fresh run from the [colleague runbook](../demo/scn01-colleague-runbook.md),
use its `state.sqlite` and `policy.json` under `$SCN01_RUN_DIR` with the same subject
and context. No model, MCP request, decision or state update is made by exporting.
Only a participant whose current trusted and recorded roles both include
ADMINISTRATOR can export context-wide history. The file can contain learner data
and assessment content; keep it within the operator's authorized environment.

## Mapping and boundaries

| Local records | Link to unchanged source | Meaning retained locally |
| --- | --- | --- |
| Topic / LearningOutcome | Competency / iSQD.LearningTarget | Local operational definitions, with original source ids |
| ActivityDefinition / Strategy / ProcessNode | Source pedagogical practices / target / scenario | Generated design lineage, not a claim of identical classes |
| ActivityOccurrence / LearningEvidence | Exact activity, outcome and causal references | Observed attempt and submitted text, not acquisition |
| Evaluation | Fixed specification and submitted evidence | Mode, result, rubric judgments and review status |
| ChangeProposal | Versioned targets and candidate definitions | Pending/applied/rejected status; no implied approval |
| HumanDecision | Exact target proposal and reviewed payload keys | Recorded decision and responsible participant |
| StateChange | Exact cause and context revisions | Applied change, distinct from a proposed change |
| LearningState | Assessment basis and outcome | Only the recorded progress/verification, never inferred by export |

`format=aimpro-execution-trace`, `format_version=1` identifies the local format.
The export pins the source SHA-256, metamodel fingerprint, scenario root/model,
and source-object descriptors. Each record retains its full versioned ALM entity,
linked entity references and sorted source object ids. `SOURCE_LINKED` means
traceable provenance/reference association; `ALM_ONLY` means no such source link
was established. All runtime types remain ALM representations even when linked.

Source links start only from provenance matching both the supplied source hash
and metamodel fingerprint, with ids resolved inside the selected scenario graph.
Links propagate through domain, evidence, target and causal references to a fixed
point. Context, participant, policy and learner fields do not spread scenario-wide
lineage to otherwise unrelated events. Unknown ids, mismatched source snapshots
and unavailable references produce explicit diagnostics rather than guessed links.
Recorded provenance is not independently authenticated pedagogical equivalence.

The export includes every context-owned active-history revision, including old
proposal statuses and context revisions; proposal candidates remain separately
labelled with their proposal namespace. Historical domain revisions are resolved
through references, without enumerating unrelated shared domain entities.
Approval links attached during application are preserved in the applied entity
while the original candidate payload stays separate. Exports use one SQLite read
transaction and are deterministic for unchanged input/state. They do not change
schema, source files, approvals or learner state.

## Acceptance and validation

The implementable scope of #7 under the immutable-source constraint is:

- Exact, versioned links from runtime evidence/evaluations and the
  proposal → decision → state-change lifecycle to unchanged source identities.
- Explicit representation gaps, without introducing external metamodel classes.
- Context isolation, administrative access control, historical and pending-state
  separation, reproducibility and a documented CLI.
- No inferred approval, competence acquisition or activity completion.

Seven dedicated tests cover pending/applied decision chains, synthetic evidence
and a pending evaluation, deterministic read-only export, source mismatch,
context isolation, learner rejection and the CLI without model construction.
The real existing demo exported successfully with zero diagnostics: one
LearningEvidence and one IN_PROGRESS ActivityOccurrence link to three source
objects, with no Evaluation or LearningState fabricated.

Automatic observed-completion workflows and formal assessment validity are
separate work. Closing the sidecar integration does not claim native runtime
modelling inside AIM-PRO, complete course progression or completion of #25.
