# Fourth authorized Teacher attempt — provider schema rejection

The owner explicitly authorized request `scn01-teacher-04-structured`, exact manifest
`e62c78d31f79208cfc075ee6dbbbca67314f8308a907228a41bb39e0bc551ad6`,
Anthropic direct `claude-sonnet-4-6`, one Teacher plus conditional separate Lead,
no retry and USD 5 operational budget. This supersedes the preparation-time
no-authorization status, without altering that historical record.

**Actual terminal result: FAILURE.** One HTTP request received status 400 in
0.909 seconds total service time (Teacher wrapper 0.727 seconds). Anthropic returned
`invalid_request_error` because the compiled grammar was too large. It produced
no Teacher output. There was no Lead invocation/verdict, proposal, candidate,
human content decision or application. Content explanations, examples, transcript,
citations and unit/assessment compatibility cannot be inspected for this attempt
because no draft exists. This is a provider schema rejection, not a content review.

The [submitted native JSON schema](submitted-native-schema.json) matches the
reviewed transformed schema exactly. The HTTP request contained no tools or tool
choice. The generic provider error's reference to tool schemas does not establish
that this run used tools. The schema is 9,265 bytes under default JSON serialization
and has 13 definitions; those measurements do not identify the provider's internal
grammar limit or prove which schema construct caused the rejection. No schema,
prompt or driver was edited and no fallback/retry was attempted.

[Original result](response.json), [unaltered run summary](run-summary.json),
[parsed original provider error](provider-error.json),
[exact authorization](model-transmission-authorization.json),
[provenance](provenance.json), [cost interpretation](cost-note.json) and
[production verification and all nine historical replays](post-run-verification.json).
Original response bytes, full input/prompts, request and SQLite state remain private
in `.cache/aimpro-examples/teacher/scn01-teacher-4-structured/`.

No usage was returned/finalized. Estimated total cost is **unknown**, not zero;
the driver's zero known-cost subtotal is not a billing receipt. Provider billing
was not inspected. Historical estimates for the first three attempts are unchanged.

Production inspection verifies unchanged exact approved project/syllabus/assessment,
original source lineage, accepted review reason, current permissions, receipts and
freshness. All original archive files and prior DB rows remain retained; the only
new DB row is the terminal failed request. There are 164 entities, twelve requests,
five HumanDecisions and three StateChanges. All nine historical terminal requests
replay identically with clients/network forbidden and unchanged DB bytes. No Teacher
is selected, and no learning activation, binding or release was created.

The twelve synthetic packet tests and local schema transformation succeeded before
the run. They do not exercise Anthropic's remote grammar compiler and did not
predict this rejection. Any remedy must first simplify/verify the schema offline,
preserve these original artifacts, and prepare a separate exact transmission packet.
No fifth model call is authorized. There is no proposal on which to ask an owner
content decision. #10 stays open; Chat 06 must not start.
