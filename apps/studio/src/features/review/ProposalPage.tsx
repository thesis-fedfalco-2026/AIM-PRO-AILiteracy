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
import type { DecisionKind, Entity, Finding, Inbox, PendingProposal, ReviewFailure } from './reviewApi';
import { useCsrfToken, useReviewServices } from './ReviewServices';
import { inboxPath } from './paths';
import { useInbox } from './useInbox';

type Notice = { tone: 'info' | 'error'; text: string };

const failureOf = (error: unknown): ReviewFailure => (error instanceof ReviewError ? error.reason : 'failed');
const detailOf = (error: unknown) => (error instanceof ReviewError && error.detail ? error.detail : '');

function Facts({ proposal, pending }: { proposal: Entity; pending: PendingProposal | undefined }) {
  const { t } = useTranslation();
  const statusLabel = useStatusLabel();
  return (
    <section aria-labelledby="review-facts">
      <h2 id="review-facts">{t('review.proposal.facts')}</h2>
      <dl className="alm-facts">
        <dt>{t('review.proposal.status')}</dt>
        <dd data-testid="proposal-status">{statusLabel(proposalStatus(proposal))}</dd>
        <dt>{t('review.proposal.proposedBy')}</dt>
        <dd>{proposal.provenance.responsible}</dd>
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
      <h2 id="review-payload">{t('review.payload.heading')}</h2>
      <p>{t('review.payload.intro')}</p>
      <details className="alm-disclosure">
        <summary>{t('review.payload.show')}</summary>
        <pre className="alm-code" data-testid="exact-payload">
          {JSON.stringify({ proposal: pending.proposal, candidates: pending.candidates }, null, 2)}
        </pre>
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
  return (
    <>
      <p className="alm-lead">{explanation.summary}</p>
      <Facts proposal={proposal} pending={pending} />
      {pending || status === 'APPROVED' ? null : <p>{t('review.proposal.notPending', { status: statusLabel(status) })}</p>}
      {status === 'APPROVED' ? <ApplyStep busy={busy} onApply={() => onApply(proposal)} /> : null}
      <Diagnostics findings={findings} contextFindings={inbox.findings} report={explanation.details} />
      {pending ? (
        <>
          <Changes comparisons={compareCandidates(pending.candidates, [inbox.context, ...inbox.entities])} />
          <ExactPayload pending={pending} />
          <DecisionForm busy={busy} onDecide={(decision, reason) => onDecide(pending, decision, reason)} />
        </>
      ) : null}
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
