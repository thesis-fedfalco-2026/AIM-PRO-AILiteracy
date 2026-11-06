# Fifth authorized Teacher attempt — provider schema rejection

The owner explicitly authorized request `scn01-teacher-05-compact-schema`, manifest
`c24a0a1f61d10e3353bd62791e4ea09fa0467002afd133d813dd9bb3f5e94888`, Anthropic direct
`claude-sonnet-4-6`, one Teacher plus conditional separate Lead, no retry and USD 5
([authorization](model-transmission-authorization.json); [preparation](../preparation-05/README.md)).

**Actual terminal result: FAILURE.** One HTTP request received status 400 after
1.7 seconds: the compiled grammar was too large
([provider error](provider-error.json)). The submitted schema was exactly the
reviewed [compact schema](../offline-schema-fix/native-schema.json); the driver
enforced this before sending. No Teacher output was returned. No Lead was invoked,
and no proposal, candidate, human decision or application exists. No retry
occurred. No usage was returned, so cost is unknown, not zero.

A first launch attempt exited 127 in the shell before Python started, because
the command was expanded without `env`. It left no run marker and sent no HTTP
request. The one-shot run was then started with the same command prefixed by `env`.

[Post-run verification](post-run-verification.json): exact refs, the accepted
review reason, permissions, receipts and freshness are unchanged. There are 164
entities, thirteen requests, five HumanDecisions and three StateChanges. All
**ten** terminal generation results replay identically with clients/network
forbidden and unchanged DB bytes. The fourth archive and packet files are
unchanged, and no Teacher is selected. The subsequent
[compilation probes](../schema-probes-01/README.md) investigate the cause.
