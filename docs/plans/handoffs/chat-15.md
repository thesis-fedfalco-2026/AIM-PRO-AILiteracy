# Chat 15 handoff — S07 studio review inbox (milestone M1)

Date: 9 November 2026. Base: `main` at `3b16f21` (PR #85, S06, merged). Step:
**S07** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 2),
**milestone M1: first usable app**. Issue:
[#86](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/86).

- Branch `feat/s07-studio-review-inbox`, in
  [PR #88](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/88):
  `8d3e4f0` (Chat 14 follow-up: CLI `decide` passes its previewed review key),
  `5fe46c9` (S07), `e8acee2` (this handoff), `7a771fc` (teacher view, after
  the owner's validation), and the commit that updates this file.
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

Teacher view (`7a771fc`, after the owner's validation, see below):
`src/features/review/teacher.ts` (pure: `teacherView` gathers the teaching
records and describes their changes in sentences; `plainIssues` turns the
generator report and the findings into sentences grouped by where the problem
is) and `TeacherView.tsx`; `ProposalPage.tsx` leads with it and moves the
identifiers, raw diagnostics, field diff and exact payload into closed
"Technical details"; inbox entries of assessments are named "Proposed
assessment: …" with the number of points to check.

`packages/ui/src/styles.css`: form, table, disclosure, card, badge, code,
reading-text and before/after styles from the existing tokens (no new colour). The routes and behaviour are
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

CI: push run [42608104325](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42608104325)
on `5fe46c9`; push run [42608348009](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42608348009)
and pull_request run [42608386250](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42608386250)
on `e8acee2`; push run on `7a771fc`: all jobs pass, including `browser`. The
commit that updates this file triggers another run, reported in the PR.

After the teacher view (`7a771fc`), local: `npm test` 90 tests OK (82 before;
`teacher-view.test.ts` was written first and passed 7/7 once `teacher.ts`
existed), `typecheck` and `build` OK, `npm run test:browser` 5 passed. The
first browser run of the new assertions failed once on a wrong count in the
test (7 visible list items, not 5: the generator notes), corrected in the test.

## Owner validation (9 November 2026)

The owner used the studio on a fresh seed (Keycloak, API on 58001, `npm run
dev` on 58000).

1. **The first proposal page was incomprehensible for a teacher.** It showed
   the data model: field paths such as `models[1].id`, versions, hashes, the
   `ExecutionContext` record, codes such as `GENERATED_CONTRACT`. The teaching
   content was in the payload but not shown. On the seed the only teaching
   change is one assessment condition; everything else is links and versions.
   Answer, the owner choosing "continue S07" and "English stays": the teacher
   view described in Changes and in the guide. The owner's verdict on it:
   "better".
2. **The owner's wider expectation.** A teacher or trainer structures a
   course progressively (syllabus, lessons, activities, targets, competences,
   then rubrics and assessments), with agents that help improve its quality;
   can upload an AIM-PRO model to start the build; sees the whole course in
   sections (syllabus, assessments, rubrics, the process behind them); then
   validates the course so that it can be used. A learner signs in, sees the
   courses they are enrolled in, opens one, sees the material and the
   syllabus, takes part in activities, exercises and assessments, and talks to
   the Socratic agent. The review inbox alone shows none of the whole course.
   The owner decided: **a read-only course overview as a new step after #88,
   and a roadmap revision proposal** written for the owner to approve.

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
| 2 | Enter `architecture-authoring`, press "Open the inbox" | One proposal under "Awaiting a decision": "Proposed assessment: Submit a fictional business reminder prompt and explain two choices.", "Points to check: 12"; nothing under "Approved, not yet applied" |
| 3 | Open the proposal; read "What changes" | One sentence: "Assessment condition added: “Explain two prompting choices.”" Judge: is it clear that nothing else in the teaching content changes? |
| 4 | Read the activity, the rubric (criteria and levels), the outcome, the resources and "To check before deciding"; open "Technical details" | Five problems of the generated content and two notes shown; the seven problems of the source material behind a closed "(7)"; the technical details hold ids, raw diagnostics, the field diff and the exact payload |
| 5 | Press "Record the decision" without choosing | "Choose a decision."; nothing recorded |
| 6 | Choose "Approve", write a reason, press "Record the decision" | "Decision recorded: Approve."; status "Approved, not applied"; an "Application" section with "Apply the change" |
| 7 | Press "Apply the change" | "Change applied. The context is now at version …"; status "Applied" |
| 8 | "Back to the review inbox" | Both lists empty |
| 9 | Conflict: stop the API, rebuild the seed into a new directory (repeat the `SEED=…` line and the `export ALM_STORE…` line), start the API again; open the proposal in the browser (sign in again: sessions live in API memory). In a third terminal, with the same exports: `.venv/bin/python -m learning --db "$ALM_STORE" --policy "$ALM_POLICY_DIR"/*.json --subject admin --context architecture-authoring decide '<proposal ref>' REJECT --reason "Other reviewer"` and type `CONFIRM`. The proposal ref is in `$SEED/seed.json` under `pending_proposals` | Then approve in the browser: the red message "This proposal changed after you opened it…", status "Rejected", no decision form |
| 10 | Keyboard only: reload the page, press Tab | "Skip to main content" first; every control reachable; focus always visible |

Stop: Ctrl-C both servers, `docker compose -f compose.identity.yml down`.
Questions to answer for the validation: is the inbox title enough to pick a
proposal? Is "What changes" enough to decide without the technical details? Are
the sentences of "To check before deciding" readable for a teacher?

## Findings (not changed in this PR)

1. **The studio shows no course as a whole** (owner validation, point 2). Planned
   as a new read-only step after #88; the data is already in the S05 reads.
   The other gaps the owner named are proposed in the roadmap revision: AIM-PRO
   upload to start a build (today the Curator reads an export file; D16 open),
   progressive refinement with agents (S09 leaves the Design Agent conversation
   out), course validation (S10, activation blocked by D4 until S11/G7), and on
   the learner side the course catalogue, enrolment and material views (S13
   covers practice and progress only).
2. **No list of contexts.** The home page asks for the context id because no
   endpoint lists the contexts a subject may review (by design a response never
   reveals which contexts exist, D10). A per-subject list would need an API
   decision.
3. **Array diffs are positional** (technical details only now). A reordered array shows as changes at each
   index. Seen on the seed: the proposed `ExecutionContext` swaps `models[1]` and
   `models[2]` (project model and release catalogue), shown as four changed
   leaves. A diff keyed by `EntityRef` would be clearer for reference lists.
4. **The generator report is parsed from free text.** Diagnostics come from the
   JSON object that follows the sentence in `proposedChange`, a convention of
   the generators, not a contract. A text without such an object is shown as it
   is. A structured field would need a core change.
5. **Not in the browser:** revoking a decision (the API allows it on the current
   revision), decisions on `ResourceBinding` or `Evaluation` records, and the
   delivery import's policy installation. The CLI still does them.
6. **Operation ids live in page memory.** A full page reload between a lost
   answer and the retry creates a new id. This cannot apply twice: after a
   reload the page shows the proposal as `APPLIED` and no apply step.
7. **The "stale" reading of Chat 14 is still to be confirmed.** The conflict test
   relies on it (a new revision after loading is a 409).
8. **Shared working tree.** Two Claude sessions worked in the same directory
   (see the baseline). Future chats should check `ListAgents` or use a git
   worktree when an earlier session may still be running.
9. **CI cost.** The `browser` job installs the Python requirements, Chromium and
   Keycloak: expect several minutes.
10. **Accessibility scope.** axe covers the automatic WCAG 2.1 A/AA rules only. A
   screen-reader pass was not done.
11. **The teacher view covers assessments only.** Teacher and trainer content,
    releases and imports show their summary sentence and the technical details.
    Problems "in the generated content" still quote the validator's message
    (for example "Input should be 'Low', 'Medium' or 'High'").
12. **Still open from earlier chats.** Chat 14 findings 3–6 (finding 3 is now
    handled in the UI: a 422 on apply shows the core message and reloads; it is
    still 422, not 409), Chat 12 findings 2, 6, 7, 8; Chat 13 findings 1–6,
    8–10; the roadmap baseline row (Chat 13 finding 12) now covers S01–S07.

## Open decisions

None blocked S07. Still open: the Chat 14 "stale" reading (PR #85 review); what
to do with PR #87 (merge it or close it; both are fine).

## Next step

After the owner merges PR #88 (closes #86), M1 is reached. By the owner's
decision of 9 November 2026 the next work is, before S08:

1. **A read-only course overview in the studio** (new step, its own issue and
   PR): the course in sections (syllabus, outcomes and targets, competences,
   lessons and activities, rubrics, assessments, the history of decisions),
   from the S05 reads, with no API change.
2. **A roadmap revision proposal** with the owner's vision (see "Owner
   validation"), for the owner to approve in a PR.

S08 (agent job worker, D14) follows the revised roadmap.

---

# Part 2 — S07b studio course overview (read-only)

Same chat, after the owner's decision of 9 November 2026 (see "Owner
validation"). Issue
[#89](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/89).
Branch `feat/s07b-course-overview`, stacked on `feat/s07-studio-review-inbox`
(PR #88 was not merged yet); its PR targets that branch and is retargeted to
`main` once #88 is merged.

## Objective

A teacher or trainer sees the whole course of a context in sections, in plain
words, read only.

## Changes

- `apps/studio/src/features/course/course.ts` (pure, `courseOverview`) and
  `CoursePage.tsx`; route `/contexts/{context_id}/course`; the section rules are
  in the guide, "Studio course overview (S07b)".
- Home: "Open the course" (default) and "Open the review inbox"; the inbox links
  to the course, the course to the inbox with the pending count; the history
  links pending and approved proposals to their review page.
- `review/RubricTable.tsx` extracted from the teacher view and reused.
- Styles: course tree, actions row, definition-list rows.
- Browser tests: `course.spec.ts`; the setup signs in `dev-learner` too.
- No API route, OpenAPI snapshot, core module, store schema, metamodel or
  AIM-PRO/jjodel export changed. No model call.

## Verification

Contract tests first: `studio/test/course-model.test.ts` (8 tests) was written
before `course.ts` and passed once it existed; `studio/test/course.test.tsx`
(page) and the updated home test followed. Local:

| Check | Result |
| --- | --- |
| `npm run check:client`, `typecheck`, `test`, `build` | OK, OK, 101 tests OK (90 before), OK |
| `npm run test:browser` | 8 passed (2 sign-ins + 6 tests) |
| `git diff --check` | exit 0 |
| `unittest discover -q`, telemetry off | 832 tests, OK, 142 skipped (no Python change) |

The first page-test run failed once on the test (`findByRole('status')` found
the session's loading message first), corrected in the test. A full-page
screenshot of the seeded course was looked at.

## Acceptance items of #89

| Item | Status | Evidence |
| --- | --- | --- |
| Every section shows the seed's content | Done | `course.spec.ts` "the course page shows the whole seeded course and writes nothing" |
| No write request; store unchanged | Done | same test: only `GET` requests; SHA-256 of `alm.sqlite` equal before and after |
| A learner-only subject sees no authoring content | Done | `course.spec.ts` "as a learner" (`dev-learner`, `architecture-delivery-2`) |
| axe passes | Done | both tests, every disclosure open |
| Docs | Done | guide section; this part |

## Findings (S07b)

1. **History sentences are the generators' wording** ("Review the exact
   ASSESSMENT output and host-composed project revision."). A teacher-facing
   name per proposal kind would need either a studio mapping by kind or a
   structured kind on the proposal.
2. **Materials are not linked to activities by reference.** An activity names
   its material only in the text of a resource requirement ("Use the complete
   assigned material: Synthetic WORKSHEET"); the page lists materials apart
   rather than guess links.
3. **Course versus context.** The page shows one context's active learning
   design. A context without one, or a learner, gets the not-visible message;
   the delivery contexts show the imported release's design when their policy
   is installed.
4. **The owner's other expectations** (progressive refinement with agents,
   AIM-PRO upload, course validation, the learner's catalogue and course
   view) are for the roadmap revision proposal.

## Next step (after Part 2)

The owner merges #88, then this PR (retargeted to `main`). The roadmap revision
proposal follows as its own PR; S08 waits for it.
