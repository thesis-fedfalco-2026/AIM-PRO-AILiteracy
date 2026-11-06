# Teacher flow correction — offline evidence

This follow-up fixes the production authoring contract after the third recorded
failure. It does not revise historical outputs or change an owner's decision.
No fourth model call, Teacher approval/application, learning activation or release
occurred. The original accepted Evaluator limitations remain in force.

[Verification](verification.json) was produced with:

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m tests.verify_scn01_teacher_offline \
  --output /tmp/teacher-offline.json
```

The verifier backs up the actual authoring DB to a temporary file, blocks sockets
and DNS, replays all eight historical results without constructing clients, and
checks the unchanged legacy input digest. Production services validate exact
refs, current permissions, receipts and freshness. The original approval reason
is passed and retained verbatim; only its hash/references are published here.

Synthetic typed responses then exercise the production structured dispatcher,
host rendering, separate synthetic review, pending proposal and exact replay in
that disposable copy. The synthetic proposal is discarded without approval or
application; its random package/proposal ids are not real Teacher inputs. The
archive inventory before and after matches for all 880 files. No raw source,
private DB, input prompt or provider traffic is added to this evidence.

Local full regression: 550 tests passed, four existing WP3 tests skipped because
the source was unavailable. Seven structured-Teacher tests forbid network access.
Both generated-contract checks and `git diff --check` pass. These results establish
implementation behavior, not pedagogical adequacy or acceptance of any content.

See the [contract and limitations](../../../../architecture/authoring-generators.md#offline-correction-after-the-third-teacher-failure-6-november-2026)
and [Chat 05 handoff](../../../../plans/handoffs/chat-05.md). No new live packet
is prepared or authorized by this correction. Chat 06 must not start while an
approved/applied Teacher is missing.
