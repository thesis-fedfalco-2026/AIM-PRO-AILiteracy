import { useSession } from '@alm/auth';
import { StatusMessage } from '@alm/ui';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { readable } from '../review/model';
import { LoadFailure, useStatusLabel } from '../review/parts';
import { buildPath, inboxPath, proposalPath } from '../review/paths';
import type { Inbox } from '../review/reviewApi';
import { RubricTable } from '../review/RubricTable';
import { useInbox } from '../review/useInbox';
import { courseOverview } from './course';
import type { CourseNode, CourseOverview, HistoryEntry } from './course';

const SECTIONS = [
  ['course-structure', 'course.structure.heading'],
  ['course-outcomes', 'course.outcomes.heading'],
  ['course-strategies', 'course.strategies.heading'],
  ['course-assessments', 'course.assessments.heading'],
  ['course-materials', 'course.materials.heading'],
  ['course-history', 'course.history.heading'],
] as const;

const VERDICTS = {
  APPROVE: 'course.verdict.approve',
  REJECT: 'course.verdict.reject',
  REQUEST_REVISION: 'course.verdict.requestRevision',
} as const;

const codes = (values: string[]) => values.map(readable).join(', ');

function Node({ node }: { node: CourseNode }) {
  const { t } = useTranslation();
  return (
    <li className="alm-node">
      <p className="alm-node__title"><span className="alm-badge">{readable(node.kind)}</span>{' '}{node.name}</p>
      {node.strategies.length > 0 ? <p>{t('course.structure.strategies', { names: node.strategies.join(', ') })}</p> : null}
      {node.activities.length > 0 ? (
        <ol className="alm-cards">
          {node.activities.map((activity, index) => (
            <li key={index} className="alm-card">
              <p><span className="alm-badge">{readable(activity.intent)}</span>{' '}{readable(activity.format)}</p>
              <p className="alm-text">{activity.instruction}</p>
              {activity.evidence.length > 0
                ? <p className="alm-muted">{t('course.structure.evidence', { evidence: codes(activity.evidence) })}</p> : null}
            </li>
          ))}
        </ol>
      ) : node.children.length === 0 ? <p className="alm-muted">{t('course.structure.noActivities')}</p> : null}
      {node.completion ? <p className="alm-muted">{t('course.structure.completion', { condition: node.completion })}</p> : null}
      {node.children.length > 0 ? <ol className="alm-tree">{node.children.map((child, index) => <Node key={index} node={child} />)}</ol> : null}
    </li>
  );
}

function History({ contextId, history }: { contextId: string; history: HistoryEntry[] }) {
  const { t, i18n } = useTranslation();
  const statusLabel = useStatusLabel();
  const when = (at: string) => {
    const date = new Date(at);
    return Number.isNaN(date.getTime()) ? at
      : new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  };
  if (history.length === 0) return <p>{t('course.history.empty')}</p>;
  return (
    <ol className="alm-cards">
      {history.map((entry) => (
        <li key={entry.proposalId} className="alm-card">
          <p><strong>{entry.summary || entry.proposalId}</strong>{' · '}{statusLabel(entry.status)}</p>
          {entry.events.length === 0 ? <p className="alm-muted">{t('course.history.noEvent')}</p> : (
            <ul>
              {entry.events.map((event, index) => (
                <li key={index}>
                  {event.kind === 'applied' ? t('course.history.applied', { at: when(event.at) }) : t('course.history.decision', {
                    at: when(event.at), by: event.by, reason: event.reason,
                    verdict: Object.hasOwn(VERDICTS, event.decision)
                      ? t(VERDICTS[event.decision as keyof typeof VERDICTS]) : event.decision,
                  })}
                </li>
              ))}
            </ul>
          )}
          {entry.status === 'AWAITING_DECISION' || entry.status === 'APPROVED'
            ? <p><Link to={proposalPath(contextId, entry.proposalId)}>{t('course.history.review')}</Link></p> : null}
        </li>
      ))}
    </ol>
  );
}

function CourseSections({ contextId, course }: { contextId: string; course: CourseOverview }) {
  const { t } = useTranslation();
  return (
    <>
      <nav aria-labelledby="course-contents">
        <h2 id="course-contents">{t('course.contents')}</h2>
        <ul>{SECTIONS.map(([id, key]) => <li key={id}><a href={`#${id}`}>{t(key)}</a></li>)}</ul>
      </nav>

      <section aria-labelledby="course-structure">
        <h2 id="course-structure">{t('course.structure.heading')}</h2>
        <p>{t('course.structure.intro')}</p>
        {course.structure ? <ol className="alm-tree"><Node node={course.structure} /></ol> : <p>{t('course.structure.empty')}</p>}
      </section>

      <section aria-labelledby="course-outcomes">
        <h2 id="course-outcomes">{t('course.outcomes.heading')}</h2>
        {course.outcomes.length === 0 ? <p>{t('course.outcomes.empty')}</p> : (
          <ul>
            {course.outcomes.map((outcome, index) => (
              <li key={index}>
                {outcome.statement}
                {outcome.competences.length > 0
                  ? <p className="alm-muted">{t('course.outcomes.competences', { names: outcome.competences.join(', ') })}</p> : null}
              </li>
            ))}
          </ul>
        )}
        {course.competences.length > 0 ? (
          <>
            <h3>{t('course.outcomes.competencesHeading')}</h3>
            <dl className="alm-facts">
              {course.competences.map((competence) => (
                <div key={competence.name} className="alm-facts__row">
                  <dt>{competence.name}</dt>
                  <dd>{competence.definition}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}
      </section>

      <section aria-labelledby="course-strategies">
        <h2 id="course-strategies">{t('course.strategies.heading')}</h2>
        {course.strategies.length === 0 ? <p>{t('course.strategies.empty')}</p> : course.strategies.map((strategy) => (
          <div key={strategy.name} className="alm-card">
            <h3>{strategy.name}</h3>
            <p className="alm-muted">{strategy.family}</p>
            <p className="alm-text">{strategy.rationale}</p>
            {strategy.constraints.length > 0
              ? <p>{t('course.strategies.conditions', { conditions: strategy.constraints.join('; ') })}</p> : null}
          </div>
        ))}
      </section>

      <section aria-labelledby="course-assessments">
        <h2 id="course-assessments">{t('course.assessments.heading')}</h2>
        {course.assessments.length === 0 ? <p>{t('course.assessments.empty')}</p> : course.assessments.map((assessment, index) => (
          <div key={index} className="alm-card">
            {assessment.activities.map((activity) => <p key={activity}>{t('course.assessments.activity', { activity })}</p>)}
            {assessment.rubric ? (
              <>
                <h3>{assessment.rubric.name}</h3>
                <RubricTable criteria={assessment.rubric.criteria} />
              </>
            ) : <p>{t('course.assessments.noRubric')}</p>}
            {assessment.conditions.length > 0 ? (
              <>
                <h3>{t('course.assessments.conditions')}</h3>
                <ul>{assessment.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>
              </>
            ) : null}
            {assessment.evidence.length > 0
              ? <p>{t('course.assessments.evidence', { evidence: codes(assessment.evidence) })}</p> : null}
          </div>
        ))}
      </section>

      <section aria-labelledby="course-materials">
        <h2 id="course-materials">{t('course.materials.heading')}</h2>
        {course.materials.length === 0 ? <p>{t('course.materials.empty')}</p> : course.materials.map((material) => (
          <details key={material.title} className="alm-disclosure">
            <summary><span className="alm-disclosure__title">{material.title}</span></summary>
            <p className="alm-text">{material.text}</p>
            {material.conditions ? <p className="alm-muted alm-text">{material.conditions}</p> : null}
          </details>
        ))}
        {course.sources.length > 0 ? (
          <>
            <h3>{t('course.materials.sources')}</h3>
            <ul>
              {course.sources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} rel="noreferrer noopener" target="_blank">{source.title}</a>
                  {source.conditions ? <p className="alm-muted">{source.conditions}</p> : null}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section aria-labelledby="course-history">
        <h2 id="course-history">{t('course.history.heading')}</h2>
        <p>{t('course.history.intro')}</p>
        <History contextId={contextId} history={course.history} />
      </section>
    </>
  );
}

/** Whether the subject takes part in the context as its author or administrator. */
function mayAuthor(inbox: Inbox, subjectKey: string) {
  return inbox.entities.some(({ type, fields }) => type === 'Participant' && fields.subjectKey === subjectKey
    && Array.isArray(fields.roles) && fields.roles.some((role) => role === 'ADMINISTRATOR' || role === 'CONTENT_RESPONSIBLE'));
}

function CourseContent({ contextId, inbox }: { contextId: string; inbox: Inbox }) {
  const { t } = useTranslation();
  const { state } = useSession();
  const course = courseOverview(inbox.context, inbox.entities);
  const subjectKey = state.status === 'signed-in' ? state.session.subjectKey : '';
  if (!course && inbox.context.fields.learningDesign === undefined && mayAuthor(inbox, subjectKey)) {
    // A new course: nothing to show until its syllabus is applied.
    return (
      <>
        <StatusMessage>{t('course.notStarted')}</StatusMessage>
        <p><Link to={buildPath(contextId)}>{t('course.build')}</Link></p>
        <p><Link to={inboxPath(contextId)}>{t('course.review', { count: inbox.pending.length })}</Link></p>
      </>
    );
  }
  if (!course) return <StatusMessage>{t('course.notVisible')}</StatusMessage>;
  return (
    <>
      <p className="alm-lead"><strong>{course.name}</strong></p>
      <p className="alm-muted">{t('course.state', { status: readable(course.status), mode: readable(course.mode) })}</p>
      <p><Link to={inboxPath(contextId)}>{t('course.review', { count: inbox.pending.length })}</Link></p>
      <p><Link to={buildPath(contextId)}>{t('course.continueBuild')}</Link></p>
      <CourseSections contextId={contextId} course={course} />
    </>
  );
}

/** The whole course of a context, read only: structure, outcomes, strategies, assessments, materials, history. */
export function CoursePage({ contextId }: { contextId: string }) {
  const { t } = useTranslation();
  const { state, reload } = useInbox(contextId);
  return (
    <>
      <h1>{t('course.title')}</h1>
      {state.status === 'loading' ? <StatusMessage>{t('course.loading')}</StatusMessage> : null}
      {state.status === 'error' ? <LoadFailure reason={state.reason} onRetry={reload} /> : null}
      {state.status === 'ready' ? <CourseContent contextId={contextId} inbox={state.inbox} /> : null}
    </>
  );
}
