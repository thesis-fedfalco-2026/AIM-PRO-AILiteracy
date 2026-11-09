import { useSession } from '@alm/auth';
import { StatusMessage } from '@alm/ui';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApplyStep } from './ApplyStep';
import { Changes } from './Changes';
import { DECISION_KEYS, DecisionForm } from './DecisionForm';
import { Diagnostics } from './Diagnostics';
import { compareCandidates, latestProposals, proposalExplanation, proposalStatus, refOf } from './model';
import { LoadFailure, useStatusLabel } from './parts';
import { ReviewError } from './reviewApi';
import type { DecisionKind, Entity, Finding, Inbox, JsonValue, PendingProposal, ReviewFailure } from './reviewApi';
import { useCsrfToken, useReviewServices } from './ReviewServices';
import { inboxPath } from './paths';
import { plainIssues, teacherView } from './teacher';
import { TeacherView } from './TeacherView';
import { useInbox } from './useInbox';

type Notice = { tone: 'info' | 'error'; text: string };

const failureOf = (error: unknown): ReviewFailure => (error instanceof ReviewError ? error.reason : 'failed');
const detailOf = (error: unknown) => (error instanceof ReviewError && error.detail ? error.detail : '');

/** Identifiers and versions of the proposal, for administrators. */
function Facts({ proposal, pending }: { proposal: Entity; pending: PendingProposal | undefined }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="review-facts">
      <h3 id="review-facts">{t('review.proposal.facts')}</h3>
      <dl className="alm-facts">
        <dt>{t('review.proposal.id')}</dt>
        <dd><code>{proposal.id}</code></dd>
        <dt>{t('review.proposal.revision')}</dt>
        <dd><code>{proposal.version}</code></dd>
        <dt>{t('review.proposal.baseVersion')}</dt>
        <dd><code>{String(proposal.fields.baseContextVersion ?? '')}</code></dd>
        {pending ? (
          <>
            <dt>{t('review.proposal.payloadKey')}</dt>
            <dd><code>{pending.reviewPayloadKey}</code></dd>
          </>
        ) : null}
      </dl>
    </section>
  );
}

function ExactPayload({ pending }: { pending: PendingProposal }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="review-payload">
      <h3 id="review-payload">{t('review.payload.heading')}</h3>
      <p>{t('review.payload.intro')}</p>
      <pre className="alm-code" data-testid="exact-payload">
        {JSON.stringify({ proposal: pending.proposal, candidates: pending.candidates }, null, 2)}
      </pre>
    </section>
  );
}

/** Everything a teacher does not need, closed by default: identifiers, raw diagnostics, field diff, payload. */
function TechnicalDetails({ proposal, pending, inbox, findings, report }: {
  proposal: Entity; pending: PendingProposal | undefined; inbox: Inbox; findings: Finding[];
  report: Record<string, JsonValue> | null;
}) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="review-technical">
      <h2 id="review-technical">{t('review.teacher.technical.heading')}</h2>
      <details className="alm-disclosure" data-testid="technical-details">
        <summary>{t('review.teacher.technical.show')}</summary>
        <p>{t('review.teacher.technical.intro')}</p>
        <Facts proposal={proposal} pending={pending} />
        <Diagnostics findings={findings} contextFindings={inbox.findings} report={report} />
        {pending ? (
          <>
            <Changes comparisons={compareCandidates(pending.candidates, [inbox.context, ...inbox.entities])} />
            <ExactPayload pending={pending} />
          </>
        ) : null}
      </details>
    </section>
  );
}

function ProposalContent({ inbox, proposalId, busy, onDecide, onApply }: {
  inbox: Inbox; proposalId: string; busy: boolean;
  onDecide(pending: PendingProposal, decision: DecisionKind, reason: string): void;
  onApply(proposal: Entity): void;
}) {
  const { t } = useTranslation();
  const statusLabel = useStatusLabel();
  const pending = inbox.pending.find((item) => item.proposal.id === proposalId);
  const proposal = latestProposals(inbox.entities).find((item) => item.id === proposalId) ?? pending?.proposal;
  if (!proposal) return <StatusMessage tone="error">{t('review.proposal.notFound', { proposal: proposalId })}</StatusMessage>;

  const explanation = proposalExplanation(proposal);
  const status = proposalStatus(proposal);
  const findings = (Array.isArray(proposal.fields.findings) ? proposal.fields.findings : []) as unknown as Finding[];
  const issues = plainIssues(explanation.details, findings, inbox.findings);
  const view = pending ? teacherView(pending.candidates, [inbox.context, ...inbox.entities]) : null;
  return (
    <>
      <p className="alm-lead">
        <strong>{view?.isAssessment ? t('review.teacher.titleAssessment') : t('review.teacher.titleOther')}</strong>
      </p>
      <p>
        {t('review.teacher.byline', { responsible: proposal.provenance.responsible })}
        {' · '}
        <span data-testid="proposal-status">{statusLabel(status)}</span>
      </p>
      {view?.isAssessment ? null : <p>{explanation.summary}</p>}
      {pending || status === 'APPROVED' ? null : <p>{t('review.proposal.notPending', { status: statusLabel(status) })}</p>}
      {status === 'APPROVED' ? <ApplyStep busy={busy} onApply={() => onApply(proposal)} /> : null}
      {view ? <TeacherView view={view} issues={issues} /> : null}
      {pending ? <DecisionForm busy={busy} onDecide={(decision, reason) => onDecide(pending, decision, reason)} /> : null}
      <TechnicalDetails proposal={proposal} pending={pending} inbox={inbox} findings={findings} report={explanation.details} />
    </>
  );
}

/** One proposal: what it changes, its diagnostics, the decision and, once approved, the application. */
export function ProposalPage({ contextId, proposalId }: { contextId: string; proposalId: string }) {
  const { t } = useTranslation();
  const { reload: reloadSession } = useSession();
  const { api, operations } = useReviewServices();
  const csrfToken = useCsrfToken();
  const { state, reload } = useInbox(contextId);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);

  /** Run a write; `settle` maps a failure to the notice and says whether the page reloads. */
  const write = async (run: () => Promise<Notice>, settle: (failure: ReviewFailure, detail: string) => [Notice, boolean]) => {
    setBusy(true);
    setNotice(null);
    let reloadAfter = true;
    try {
      setNotice(await run());
    } catch (error) {
      const failure = failureOf(error);
      if (failure === 'signed-out') {
        setBusy(false);
        void reloadSession();
        return;
      }
      const [failed, reloads] = settle(failure, detailOf(error));
      setNotice(failed);
      reloadAfter = reloads;
    }
    setBusy(false);
    if (reloadAfter) reload();
  };

  const decide = (pending: PendingProposal, decision: DecisionKind, reason: string) => void write(
    async () => {
      await api.decide(contextId, csrfToken, {
        target: refOf(pending.proposal), decision, reason, reviewPayloadKey: pending.reviewPayloadKey,
      });
      return { tone: 'info', text: t('review.decision.recorded', { decision: t(DECISION_KEYS[decision]) }) };
    },
    (failure, detail) => [{
      tone: 'error',
      text: failure === 'conflict' ? t('review.decision.conflict')
        : failure === 'refused' ? t('review.decision.refused', { detail })
          : failure === 'forbidden' ? t('review.decision.forbidden') : t('review.decision.failed'),
    }, true],
  );

  const apply = (proposal: Entity) => void write(
    async () => {
      const change = await api.apply(contextId, csrfToken, refOf(proposal), operations.for(contextId, refOf(proposal)));
      return { tone: 'info', text: t('review.apply.applied', { version: String(change.fields.newVersion ?? '') }) };
    },
    // Without an answer the change may or may not be applied: keep the page, a retry replays the operation.
    (failure, detail) => failure === 'failed' ? [{ tone: 'error', text: t('review.apply.failed') }, false] : [{
      tone: 'error',
      text: failure === 'forbidden' ? t('review.apply.forbidden')
        : failure === 'unavailable' ? t('review.errors.unavailable') : t('review.apply.conflict', { detail }),
    }, true],
  );

  return (
    <>
      <p><Link to={inboxPath(contextId)}>{t('review.proposal.back')}</Link></p>
      <h1>{t('review.proposal.title')}</h1>
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {state.status === 'loading' ? <StatusMessage>{t('review.inbox.loading')}</StatusMessage> : null}
      {state.status === 'error' ? <LoadFailure reason={state.reason} onRetry={reload} /> : null}
      {state.status === 'ready'
        ? <ProposalContent inbox={state.inbox} proposalId={proposalId} busy={busy} onDecide={decide} onApply={apply} />
        : null}
    </>
  );
}
