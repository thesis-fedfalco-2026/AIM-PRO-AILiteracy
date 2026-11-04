# Explicit source-action coverage for Curator planning

The [real rejected trial](scn01-selected-curator-example.md) matched target ids
and supported its citations, but omitted participant prompt construction and
explanation of choices. The local correction makes these source obligations
explicit and checks their structural coverage before a separate Lead call.
The subsequently authorized [corrected real run](scn01-covered-curator-example.md)
produced four units covering all five actions. The separate Lead returned ACCEPT;
one proposal remains pending human decision/application.

## Input and output

`SourcePlan` optionally carries `coverage_requirements`. Each record includes
`key`, `source_target_id`, `source_object_id`, `source_field`, exact `source_quote`,
`actor` (FACILITATOR/PEER/LEARNER), `expected_intent` and `required_action`.
These are host-controlled planning records, not ALM entities, runtime roles,
permissions or learner observations. Code does not infer intent by searching
arbitrary source words. The quote must occur in the specified source field, and
that object must be the exact target or one of its actual practices. Invalid
anchors and duplicate keys fail before retrieval/reservation/model construction.

Example excerpt from the full prepared plan:

```json
{
  "key": "learner-construction",
  "source_target_id": "<exact scenario target id>",
  "source_object_id": "<that target's exact practice id>",
  "source_field": "inPractice",
  "source_quote": "write a prompt for their own business",
  "actor": "LEARNER",
  "expected_intent": "PRACTICE",
  "required_action": "Participants construct their own first fictional business prompt."
}
```

An exact quote establishes origin, not correctness of the actor/intent
interpretation. The prepared packet exposes these interpretations for review.
They are reserved, included in model input/source trace, and later in the exact
reviewed source snapshot. Source hash/scope/subject/context checks remain.

Each SyllabusUnit can now include `coverage` entries containing
`requirement_key` and a concrete `planned_action`. Every explicit requirement
must be covered by a unit with the correct target/practice and expected intent.
Missing/unknown/duplicate keys fail before Lead review. EXPLAIN-only cannot
cover required PRACTICE by adding labels. One combined EXPLAIN/PRACTICE unit
or several ordered units are both valid; no two-unit fixture or ASSESS is forced.

Labels cannot establish substantive coverage. The Lead still compares the
source quote/actor and actual planned action and can reject a structurally valid
but misleading description. Human review/application remain separate. No planned
action establishes acquisition, verification, completion or learner results.

Prompts now distinguish demonstration from the learner's own work, preserve
source-required peer examples/practice, and avoid requiring ASSESS/rubrics/
thresholds absent from source/brief. They distinguish EString vocabulary
diagnostics (`UNTYPED_VOCABULARY_VALUE`) from actual enum/contract errors. Neither
external metamodel nor source values are normalized to satisfy model review.

## Compatibility and corrected packet

The extension is optional. Empty fields are omitted from serialization,
preserving historical source-packet/trace digests and legacy draft payloads.
Old approvals are not rewritten or given new obligations. Resolver validation
enforces coverage only when its reviewed source snapshot contains requirements.
No database or external metamodel migration is needed.

Fresh ignored directory:
`.cache/aimpro-examples/curator/scn01-selected-sources-2/`.
It uses the same seven content-pinned excerpts and five requirements quoting
SCN01's original ModellingAIPractices field:

1. Adviser modelling with thinking aloud and weak/improved/worse variants — EXPLAIN.
2. Peer-owner prompts and failures — EXPLAIN.
3. Learner identification of prompt moves and paired transcript annotation — PRACTICE.
4. Learner construction of an own fictional business prompt — PRACTICE.
5. Learner explanation of two choices — PRACTICE.

`RUN_REVIEW.md`, `model-input.json`, `curator-prompt.txt`, schemas and the hashed
manifest preserve the preauthorization Curator + Lead transmission packet.
The owner subsequently authorized this run; its actual outputs and ACCEPT result
are recorded in the linked report. Human approval/application and dedicated
Evaluator generation remain separate, unauthorized next steps. Previous trial
outputs/state remain unchanged.

## Verification

`tests/test_syllabus_coverage.py` covers the observed omission, misleading
labels, valid combined/separate units, bad anchors/keys, legacy serialization
and continued semantic rejection. Source-service tests cover pre-retrieval
rejection and reservation/persistence/review/application/resolution of exact
coverage-bearing inputs. They use synthetic responses and temporary state with
socket/DNS blocking. Full regression also checks historical delivery/evidence
and real read-only PostgreSQL/MCP.

Local verification on 3 November 2026: **464 full-regression tests pass with no
skips and PostgreSQL/MCP enabled**; 56 focused coverage/source/Curator/lifecycle
tests pass. Generated-contract and whitespace checks pass. Actual model-free
preparation and replay of the new packet succeed. Historical preparation/trace
hashes and the rejected model result's replay remain exact with retrieval/models
forbidden. The correction's tests are separate from the subsequently authorized
real model run. No human decision, commit, push or new remote CI run is claimed.
