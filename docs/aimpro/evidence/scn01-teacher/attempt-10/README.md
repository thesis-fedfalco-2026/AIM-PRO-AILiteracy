# Tenth authorized SCN01 attempt — Lead ACCEPT, owner APPROVE, applied

The owner explicitly authorized request `scn01-teacher-10-regeneration`:

- manifest `742f46699d554c10e4e551946416307750318c74fe761f697e4fe5fce51fe6d6`;
- Anthropic direct `claude-sonnet-4-6`;
- one Teacher call plus a conditional separate Lead;
- no retry, USD 5 budget.

See the [authorization](model-transmission-authorization.json) and the
[preparation](../preparation-10/README.md).

**Actual terminal result: PROPOSAL.**

- **Requests:** two HTTP requests.
- **Teacher:** `end_turn`, 5,242 output tokens, no `output_config`. The
  whole-response JSON passed the Pydantic contract and all host checks, including
  the T01 prompt-body check ([original output](teacher-original-output.json);
  response text 21,389 characters, SHA-256 `1ea4dcbc…73c1`).
- **Lead:** `end_turn`, 889 output tokens. Verdict ACCEPT, with all four flags
  true ([verdict](lead-verdict.json)).
- **Total time:** 141 s.
- **Cost:** estimated USD 0.899782 from complete usage. This is not an invoice
  ([summary](run-summary.json)).
- **Proposal:** `proposal-db534143fb8d4c40a73449af1adb2f7c@1`, AWAITING_DECISION,
  20 candidates, review payload key `5e8ec798…f328`.

Post-run verification found exact refs, permissions, receipts and freshness
unchanged. Fifteen terminal results replay exactly, with clients and network
forbidden ([post-run verification](post-run-verification.json)).

## Local review (presented to the owner before the decision)

The four rendered materials appear verbatim in the proposal candidates. Each
requirement was checked against the original components and the retained
excerpts:

- **Requirements 1–3:** the four assets have the exact keys and kinds, and there
  is one observational EXPLAIN item.
- **Requirements 4–5:** the weak prompt is "You are an accounts assistant for
  Stonebrook Tools. Send a message to Harbor Workshop about their account.". It
  differs from every assessment prompt body, and the facts are exact and declared
  fictional.
- **Requirement 6:** worse equals improved minus the final tone sentence, which
  is the only tone guidance.
- **Requirement 7:** the peer speaks in first person, and fictional status is
  stated in `notice`.
- **Requirements 8–9:** the label set is correct, and effects are qualified in
  all speech, including the closing summary.
- **Requirement 10:** the citations name excerpts 3, 4, 6 and 7, and the key
  attributions were found in the retained text.
- **Requirements 11–18:** the full adviser and peer sequence is present, the
  draft states that it is openly commented teaching, there is no notebook and no
  real data, and `new_gaps` is empty.

The owner accepted three limitations, which are not fixed:

1. The improved and worse prompts follow the sentence frame of the approved
   Greenleaf assessment prompt, with new facts (about 63% word overlap, including
   the verbatim run "Ask the customer to arrange payment within five business days
   and include the invoice … and amount in the email body"). The attempt-06 prompt
   had the same overlap, and the earlier review did not flag it.
2. The peer scene presents the authored email in-fiction as the tool's reply. The
   notice does not state explicitly that the email is not real AI output.
3. Minor points:
   - the improved prompt adds a business descriptor and a deadline that are not
     declared facts;
   - one transcript line is phrased more categorically than the rest.

## Human decision and application

The owner instructed, in Italian: "Approvo la proposal
proposal-db534143fb8d4c40a73449af1adb2f7c della request
scn01-teacher-10-regeneration e ne autorizzo l'applicazione, con i limiti accettati
1–3." The Lead ACCEPT did not grant this approval. Production services recorded
the following ([decision](owner-decision.json)):

- HumanDecision `decision-ddf299556a93486eb7595a52ed8033b6@1`, APPROVE, with the
  three limitations in its reason.
- StateChange `change-8807603557ac4a029312979287315973@1`. The application is
  idempotent, and the proposal is APPLIED.
- Context `scn01-selected-syllabus-2@2d6f0be42c8b4f81b92873e3c33bf017`.
- Project
  `authoring-project:072a25db…dbac@2d6f0be42c8b4f81b92873e3c33bf017`.
- Selected TEACHER_CONTENT
  `authoring-output:0550349a953f4fee5c161eb8fcbf1023759589d79c752fdeb99191c4f0713b83@eb707876a6a047e78e705078dca5855b`.

The project receipt is valid and fresh, with no stale dependencies. The database
now holds six HumanDecisions and four StateChanges. No learner state, binding,
evaluation or release exists ([verification](post-decision-verification.json)).
After application, all fifteen terminal results still replay exactly without
models ([replay](post-application-replay.json)).
