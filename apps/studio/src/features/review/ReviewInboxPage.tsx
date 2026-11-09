import { Button, StatusMessage } from '@alm/ui';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { latestProposals, proposalExplanation, proposalStatus } from './model';
import { LoadFailure } from './parts';
import type { Entity, Finding, Inbox } from './reviewApi';
import { coursePath, proposalPath } from './paths';
import { plainIssues, teacherView } from './teacher';
import { useInbox } from './useInbox';

function ProposalLink({ contextId, proposal, title, meta }: {
  contextId: string; proposal: Entity; title?: string; meta: string;
}) {
  return (
    <li className="alm-card">
      <Link to={proposalPath(contextId, proposal.id)}>{title || proposalExplanation(proposal).summary || proposal.id}</Link>
      <p className="alm-muted">{meta}</p>
    </li>
  );
}

function InboxLists({ contextId, inbox }: { contextId: string; inbox: Inbox }) {
  const { t } = useTranslation();
  const approved = latestProposals(inbox.entities).filter((proposal) => proposalStatus(proposal) === 'APPROVED');
  return (
    <>
      <section aria-labelledby="inbox-pending">
        <h2 id="inbox-pending">{t('review.inbox.pendingHeading')}</h2>
        {inbox.pending.length === 0 ? <p>{t('review.inbox.pendingEmpty')}</p> : (
          <ul className="alm-cards">
            {inbox.pending.map(({ proposal, candidates }) => {
              const view = teacherView(candidates, [inbox.context, ...inbox.entities]);
              const findings = (Array.isArray(proposal.fields.findings) ? proposal.fields.findings : []) as unknown as Finding[];
              const issues = plainIssues(proposalExplanation(proposal).details, findings, inbox.findings);
              const task = view.activities[0]?.instruction.split('\n')[0];
              const title = view.isAssessment
                ? (task ? `${t('review.teacher.titleAssessment')}: ${task}` : t('review.teacher.titleAssessment')) : undefined;
              return (
                <ProposalLink key={proposal.id} contextId={contextId} proposal={proposal} {...(title ? { title } : {})}
                  meta={t('review.inbox.pendingMeta', { responsible: proposal.provenance.responsible,
                    issues: String(issues.generated.length + issues.source.length) })} />
              );
            })}
          </ul>
        )}
      </section>
      <section aria-labelledby="inbox-approved">
        <h2 id="inbox-approved">{t('review.inbox.approvedHeading')}</h2>
        {approved.length === 0 ? <p>{t('review.inbox.approvedEmpty')}</p> : (
          <ul className="alm-cards">
            {approved.map((proposal) => (
              <ProposalLink key={proposal.id} contextId={contextId} proposal={proposal}
                meta={t('review.inbox.approvedMeta', { responsible: proposal.provenance.responsible })} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

/** The proposals of a context that await a person: a decision, or the application of an approval. */
export function ReviewInboxPage({ contextId }: { contextId: string }) {
  const { t } = useTranslation();
  const { state, reload } = useInbox(contextId);
  return (
    <>
      <h1>{t('review.inbox.title')}</h1>
      <p className="alm-muted">{t('review.inbox.context', { contextId })}</p>
      <p><Link to={coursePath(contextId)}>{t('review.inbox.course')}</Link></p>
      {state.status === 'loading' ? <StatusMessage>{t('review.inbox.loading')}</StatusMessage> : null}
      {state.status === 'error' ? <LoadFailure reason={state.reason} onRetry={reload} /> : null}
      {state.status === 'ready' ? (
        <>
          <InboxLists contextId={contextId} inbox={state.inbox} />
          <Button variant="secondary" onClick={reload}>{t('review.inbox.reload')}</Button>
        </>
      ) : null}
    </>
  );
}
