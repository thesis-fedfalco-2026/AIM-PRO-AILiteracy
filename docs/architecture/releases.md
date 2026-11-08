# Production releases, delivery imports and activation

`learning/releases.py` turns the release and delivery design of the
[authoring lifecycle](authoring-lifecycle.md#release-delivery-and-history) into
four production ALM commands (R1, issue #71). It works over the existing Resource,
DomainModel, ResourceBinding, PolicySet and proposal/decision/application
records. It changes no metamodel, schema, AIM-PRO type or source export.

The commands only propose or inspect. Every decision and every application uses
the existing `decide` and `apply`. No command calls a model, a retrieval service
or the network.

| Command | Context | Result |
| --- | --- | --- |
| `propose-release` | authoring, PREPARATION/DRAFT | pending proposal: release Resource, release catalogue, updated authoring context |
| `show-release` | authoring | receipts, exact frozen closure and findings; no writes |
| `propose-delivery-import` | a separate, empty destination in PREPARATION/DRAFT | pending proposal: frozen definitions, runtime model, bindings, policy revision; plus a trusted-policy preview |
| `propose-activation` | the destination after an applied import | pending proposal that changes only mode/status to LEARNING/ACTIVE |

## Owner decisions applied

The owner decided D1–D5 on 8 November 2026 (#71).

- **D2.** The release manifest stays `authoring-release` format 1.
  `show-release` lists the exact domain closure.
- **D3.** Destination permissions use the policy-preview pattern. The import
  proposes a new trusted policy and never replaces the current one. The operator
  installs the exact approved file before activation.
- **D4 = option a.** An import keeps the ASSESS activities of the frozen design.
  `propose-activation` is refused with the finding `RELEASE_RUNTIME_ROLE` while
  any ASSESS activity has no configured runtime role. R1 configures none, so the
  refusal holds until a later explicit decision, for example with the
  assessor-facing evaluation adapter (G7).

## Identities

| Record | Identity | Version |
| --- | --- | --- |
| Release Resource | `authoring-release:` + SHA-256 of (authoring context, project id) | new per release |
| Release catalogue | release identity + `:catalogue`; it lists every release of the project | same as the release |
| Delivery runtime model | `authoring-delivery:` + SHA-256 of (destination, release id, release version) | new |
| Runtime workers and bindings | prefixed by the runtime model identity | new |

The release content is the canonical JSON of the `ReleaseManifest`. Its
`derivedFrom` is the exact project Resource. A later release of the same project
gets a new version and a new catalogue revision; earlier releases stay listed and
unchanged.

## Authority

Each command requires `read` and `propose`, plus ADMINISTRATOR or
CONTENT_RESPONSIBLE in both the trusted policy and the recorded participant.
An import requires that authority in both the authoring and the destination
context, loaded under the same installed policy. The import also proposes a
PolicySet revision, so its decision needs an ADMINISTRATOR reviewer. `--subject`
is a trusted local operator selection, not remote authentication.

## CLI workflow

Placeholders stand for complete EntityRef JSON values (`type`, `id`, `version`);
`latest` is always refused.

```bash
# 1. Propose a release of the current, fully approved project selection.
.venv/bin/python -m learning --db state.sqlite --policy policy.json --subject author \
  --context authoring propose-release --project '<project Resource ref>' \
  --domain '<project DomainModel ref>' --base-context '<authoring context ref>' \
  --request-id release-01
# 2. Review and apply it with the existing commands (decide asks for CONFIRM).
.venv/bin/python -m learning ... --context authoring decide '<proposal ref>' APPROVE --reason '...'
.venv/bin/python -m learning ... --context authoring apply '<proposal ref>' --operation-id release-01
# 3. Inspect the applied release.
.venv/bin/python -m learning ... --context authoring show-release '<release Resource ref>'
# 4. Propose the import into a separate delivery context.
.venv/bin/python -m learning ... --context delivery-01 propose-delivery-import import.json \
  --request-id import-01 --policy-preview delivery-01-policy.json
# 5. Review and apply the import in the destination, then install the preview file.
# 6. With the installed preview, propose activation; then decide and apply it.
.venv/bin/python -m learning --db state.sqlite --policy delivery-01-policy.json ... \
  --context delivery-01 propose-activation --base-context '<delivery context ref>' --request-id activate-01
```

The import bundle is a `DeliveryImport` record:

```json
{
  "release": {"type": "Resource", "id": "authoring-release:…", "version": "…"},
  "authoring_context": "authoring",
  "base_context": {"type": "ExecutionContext", "id": "delivery-01", "version": "…"},
  "scope_name": "delivery-01-learning",
  "bindings": [{
    "requirement": {"type": "ResourceRequirement", "id": "…", "version": "…"},
    "resource": {"type": "Resource", "id": "…", "version": "…"},
    "usage_scope": "delivery-01-learning"}],
  "completion_handlers": [{"rule": {"type": "RuleDefinition", "id": "…", "version": "…"},
                           "handler": "all_completed"}]
}
```

`--policy-preview` must name a new file in an existing directory. The CLI never
writes the current policy file. A refused activation exits with status 2 and
prints its findings as JSON on standard error.

## What each command checks

### `propose-release`

One `BEGIN IMMEDIATE` transaction holds authorization, the base check, request
reservation, `prepare_release` and the atomic proposal. The project must be the
current catalogue selection. `prepare_release` refuses:

- a missing required kind, a missing or stale dependency;
- an invalid project or artifact receipt;
- a domain outside this context's snapshot, a domain without the selected
  definitions, or one not reviewed with this project revision.

An identical request replays its recorded result, also after application. A
different command under the same request id is refused (`StateConflict`). The
command never approves, applies or activates anything.

### `show-release`

One read transaction, no writes. It reports:

- the receipts (proposal, decision, StateChange) of the release, the project and
  every artifact, checked against current reviewer authority;
- the sorted exact closure of the release domain;
- findings: `RELEASE_UNAPPROVED`, `RELEASE_PROJECT_RECEIPT`,
  `RELEASE_ARTIFACT_RECEIPT`, `RELEASE_DOMAIN_UNREVIEWED`, `RELEASE_PIN_MISMATCH`,
  `RELEASE_EXECUTION_STATE`, `RELEASE_CLOSURE` and stale-dependency findings.

A Lead ACCEPT is never a receipt: only an applied human decision is. Later
authoring revisions leave the output unchanged. A release that was never applied
is not stored and is reported as not applied.

### `propose-delivery-import`

It refuses a destination that already holds learner history (occurrences,
evidence, states or evaluations) or any configuration ("requires a reviewed
migration"). It then reads the release through `released_entities`, which
rechecks every receipt and that the manifest pins match the reviewed project.

The proposal holds:

- the frozen closure, unchanged (the store also refuses a different payload for
  an existing id and version);
- the release Resource and a runtime DomainModel that pins it;
- Teacher and Trainer worker specializations for the EXPLAIN and PRACTICE
  activities of the design, limited to the new scope;
- one ResourceBinding per selection, with a pending review key;
- a PolicySet revision that embeds the full policy preview;
- the destination context, pinned to the frozen domain and design and still
  PREPARATION/DRAFT.

Each binding selection must name a requirement of the frozen design, the exact
resource version that the released generated packages pin for it, and the new
scope. A binding to a resource that is not a generated material must be a WP3
catalogue resource: its `resource_key(id, version)` must appear in its
provenance. The policy preview adds the new scope (destination participants,
design activities, exact bound resource keys, no sources) and the explicit
completion handlers. A handler must bind a completion rule of the frozen design
that the current policy does not already bind.

The import explanation cites the receipts of the release, the project and every
artifact. Authoring approval grants no destination use. The bindings become
approved only through the destination's own decision on the import.

### `propose-activation`

The command first refuses with `RELEASE_POLICY_NOT_INSTALLED` when the installed
policy version differs from the context policy. It then collects every blocking
finding and refuses (`ActivationRefused`) unless none remains:

| Finding | Condition |
| --- | --- |
| `RELEASE_IMPORT_UNAPPLIED` | no valid applied import receipt in the destination |
| `RELEASE_PIN_MISMATCH` | the context no longer pins the frozen domain and design |
| `RELEASE_LEARNER_HISTORY` | the destination holds learner history |
| `RELEASE_POLICY_NOT_INSTALLED` | the installed policy differs from the reviewed preview |
| readiness `R05`–`R08` | `advance` readiness fails, e.g. a missing or unapproved binding or a missing completion rule |
| `RELEASE_COMPLETION_HANDLER` | a completion rule has no handler in the installed policy |
| `RELEASE_RUNTIME_ROLE` | an activity intent has no runtime role; for ASSESS this is the D4 refusal |

A refused request reserves nothing. A successful one proposes only
LEARNING/ACTIVE; the human decision and the application stay separate.

## Reserved rules

Generic `propose` refuses, and `apply` refuses again under its final write lock:

- creating or changing a release Resource, recognized by identity or by
  `authoring-release` content, and changing a release catalogue entry;
- adding another context's project domain to a context's models, which would
  import release definitions outside `propose-delivery-import`;
- changing models, design, policy, bindings, mode or status of an imported
  delivery, including a generic activation.

At application, a reserved change must come from a proposal recorded by the
matching command. The release, import or activation conditions are then
rechecked: release receipts and the current project selection; import receipts,
the unchanged frozen definitions and the empty learner history; or the full set of
activation findings. The context compare-and-swap still refuses any changed base.

## Completion rules and SCN01

The dedicated generators never infer completion rules. A frozen release can only
carry them through an explicit, reviewed project revision of the composite
design. The acceptance tests author such rules this way before releasing.

A read-only check on a copy of the applied SCN01 database (8 November) found the
approved design with 5 process nodes, none with a completion rule, and 4 ASSESS
activities. An SCN01 delivery would therefore stay refused for two reasons: the
missing completion rules and D4. Nothing in R1 changes that design.

## Verification

```bash
.venv/bin/python -m unittest tests.test_releases tests.test_authoring_cycle tests.test_authoring_projects -v
LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false .venv/bin/python -m unittest discover -q
.venv/bin/python -m aimpro.generate --check
```

`tests/test_releases.py` uses temporary SQLite. It blocks sockets, DNS, `crewai.LLM`
and `LLMFactory` calls, and makes agent construction fail. Its synthetic project
comes from the production generators with synthetic model responses. The
acceptance cycle in `tests/test_authoring_cycle.py` now runs release, import and
activation through these commands. Its runtime scenarios simulate one boundary:
they patch an EVALUATOR runtime worker into the import, standing in for the future
G7 assessor role that D4 requires before activation.

## Not covered

R1 does no AIM-PRO or jjodel export, learner enrolment, runtime assessor adapter,
migration of an active delivery or web review surface. No real SCN01 release,
import, binding or activation is part of it; each needs its own owner decision
(D7).
