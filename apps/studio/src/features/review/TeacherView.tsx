import { useTranslation } from 'react-i18next';

import { readable } from './model';
import { RubricTable } from './RubricTable';
import type { ContentChange, CoursePart, Issue, PlainIssues, TeacherView as View } from './teacher';

const evidenceList = (codes: string[]) => codes.map(readable).join(', ');

function Change({ change }: { change: ContentChange }) {
  const { t } = useTranslation();
  return (
    <li>
      {t(change.message, { value: change.value ?? '' })}
      {change.before !== undefined && change.after !== undefined ? (
        <div className="alm-compare">
          <div>
            <p className="alm-compare__label">{t('review.teacher.changes.now')}</p>
            <p className="alm-text">{change.before}</p>
          </div>
          <div>
            <p className="alm-compare__label">{t('review.teacher.changes.proposed')}</p>
            <p className="alm-text">{change.after}</p>
          </div>
        </div>
      ) : null}
    </li>
  );
}

/** One problem as a sentence of the catalogue. */
export function IssueText({ issue }: { issue: Issue }) {
  const { t } = useTranslation();
  switch (issue.message) {
    case 'review.teacher.issue.generated': return t(issue.message, issue.values);
    case 'review.teacher.issue.tooFew': return t(issue.message, issue.values);
    case 'review.teacher.issue.notAllowed': return t(issue.message, issue.values);
    case 'review.teacher.issue.other': return t(issue.message, issue.values);
    case 'review.teacher.issue.finding': return t(issue.message, issue.values);
  }
}

function IssueList({ heading, issues }: { heading: string; issues: Issue[] }) {
  if (issues.length === 0) return null;
  return (
    <>
      <h3>{heading}</h3>
      <ul>{issues.map((issue, index) => <li key={index}><IssueText issue={issue} /></li>)}</ul>
    </>
  );
}

/** What to check before deciding: problems of the proposal, of the course and its sources, and the generator's notes. */
export function Issues({ issues }: { issues: PlainIssues }) {
  const { t } = useTranslation();
  const problems = issues.generated.length + issues.source.length;
  return (
    <section aria-labelledby="teacher-issues">
      <h2 id="teacher-issues">{t('review.teacher.issues.heading')}</h2>
      {problems === 0 && issues.notes.length === 0 ? <p>{t('review.teacher.issues.none')}</p> : null}
      <IssueList heading={t('review.teacher.issues.generated')} issues={issues.generated} />
      {issues.source.length > 0 ? (
        <details className="alm-disclosure">
          <summary>{t('review.teacher.issues.source', { found: String(issues.source.length) })}</summary>
          <ul>{issues.source.map((issue, index) => <li key={index}><IssueText issue={issue} /></li>)}</ul>
        </details>
      ) : null}
      {issues.notes.length > 0 ? (
        <>
          <h3>{t('review.teacher.issues.notes')}</h3>
          <ul>{issues.notes.map((note) => <li key={note}>{note}</li>)}</ul>
        </>
      ) : null}
    </section>
  );
}

function Changes({ changes }: { changes: ContentChange[] }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="teacher-changes">
      <h2 id="teacher-changes">{t('review.teacher.changes.heading')}</h2>
      {changes.length === 0 ? <p>{t('review.teacher.changes.none')}</p> : (
        <ul className="alm-changes">{changes.map((change, index) => <Change key={index} change={change} />)}</ul>
      )}
    </section>
  );
}

/** Completion rules: when each part of the course counts as completed. The content is the one in use. */
function CompletionRules({ view, issues }: { view: View; issues: PlainIssues }) {
  const { t } = useTranslation();
  return (
    <>
      <section aria-labelledby="teacher-completion">
        <h2 id="teacher-completion">{t('review.teacher.completion.heading')}</h2>
        <p>{t('review.teacher.completion.intro')}</p>
        <ul data-testid="completion-rules">
          {view.rules.map((rule, index) => (
            <li key={index}>{t('review.teacher.completion.rule', { kind: readable(rule.nodeKind), node: rule.node, rule: rule.rule })}</li>
          ))}
        </ul>
      </section>
      {view.compared ? <Changes changes={view.changes} /> : null}
      <Issues issues={issues} />
    </>
  );
}

const PARTS = {
  SOURCE: 'review.teacher.part.SOURCE', SYLLABUS: 'review.teacher.part.SYLLABUS',
  ASSESSMENT: 'review.teacher.part.ASSESSMENT', TEACHER_CONTENT: 'review.teacher.part.TEACHER_CONTENT',
  TRAINER_CONTENT: 'review.teacher.part.TRAINER_CONTENT',
} as const;

function usePartName() {
  const { t } = useTranslation();
  return (kind: string) => t(Object.hasOwn(PARTS, kind) ? PARTS[kind as keyof typeof PARTS] : 'review.teacher.part.other');
}

function Parts({ parts }: { parts: CoursePart[] }) {
  const { t } = useTranslation();
  const partName = usePartName();
  return (
    <ul data-testid="course-parts">
      {parts.map((part, index) => (
        <li key={index}>{t('review.teacher.part.item', { kind: partName(part.kind), title: part.title })}</li>
      ))}
    </ul>
  );
}

/** A project initialization: what it selects, what the course still needs, and why it is approved. */
function Project({ project }: { project: NonNullable<View['project']> }) {
  const { t } = useTranslation();
  const partName = usePartName();
  return (
    <section aria-labelledby="teacher-project">
      <h2 id="teacher-project">{t('review.teacher.project.heading')}</h2>
      <p>{t('review.teacher.project.intro', { id: project.id })}</p>
      <h3>{t('review.teacher.project.selected')}</h3>
      <Parts parts={project.selected} />
      {project.missing.length > 0
        ? <p>{t('review.teacher.project.missing', { kinds: project.missing.map(partName).join(', ') })}</p> : null}
    </section>
  );
}

/** A release: the parts of the course it freezes, and what it does not publish. */
function Release({ release }: { release: NonNullable<View['release']> }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="teacher-release">
      <h2 id="teacher-release">{t('review.teacher.release.heading')}</h2>
      <p>{t('review.teacher.release.intro')}</p>
      <Parts parts={release.parts} />
    </section>
  );
}

/** A delivery import: its units, the resources its requirements use, its agents and its sources. */
function Delivery({ delivery }: { delivery: NonNullable<View['delivery']> }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="teacher-delivery">
      <h2 id="teacher-delivery">{t('review.teacher.delivery.heading')}</h2>
      <p>{t('review.teacher.delivery.intro', { count: delivery.units })}</p>
      {delivery.bindings.length > 0 ? (
        <>
          <h3>{t('review.teacher.delivery.bindings')}</h3>
          <ul>{delivery.bindings.map((binding, index) => <li key={index}>{t('review.teacher.delivery.binding', binding)}</li>)}</ul>
        </>
      ) : null}
      {delivery.agents.length > 0 ? (
        <>
          <h3>{t('review.teacher.delivery.agents')}</h3>
          <ul>
            {delivery.agents.map((agent, index) => (
              <li key={index}>{t('review.teacher.delivery.agent', { role: readable(agent.role), name: agent.name })}</li>
            ))}
          </ul>
        </>
      ) : null}
      {delivery.scopes.length > 0 ? <p>{t('review.teacher.delivery.scopes', { scopes: delivery.scopes.join(', ') })}</p> : null}
    </section>
  );
}

/** What a teacher needs to decide: the changes, the teaching content, and what to check, in plain words. */
export function TeacherView({ view, issues }: { view: View; issues: PlainIssues }) {
  const { t } = useTranslation();
  if (view.kind === 'completion') return <CompletionRules view={view} issues={issues} />;
  if (view.project) return <><Project project={view.project} /><Issues issues={issues} /></>;
  if (view.release) return <><Release release={view.release} /><Issues issues={issues} /></>;
  return (
    <>
      {view.notAccepted !== null
        ? <p data-testid="not-accepted">{t('review.teacher.notAccepted', { reason: view.notAccepted })}</p> : null}
      {view.delivery ? <Delivery delivery={view.delivery} /> : null}
      {view.compared ? <Changes changes={view.changes} /> : null}

      {view.activities.length > 0 ? (
        <section aria-labelledby="teacher-students">
          <h2 id="teacher-students">{t('review.teacher.students.heading')}</h2>
          {view.activities.map((activity, index) => (
            <div key={index} className="alm-card">
              <p className="alm-text">{activity.instruction}</p>
              {activity.evidence.length > 0
                ? <p className="alm-muted">{t('review.teacher.students.evidence', { evidence: evidenceList(activity.evidence) })}</p>
                : null}
            </div>
          ))}
        </section>
      ) : null}

      {view.materials.length > 0 ? (
        <section aria-labelledby="teacher-materials">
          <h2 id="teacher-materials">{t('review.teacher.materials.heading')}</h2>
          {view.materials.map((material, index) => (
            <div key={index} className="alm-card" data-testid="material">
              <h3>{material.title}</h3>
              <p className="alm-text">{material.text}</p>
            </div>
          ))}
        </section>
      ) : null}

      {view.rubrics.length > 0 || view.assessments.length > 0 ? (
        <section aria-labelledby="teacher-assessed">
          <h2 id="teacher-assessed">{t('review.teacher.assessed.heading')}</h2>
          {view.rubrics.map((rubric, index) => (
            <div key={index}>
              <h3>{rubric.name}</h3>
              <RubricTable criteria={rubric.criteria} />
            </div>
          ))}
          {view.assessments.map((assessment, index) => (
            <div key={index}>
              {assessment.conditions.length > 0 ? (
                <>
                  <h3>{t('review.teacher.assessed.conditions')}</h3>
                  <ul>{assessment.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>
                </>
              ) : null}
              {assessment.evidence.length > 0
                ? <p>{t('review.teacher.assessed.accepted', { evidence: evidenceList(assessment.evidence) })}</p> : null}
            </div>
          ))}
        </section>
      ) : null}

      {view.outcomes.length > 0 ? (
        <section aria-labelledby="teacher-outcomes">
          <h2 id="teacher-outcomes">{t('review.teacher.outcomes.heading')}</h2>
          <ul>{view.outcomes.map((outcome) => <li key={outcome}>{outcome}</li>)}</ul>
        </section>
      ) : null}

      {view.requirements.length > 0 ? (
        <section aria-labelledby="teacher-resources">
          <h2 id="teacher-resources">{t('review.teacher.resources.heading')}</h2>
          <ul>
            {view.requirements.map((requirement, index) => (
              <li key={index}>
                <strong>{requirement.mandatory ? t('review.teacher.resources.required') : t('review.teacher.resources.optional')}</strong>
                {': '}{requirement.purpose}
                {requirement.constraints.length > 0
                  ? <ul>{requirement.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {view.kind !== 'other' || view.activities.length > 0 ? null : <p>{t('review.teacher.otherProposal')}</p>}

      <Issues issues={issues} />
    </>
  );
}
