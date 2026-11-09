# Chat 15 handoff — S07 studio review inbox (milestone M1)

Date: 9 November 2026. Base: `main` at `3b16f21` (PR #85, S06, merged). Step:
**S07** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 2),
**milestone M1: first usable app**. Issue:
[#86](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/86).

- Branch `feat/s07-studio-review-inbox`, commits: `8d3e4f0` (Chat 14 follow-up:
  CLI `decide` passes its previewed review key), `5fe46c9` (S07), and the commit
  that adds this file.
- No model call, no live run, synthetic data only. Services used: the local
  Keycloak of `compose.identity.yml` (throwaway secrets, stopped afterwards),
  the API on `127.0.0.1:58001` and the studio preview on `127.0.0.1:58000`,
  both started and stopped by Playwright. No API route, OpenAPI snapshot, core
  module, store schema, ALM metamodel, realm file, identity map or
  AIM-PRO/jjodel export changed.

## Objective

A reviewer completes a review in the browser.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 85` | `MERGED`, merge commit `3b16f21` |
| `git log --oneline -3 origin/main` | `3b16f21` (merge of #85), `519a690`, `a949186` |
| `gh pr list --state open` | none (at the start) |
| `unittest discover -q`, telemetry off, clean tree at `3b16f21` | 828 tests, OK, 140 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| Tools | Python 3.12.7, Node 22.22.2, Docker 29.8.2 |

**Differences from the Chat 14 handoff.**

1. PR #85 was merged at `519a690`, before the follow-up commit the handoff
   announces (owner answers: CLI `decide` passes its previewed key). The
   follow-up was only in the working tree. Its tests passed here
   (`tests.services.test_authoring_review_api tests.test_learning_review
   tests.test_learning_decisions`: 60 tests, OK, 30 skipped) and the full suite
   gave 832 tests, OK, 142 skipped.
2. **Two sessions shared the working tree.** The Chat 14 session
   (`py-prototype-73`) was still running. At 11:49 it committed the follow-up
   as `8d3e4f0` while `HEAD` was already this branch (created at 11:42 from
   `origin/main`), so the commit landed here. Its content is the follow-up
   verified above. After a message from this session it stopped all work in
   the tree. Before that message it had also pushed `8d3e4f0` to
   `feat/s06-cli-review-key` and opened
   [PR #87](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/87).
   Either route works: same commit, same parent `3b16f21`. If #87 is merged
   first, this branch already contains it; otherwise #87 can be closed.
3. At 12:02 someone else changed `README.md` (3 lines) and created
   `docs/architecture/system-overview.md`. They are not part of this PR and were
   left untouched, as were the pre-existing untracked
   `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md` and
   `examples/lpo-ai/`.

S07 has no open decision in the roadmap. Its dependency S06 is merged.

## Changes

Front-end (`apps/studio`), using only the S05 and S06 endpoints:

| File | Content |
| --- | --- |
| `src/features/review/reviewApi.ts` | `createReviewApi`: `inbox` (context summary and pending proposals together), `decide` (target, decision, reason, `review_payload_key`, `X-CSRF-Token`), `apply` (proposal, `operation_id`); `ReviewError` maps 401/403/404/409/422/other and "no answer" to a reason |
| `src/features/review/model.ts` | pure functions: `parseExplanation` (sentence + optional JSON report of `proposedChange`), `diffValues` (leaf diff with paths), `compareCandidates` (each candidate against the applied record with the same type and id), `latestProposals` |
| `src/features/review/ReviewServices.tsx` | the review API and `OperationIds` (one random UUID per approved revision, kept in memory) through React context; `useCsrfToken` |
| `src/features/review/useInbox.ts` | reads and reloads the inbox; nothing old is shown while it reloads; 401 returns to sign-in |
| `ReviewInboxPage.tsx`, `ProposalPage.tsx`, `Diagnostics.tsx`, `Changes.tsx`, `DecisionForm.tsx`, `ApplyStep.tsx`, `parts.tsx`, `paths.ts`, `routes.tsx` | the pages: inbox (awaiting a decision; approved, not applied), proposal (facts, apply step when approved, diagnostics, changes, exact payload, decision form) |
| `src/features/home/HomePage.tsx` | "Open a review inbox": a context id field (the API lists no contexts) |
| `src/App.tsx`, `src/main.tsx`, `src/routes.tsx` | `StudioApp` takes `review` (and `operations` for tests); the review routes |
| `src/i18n/en.json` | every new string; keys in camelCase (i18next reads `_SUFFIX` as a context or plural) |

`packages/ui/src/styles.css`: form, table, disclosure, card, badge and code
styles from the existing tokens (no new colour). The routes and behaviour are
described in `docs/architecture/role-applications.md`, new section "Studio
review inbox (S07)", and the manual studio check has a review step.

Browser tests (`apps/e2e/`, not a workspace): `playwright.config.ts`,
`stack/api.mjs` (new seed in `e2e/.state/`, API on 58001 against the local
realm), `stack/paths.mjs`, `stack/identity-check.ts` (fails early when Keycloak
or the dev password is missing), `sign-in.setup.ts` (one real Keycloak sign-in
as `dev-admin`), `support.ts` (seed restored before each test; the CLI on the
same database; `expectAccessible` with axe WCAG 2.1 A/AA rules),
`review.spec.ts`, `accessibility.spec.ts`. `npm run test:browser` runs them.

Dependencies (exact, `apps/package.json`): `@playwright/test` 1.64.1 (D12),
`@axe-core/playwright` 4.14.0, and `playwright-core` 1.64.1, pinned so that axe
and Playwright share one `playwright-core` (without it npm installed 1.65.0 for
axe and the `Page` types did not match). All were released at least 25 days ago.

CI: new job `browser` in `.github/workflows/aimpro-contracts.yml`: Python
requirements, `npm ci --ignore-scripts`, `npx playwright install --with-deps
chromium`, throwaway masked secrets, `docker compose -f compose.identity.yml up
-d --wait`, `npm run test:browser`, report uploaded on failure, compose down.

## Verification

Contract tests first: `studio/test/review-model.test.ts` and
`studio/test/review.test.tsx` were written against the planned module and page
API. The first run after the implementation had one failure, an error in the
test (`findByRole` awaited inside `act`), corrected without changing the code.

Local, on the tree of `5fe46c9`:

| Check | Result |
| --- | --- |
| `npm run check:client`, `npm run typecheck`, `npm test`, `npm run build` (in `apps/`) | OK, OK, 82 tests OK (62 before), OK |
| `npm run test:browser` (Keycloak running) | 5 passed (sign-in setup + 4 tests), 10.4 s |
| `unittest discover -q`, telemetry off | 832 tests, OK, 142 skipped (S07 changes no Python) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0, exit 0, exit 0 |

**The browser tests can fail.** Two temporary mutations, reverted afterwards:

- The decision path no longer reloads after a 409: the conflict test failed
  (`expect(locator).toHaveText` on the status). Removing the label of the
  context field made the review and accessibility tests fail at the locator.
- `--alm-color-text-muted` set to `#b0b4ba`: the accessibility test failed with
  the axe rule `color-contrast`.

Screenshots of the home, inbox, proposal, changes, apply step and a 390 px wide
view were taken with a throwaway spec (deleted) and looked at. They led to two
changes: short lists of plain values on one line, and no "does not await a
decision" sentence above the apply step.

**Signed-in writes through the real Keycloak are now verified** (Chat 14 left
them "not verified"): every browser test decides or applies with the BFF
session obtained through Keycloak and the CSRF token.

CI on `5fe46c9`: reported in the PR (the handoff commit triggers another run).

## Acceptance items of #86

| Item | Status | Evidence |
| --- | --- | --- |
| Browser test: review and apply an Evaluator proposal on the seed database | Done | `review.spec.ts` "a reviewer reviews and applies the Evaluator proposal of the seed": inbox → proposal; diagnostics and changes shown; approve, then apply; the CLI `show` lists one `APPROVE` decision with the proposal's `reviewPayloadKey` and one `StateChange` whose `newVersion` is the context version |
| Browser test: a payload changed after loading is refused and reloaded | Done | "a proposal decided by another reviewer after loading is refused and reloaded": the CLI rejects while the page is open; the approval gets 409; the page shows the conflict and "Rejected"; only the CLI decision exists. "Changed" means a new revision (the Chat 14 reading, still to be confirmed) |
| Accessibility check (axe) passes on the inbox views | Done | `accessibility.spec.ts`: home (with its validation error), inbox with and without pending proposals, proposal with every disclosure open, its validation errors, the apply step, a refused application, an unavailable context |
| Owner test script for teacher validation | Done | below |

Also tested: "an application whose answer is lost is retried with the same
operation id" (the API applies, the browser gets no answer, the retry sends the
same id and gets the replay; one `StateChange`).

## Owner test script (teacher validation)

About 15 minutes. Synthetic data only; nothing leaves the computer.

Setup, once (repository root):

```sh
export ALM_KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -hex 16)
export ALM_KEYCLOAK_DEV_PASSWORD=$(openssl rand -hex 16)
export ALM_OIDC_CLIENT_SECRET=$(openssl rand -hex 24)
echo "dev-admin password: $ALM_KEYCLOAK_DEV_PASSWORD"
docker compose -f compose.identity.yml up -d --wait
export ALM_OIDC_ISSUER=http://127.0.0.1:58080/realms/alm-dev
export ALM_OIDC_CLIENT_ID=alm-authoring-api
export ALM_OIDC_REDIRECT_URI=http://127.0.0.1:58000/auth/callback
export ALM_OIDC_POST_LOGOUT_REDIRECT_URI=http://127.0.0.1:58000/
export ALM_IDENTITY_MAP=infra/keycloak/identity-map.dev.json
export ALM_API_COOKIE_SECURE=false
export LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false
SEED=$(mktemp -d)/seed && .venv/bin/python -m tests.seed --output "$SEED"
export ALM_STORE=$SEED/alm.sqlite ALM_POLICY_DIR=$SEED/policies
.venv/bin/python -m services.authoring_api --port 58001
```

In a second terminal: `cd apps && npm ci --ignore-scripts && npm run dev --workspace @alm/studio`.

| # | Do | Expect |
| --- | --- | --- |
| 1 | Open `http://127.0.0.1:58000/studio/`, press "Sign in", sign in as `dev-admin` with the printed password | "Signed in as admin"; the home page offers "Open a review inbox" |
| 2 | Enter `architecture-authoring`, press "Open the inbox" | One proposal under "Awaiting a decision": "Review the exact ASSESSMENT output and host-composed project revision." (11 records); nothing under "Approved, not yet applied" |
| 3 | Open the proposal; read "Diagnostics" | Tables "Contract findings" and "Source diagnostics", lists "Generator gaps" and "Syllabus gaps": the synthetic output's known problems |
| 4 | Read "Changes against the applied version" | One block per record; changed ones open, with the field path, the applied and the proposed value; unchanged ones closed. Judge: can a teacher tell what the assessment changes? |
| 5 | Press "Record the decision" without choosing | "Choose a decision."; nothing recorded |
| 6 | Choose "Approve", write a reason, press "Record the decision" | "Decision recorded: Approve."; status "Approved, not applied"; an "Application" section with "Apply the change" |
| 7 | Press "Apply the change" | "Change applied. The context is now at version …"; status "Applied" |
| 8 | "Back to the review inbox" | Both lists empty |
| 9 | Conflict: stop the API, rebuild the seed into a new directory (repeat the `SEED=…` line and the `export ALM_STORE…` line), start the API again; open the proposal in the browser (sign in again: sessions live in API memory). In a third terminal, with the same exports: `.venv/bin/python -m learning --db "$ALM_STORE" --policy "$ALM_POLICY_DIR"/*.json --subject admin --context architecture-authoring decide '<proposal ref>' REJECT --reason "Other reviewer"` and type `CONFIRM`. The proposal ref is in `$SEED/seed.json` under `pending_proposals` | Then approve in the browser: the red message "This proposal changed after you opened it…", status "Rejected", no decision form |
| 10 | Keyboard only: reload the page, press Tab | "Skip to main content" first; every control reachable; focus always visible |

Stop: Ctrl-C both servers, `docker compose -f compose.identity.yml down`.
Questions to answer for the validation: is the summary sentence enough to pick a
proposal? Are the diagnostics readable for a teacher, or only for a developer?
Is the diff by field path understandable?

## Findings (not changed in this PR)

1. **No list of contexts.** The home page asks for the context id because no
   endpoint lists the contexts a subject may review (by design a response never
   reveals which contexts exist, D10). A per-subject list would need an API
   decision.
2. **Array diffs are positional.** A reordered array shows as changes at each
   index. Seen on the seed: the proposed `ExecutionContext` swaps `models[1]` and
   `models[2]` (project model and release catalogue), shown as four changed
   leaves. A diff keyed by `EntityRef` would be clearer for reference lists.
3. **The generator report is parsed from free text.** Diagnostics come from the
   JSON object that follows the sentence in `proposedChange`, a convention of
   the generators, not a contract. A text without such an object is shown as it
   is. A structured field would need a core change.
4. **Not in the browser:** revoking a decision (the API allows it on the current
   revision), decisions on `ResourceBinding` or `Evaluation` records, and the
   delivery import's policy installation. The CLI still does them.
5. **Operation ids live in page memory.** A full page reload between a lost
   answer and the retry creates a new id. This cannot apply twice: after a
   reload the page shows the proposal as `APPLIED` and no apply step.
6. **The "stale" reading of Chat 14 is still to be confirmed.** The conflict test
   relies on it (a new revision after loading is a 409).
7. **Shared working tree.** Two Claude sessions worked in the same directory
   (see the baseline). Future chats should check `ListAgents` or use a git
   worktree when an earlier session may still be running.
8. **CI cost.** The `browser` job installs the Python requirements, Chromium and
   Keycloak: expect several minutes.
9. **Accessibility scope.** axe covers the automatic WCAG 2.1 A/AA rules only. A
   screen-reader pass was not done.
10. **Still open from earlier chats.** Chat 14 findings 3–6 (finding 3 is now
    handled in the UI: a 422 on apply shows the core message and reloads; it is
    still 422, not 409), Chat 12 findings 2, 6, 7, 8; Chat 13 findings 1–6,
    8–10; the roadmap baseline row (Chat 13 finding 12) now covers S01–S07.

## Open decisions

None blocked S07. Still open: the Chat 14 "stale" reading (PR #85 review); what
to do with PR #87 (merge it or close it; both are fine).

## Next step

After the owner reviews and merges this PR (closes #86), M1 is reached. The next
step is **S08 — Agent job worker and progress stream**, which depends on D14
(jobs store). Use the "Prompt for later steps" of the roadmap with `chat-15.md`
as the latest handoff, and check that D14 is recorded as confirmed before
starting.
