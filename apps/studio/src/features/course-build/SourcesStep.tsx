import { Button, StatusMessage } from '@alm/ui';
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { DISCOVERY, PREPARATION } from './buildApi';
import type {
  CoverageRequirement, ExportReport, ExportTargets, JobView, SourceDiscovery, SourcePlan, SourcePreparation,
} from './buildApi';
import { useBuildServices } from './BuildServices';
import { describedBy, Field, TextInput, useFollowedJob, useStep } from './parts';
import { useCsrfToken } from '../review/ReviewServices';

type Excerpt = SourceDiscovery['excerpts'][number] | SourcePreparation['excerpts'][number];

const lines = (value: string) => value.split('\n').map((line) => line.trim()).filter(Boolean);

/** The licence of an excerpt and the corpus verdict on it, as the conditions the teacher reviews. */
function UsageConditions({ excerpt }: { excerpt: Excerpt }) {
  const { t } = useTranslation();
  return (
    <p>
      {excerpt.licence_verdict
        ? t('build.sources.usage', { licence: excerpt.licence, verdict: excerpt.licence_verdict })
        : t('build.sources.usageNoVerdict', { licence: excerpt.licence })}
    </p>
  );
}

function ExcerptText({ excerpt }: { excerpt: Excerpt }) {
  const { t } = useTranslation();
  return (
    <>
      <p><a href={excerpt.uri} target="_blank" rel="noreferrer">{excerpt.uri}</a></p>
      <UsageConditions excerpt={excerpt} />
      <details className="alm-disclosure">
        <summary>{t('build.sources.read')}</summary>
        <blockquote>{excerpt.text}</blockquote>
      </details>
    </>
  );
}

/** The status of a discovery or preparation job, in words. */
function SourceJobStatus({ job }: { job: JobView }) {
  const { t } = useTranslation();
  switch (job.status) {
    case 'QUEUED': return <StatusMessage>{t('build.sources.queued')}</StatusMessage>;
    case 'RUNNING': return (
      <StatusMessage>{t(job.job.kind === DISCOVERY ? 'build.sources.searching' : 'build.sources.preparing')}</StatusMessage>
    );
    case 'COMPLETED': return <StatusMessage>{t('build.sources.found')}</StatusMessage>;
    case 'AWAITING_CHOICE': return <StatusMessage>{t('build.sources.awaiting')}</StatusMessage>;
    case 'ACCEPTED': return <StatusMessage>{t('build.sources.accepted')}</StatusMessage>;
    case 'DECLINED': return <StatusMessage>{t('build.sources.declined')}</StatusMessage>;
    case 'ABANDONED': return <StatusMessage tone="error">{t('build.curator.abandoned')}</StatusMessage>;
    default: return (
      <>
        <StatusMessage tone="error">{t('build.sources.ended', { detail: job.detail ?? '' })}</StatusMessage>
        <p>{t('build.sources.retry')}</p>
      </>
    );
  }
}

function DiscoveryForm({ contextId, busyJob, onQueued }: {
  contextId: string; busyJob: boolean; onQueued(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [scope, setScope] = useState('');
  const [queries, setQueries] = useState('');
  const [k, setK] = useState('10');
  const [missing, setMissing] = useState({ scope: false, queries: false, k: false });
  const requestId = useRef<string | null>(null);
  const change = (set: (value: string) => void) => (value: string) => {
    requestId.current = null;
    set(value);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = lines(queries);
    const limit = Number(k);
    const invalid = {
      scope: !scope.trim(), queries: found.length === 0 || found.length > 20 || new Set(found).size !== found.length,
      k: !Number.isInteger(limit) || limit < 1 || limit > 20,
    };
    setMissing(invalid);
    if (invalid.scope || invalid.queries || invalid.k) return;
    requestId.current ??= newRequestId();
    const current = requestId.current;
    void run(async () => {
      const queued = await api.queueDiscovery(contextId, csrfToken, current, {
        sourceScope: scope.trim(), queries: found.map((query) => ({ query, k: limit })),
      });
      requestId.current = null;
      onQueued(queued);
      return null;
    });
  };

  return (
    <form className="alm-form" noValidate onSubmit={submit}>
      <Field id={`${id}-scope`} label={t('build.sources.scope')} hint={t('build.curator.scopeHint')}
        error={missing.scope ? t('build.curator.scopeRequired') : null}>
        <TextInput id={`${id}-scope`} value={scope} onChange={change(setScope)} invalid={missing.scope} hint />
      </Field>
      <Field id={`${id}-queries`} label={t('build.sources.queries')} hint={t('build.sources.queriesHint')}
        error={missing.queries ? t('build.sources.queriesRequired') : null}>
        <textarea id={`${id}-queries`} className="alm-input" rows={3} value={queries} aria-invalid={missing.queries}
          aria-describedby={describedBy(`${id}-queries`, true, missing.queries)}
          onChange={(event) => change(setQueries)(event.target.value)} />
      </Field>
      <Field id={`${id}-k`} label={t('build.sources.k')} hint={t('build.sources.kHint')}
        error={missing.k ? t('build.sources.kRequired') : null}>
        <input id={`${id}-k`} className="alm-input" type="number" min={1} max={20} value={k} aria-invalid={missing.k}
          aria-describedby={describedBy(`${id}-k`, true, missing.k)}
          onChange={(event) => change(setK)(event.target.value)} />
      </Field>
      <Button type="submit" busy={busy || busyJob}>{t('build.sources.search')}</Button>
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
    </form>
  );
}

const ACTORS: CoverageRequirement['actor'][] = ['LEARNER', 'FACILITATOR', 'PEER'];
const INTENTS: CoverageRequirement['expected_intent'][] = ['EXPLAIN', 'PRACTICE', 'ASSESS'];

interface Row {
  target: string; object: string; field: string; quote: string;
  actor: CoverageRequirement['actor']; intent: CoverageRequirement['expected_intent']; action: string;
}

const EMPTY_ROW: Row = { target: '', object: '', field: '', quote: '', actor: 'LEARNER', intent: 'PRACTICE', action: '' };

/** The text of a field of an object of the targets, or null. */
function fieldText(targets: ExportTargets, row: Row): string | null {
  const target = targets.targets.find((item) => item.id === row.target);
  const found = target?.id === row.object ? target : target?.practices.find((item) => item.id === row.object);
  return found?.fields[row.field] ?? null;
}

/** A row is complete and its quote is an exact part of the chosen field. */
export function rowProblem(targets: ExportTargets, row: Row): 'missing' | 'quote' | null {
  if (!row.target || !row.object || !row.field || !row.quote.trim() || !row.action.trim()) return 'missing';
  return fieldText(targets, row)?.includes(row.quote) ? null : 'quote';
}

function CoverageRow({ id, index, targets, row, problem, onChange, onRemove }: {
  id: string; index: number; targets: ExportTargets; row: Row; problem: 'missing' | 'quote' | null;
  onChange(row: Row): void; onRemove(): void;
}) {
  const { t } = useTranslation();
  const target = targets.targets.find((item) => item.id === row.target);
  const objects = target ? [target, ...target.practices] : [];
  const object = objects.find((item) => item.id === row.object);
  const text = fieldText(targets, row);
  const select = (name: keyof Row, label: string, value: string, options: [string, string][], reset: Partial<Row> = {}) => (
    <Field id={`${id}-${name}`} label={label}>
      <select id={`${id}-${name}`} className="alm-input" value={value}
        onChange={(event) => onChange({ ...row, ...reset, [name]: event.target.value })}>
        <option value="">{t('build.sources.coverage.choose')}</option>
        {options.map(([key, shown]) => <option key={key} value={key}>{shown}</option>)}
      </select>
    </Field>
  );
  const summary = (fields: Record<string, string>, fallback: string) => {
    const first = Object.values(fields)[0];
    return first ? (first.length > 80 ? `${first.slice(0, 80)}…` : first) : fallback;
  };
  return (
    <fieldset className="alm-fieldset">
      <legend>{t('build.sources.coverage.row', { number: String(index + 1) })}</legend>
      {problem ? (
        <p className="alm-field-error">
          {t(problem === 'quote' ? 'build.sources.coverage.quoteMismatch' : 'build.sources.coverage.incomplete')}
        </p>
      ) : null}
      {select('target', t('build.sources.coverage.target'), row.target,
        targets.targets.map((item) => [item.id, summary(item.fields, item.id)]), { object: '', field: '' })}
      {select('object', t('build.sources.coverage.object'), row.object,
        objects.map((item) => [item.id, t('build.sources.coverage.objectOption', {
          kind: item.class_name, text: summary(item.fields, item.id) })]), { field: '' })}
      {select('field', t('build.sources.coverage.field'), row.field,
        Object.keys(object?.fields ?? {}).map((name) => [name,
          t(`build.sources.coverage.fields.${name as CoverageRequirement['source_field']}`)]))}
      {text ? <blockquote data-testid="coverage-field-text">{text}</blockquote> : null}
      <Field id={`${id}-quote`} label={t('build.sources.coverage.quote')} hint={t('build.sources.coverage.quoteHint')}>
        <TextInput id={`${id}-quote`} value={row.quote} invalid={problem === 'quote'} hint
          onChange={(quote) => onChange({ ...row, quote })} />
      </Field>
      {select('actor', t('build.sources.coverage.actor'), row.actor,
        ACTORS.map((actor) => [actor, t(`build.sources.coverage.actors.${actor}`)]))}
      {select('intent', t('build.sources.coverage.intent'), row.intent,
        INTENTS.map((intent) => [intent, t(`build.sources.coverage.intents.${intent}`)]))}
      <Field id={`${id}-action`} label={t('build.sources.coverage.action')} hint={t('build.sources.coverage.actionHint')}>
        <TextInput id={`${id}-action`} value={row.action} invalid={problem === 'missing' && !row.action.trim()} hint
          onChange={(action) => onChange({ ...row, action })} />
      </Field>
      <Button variant="secondary" onClick={onRemove}>{t('build.sources.coverage.remove')}</Button>
    </fieldset>
  );
}

/** Optional coverage requirements, anchored in the texts of the uploaded model's targets and practices. */
function CoverageEditor({ contextId, report, targets, rows, problems, onTargets, onRows }: {
  contextId: string; report: ExportReport | null; targets: ExportTargets | null; rows: Row[];
  problems: ('missing' | 'quote' | null)[]; onTargets(targets: ExportTargets): void; onRows(rows: Row[]): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api } = useBuildServices();
  const { busy, notice, run } = useStep();
  const load = () => {
    if (report === null) return;
    void run(async () => {
      onTargets(await api.exportTargets(contextId, report.export, report.scenario, report.competencies));
      return null;
    });
  };
  let body;
  if (report === null) body = <p className="alm-muted">{t('build.sources.coverage.needsUpload')}</p>;
  else if (targets === null) {
    body = <Button variant="secondary" busy={busy} onClick={load}>{t('build.sources.coverage.load')}</Button>;
  } else {
    body = (
      <>
        {rows.map((row, index) => (
          <CoverageRow key={index} id={`${id}-${index}`} index={index} targets={targets} row={row}
            problem={problems[index] ?? null}
            onChange={(next) => onRows(rows.map((item, at) => (at === index ? next : item)))}
            onRemove={() => onRows(rows.filter((_, at) => at !== index))} />
        ))}
        <Button variant="secondary" onClick={() => onRows([...rows, EMPTY_ROW])}>{t('build.sources.coverage.add')}</Button>
      </>
    );
  }
  return (
    <details className="alm-disclosure">
      <summary>{t('build.sources.coverage.heading')}</summary>
      <p>{t('build.sources.coverage.intro')}</p>
      {body}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
    </details>
  );
}

interface Choice { picked: boolean; purpose: string; limitations: string }

/** The source plan of the picked excerpts: the discovery's queries, and limits that state the distribution picked. */
export function sourcePlan(found: SourceDiscovery, sha256: string, choices: Record<string, Choice>,
  requirements: CoverageRequirement[]): SourcePlan {
  const picked = found.excerpts.filter((excerpt) => choices[excerpt.document_id]?.picked);
  const perResource = new Map<string, number>();
  for (const excerpt of picked) perResource.set(excerpt.resource_id, (perResource.get(excerpt.resource_id) ?? 0) + 1);
  return {
    format: 'aimpro-source-plan', format_version: 1, source_sha256: sha256, source_scope: found.source_scope,
    queries: found.queries,
    documents: picked.map((excerpt) => ({
      resource_id: excerpt.resource_id, resource_version: excerpt.resource_version, document_id: excerpt.document_id,
      content_sha256: excerpt.content_sha256, purpose: choices[excerpt.document_id]!.purpose.trim(),
      limitations: lines(choices[excerpt.document_id]!.limitations),
    })),
    min_resources: Math.max(1, perResource.size),
    max_documents_per_resource: Math.max(1, ...perResource.values()),
    coverage_requirements: requirements,
  };
}

function ExcerptPicker({ contextId, job, report, busyJob, onQueued }: {
  contextId: string; job: JobView; report: ExportReport | null; busyJob: boolean; onQueued(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const loading = useStep();
  const [found, setFound] = useState<SourceDiscovery | null>(null);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [rows, setRows] = useState<Row[]>([]);
  const [errors, setErrors] = useState<{ none: boolean; tooMany: boolean; excerpts: string[]; rows: ('missing' | 'quote' | null)[] }>(
    { none: false, tooMany: false, excerpts: [], rows: [] });
  const [targets, setTargets] = useState<ExportTargets | null>(null);
  const requestId = useRef<string | null>(null);
  const { run: load } = loading;

  useEffect(() => {
    setFound(null);
    void load(async () => {
      setFound(await api.readDiscovery(contextId, job.request_id));
      return null;
    });
    // `load` changes on every render; the discovery is read once per job.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, contextId, job.request_id]);

  const choose = (documentId: string, change: Partial<Choice>) => {
    requestId.current = null;
    setChoices((current) => ({
      ...current, [documentId]: { picked: false, purpose: '', limitations: '', ...current[documentId], ...change },
    }));
  };
  const changeRows = (next: Row[]) => {
    requestId.current = null;
    setRows(next);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (found === null || report === null) return;
    const picked = found.excerpts.filter((excerpt) => choices[excerpt.document_id]?.picked);
    const incomplete = picked.filter((excerpt) => {
      const choice = choices[excerpt.document_id]!;
      return !choice.purpose.trim() || lines(choice.limitations).length === 0;
    }).map((excerpt) => excerpt.document_id);
    const rowProblems = targets === null ? rows.map(() => null) : rows.map((row) => rowProblem(targets, row));
    const next = { none: picked.length === 0, tooMany: picked.length > 20, excerpts: incomplete, rows: rowProblems };
    setErrors(next);
    if (next.none || next.tooMany || incomplete.length > 0 || rowProblems.some(Boolean)) return;
    const requirements: CoverageRequirement[] = rows.map((row, index) => ({
      key: `requirement-${index + 1}`, source_target_id: row.target, source_object_id: row.object,
      source_field: row.field as CoverageRequirement['source_field'], source_quote: row.quote,
      actor: row.actor, expected_intent: row.intent, required_action: row.action.trim(),
    }));
    requestId.current ??= newRequestId();
    const current = requestId.current;
    void run(async () => {
      const queued = await api.queuePreparation(contextId, csrfToken, current, {
        export: report.export, scenario: report.scenario, competencies: report.competencies,
        plan: sourcePlan(found, report.export.sha256, choices, requirements),
      });
      requestId.current = null;
      onQueued(queued);
      return null;
    });
  };

  if (found === null) {
    return loading.notice ? <StatusMessage tone={loading.notice.tone}>{loading.notice.text}</StatusMessage>
      : <StatusMessage>{t('build.sources.loading')}</StatusMessage>;
  }
  return (
    <section aria-labelledby={`${id}-heading`}>
      <h3 id={`${id}-heading`}>{t('build.sources.pickHeading')}</h3>
      <p>{t('build.sources.pickIntro', { count: found.excerpts.length })}</p>
      <p className="alm-muted">{t('build.sources.licenceNote')}</p>
      {found.excerpts.length === 0 ? <p>{t('build.sources.nothingFound')}</p> : (
        <form className="alm-form" noValidate onSubmit={submit}>
          {errors.none ? <p className="alm-field-error">{t('build.sources.pickOne')}</p> : null}
          {errors.tooMany ? <p className="alm-field-error">{t('build.sources.tooMany')}</p> : null}
          {found.excerpts.map((excerpt, index) => {
            const choice = choices[excerpt.document_id];
            const key = `${id}-${index}`;
            const incomplete = errors.excerpts.includes(excerpt.document_id);
            return (
              <fieldset key={excerpt.document_id} className="alm-fieldset" data-testid="discovered-excerpt">
                <legend>{t('build.sources.excerpt', { title: excerpt.title, number: String(index + 1) })}</legend>
                <p>{t('build.sources.foundBy', { queries: excerpt.found_by.join(', ') })}</p>
                <ExcerptText excerpt={excerpt} />
                <label className="alm-choice">
                  <input type="checkbox" checked={choice?.picked ?? false}
                    onChange={(event) => choose(excerpt.document_id, { picked: event.target.checked })} />
                  {t('build.sources.use', { number: String(index + 1) })}
                </label>
                {choice?.picked ? (
                  <>
                    <Field id={`${key}-purpose`} label={t('build.sources.purpose')} hint={t('build.sources.purposeHint')}
                      error={incomplete && !choice.purpose.trim() ? t('build.sources.purposeRequired') : null}>
                      <TextInput id={`${key}-purpose`} value={choice.purpose} hint
                        invalid={incomplete && !choice.purpose.trim()}
                        onChange={(purpose) => choose(excerpt.document_id, { purpose })} />
                    </Field>
                    <Field id={`${key}-limitations`} label={t('build.sources.limitations')}
                      hint={t('build.sources.limitationsHint')}
                      error={incomplete && lines(choice.limitations).length === 0 ? t('build.sources.limitationsRequired') : null}>
                      <textarea id={`${key}-limitations`} className="alm-input" rows={2} value={choice.limitations}
                        aria-invalid={incomplete && lines(choice.limitations).length === 0}
                        aria-describedby={describedBy(`${key}-limitations`, true, incomplete)}
                        onChange={(event) => choose(excerpt.document_id, { limitations: event.target.value })} />
                    </Field>
                  </>
                ) : null}
              </fieldset>
            );
          })}
          <CoverageEditor contextId={contextId} report={report} targets={targets} rows={rows} problems={errors.rows}
            onTargets={setTargets} onRows={changeRows} />
          {report === null ? <p className="alm-muted">{t('build.sources.needsUpload')}</p> : (
            <Button type="submit" busy={busy || busyJob}>{t('build.sources.prepare')}</Button>
          )}
          {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
        </form>
      )}
    </section>
  );
}

function PreparationReview({ contextId, job, onJob }: { contextId: string; job: JobView; onJob(job: JobView): void }) {
  const { t } = useTranslation();
  const id = useId();
  const { api } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const loading = useStep();
  const [prepared, setPrepared] = useState<SourcePreparation | null>(null);
  const { run: load } = loading;

  useEffect(() => {
    setPrepared(null);
    void load(async () => {
      setPrepared(await api.readPreparation(contextId, job.request_id));
      return null;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, contextId, job.request_id]);

  const decide = (choice: 'ACCEPTED' | 'DECLINED') => {
    void run(async () => {
      onJob(await api.chooseSources(contextId, csrfToken, job.request_id, choice));
      return null;
    });
  };

  if (prepared === null) {
    return loading.notice ? <StatusMessage tone={loading.notice.tone}>{loading.notice.text}</StatusMessage>
      : <StatusMessage>{t('build.sources.loading')}</StatusMessage>;
  }
  return (
    <section aria-labelledby={`${id}-heading`} data-testid="prepared-sources">
      <h3 id={`${id}-heading`}>{t('build.sources.reviewHeading')}</h3>
      <p>{t('build.sources.reviewIntro', { count: prepared.excerpts.length, scope: prepared.source_scope })}</p>
      <ol>
        {prepared.excerpts.map((excerpt) => (
          <li key={excerpt.document_id}>
            <p><strong>{excerpt.title}</strong></p>
            <dl className="alm-facts">
              <dt>{t('build.sources.purpose')}</dt>
              <dd>{excerpt.purpose}</dd>
              <dt>{t('build.sources.limitations')}</dt>
              <dd>{excerpt.limitations.join('; ')}</dd>
            </dl>
            <ExcerptText excerpt={excerpt} />
          </li>
        ))}
      </ol>
      {prepared.coverage_requirements.length > 0 ? (
        <>
          <h4>{t('build.sources.coverage.heading')}</h4>
          <ul>
            {prepared.coverage_requirements.map((requirement) => (
              <li key={requirement.key}>{t('build.sources.coverage.summary', {
                actor: t(`build.sources.coverage.actors.${requirement.actor}`),
                intent: t(`build.sources.coverage.intents.${requirement.expected_intent}`),
                action: requirement.required_action, quote: requirement.source_quote,
              })}</li>
            ))}
          </ul>
        </>
      ) : null}
      {job.status === 'AWAITING_CHOICE' ? (
        <div className="alm-actions">
          <Button busy={busy} onClick={() => decide('ACCEPTED')}>{t('build.sources.accept')}</Button>
          <Button variant="secondary" busy={busy} onClick={() => decide('DECLINED')}>{t('build.sources.decline')}</Button>
        </div>
      ) : null}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
    </section>
  );
}

/**
 * Prepare the sources of the course: search, pick the excerpts and say what
 * each is for, then review the prepared sources and accept or decline them.
 * Nothing is used by the Curator until the teacher accepts it (D22).
 */
export function SourcesStep({ contextId, report, opened, onJob }: {
  contextId: string; report: ExportReport | null; opened: JobView | null; onJob(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [discovery, setDiscovery] = useState<JobView | null>(null);
  const [preparation, setPreparation] = useState<JobView | null>(null);

  useEffect(() => {
    if (opened?.job.kind === DISCOVERY) {
      setDiscovery(opened);
      setPreparation(null);
    } else if (opened?.job.kind === PREPARATION) setPreparation(opened);
  }, [opened]);

  const followDiscovery = useCallback((job: JobView) => { setDiscovery(job); onJob(job); }, [onJob]);
  const followPreparation = useCallback((job: JobView) => { setPreparation(job); onJob(job); }, [onJob]);
  useFollowedJob(contextId, discovery, followDiscovery);
  useFollowedJob(contextId, preparation, followPreparation);

  const discovering = discovery !== null && (discovery.status === 'QUEUED' || discovery.status === 'RUNNING');
  const preparing = preparation !== null && (preparation.status === 'QUEUED' || preparation.status === 'RUNNING');
  const reviewable = preparation !== null && ['AWAITING_CHOICE', 'ACCEPTED', 'DECLINED'].includes(preparation.status);

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.sources.heading')}</h2>
      <p>{t('build.sources.intro')}</p>
      <DiscoveryForm contextId={contextId} busyJob={discovering}
        onQueued={(job) => { setPreparation(null); followDiscovery(job); }} />
      {discovery ? <SourceJobStatus job={discovery} /> : null}
      {discovery?.status === 'COMPLETED' ? (
        <ExcerptPicker contextId={contextId} job={discovery} report={report} busyJob={preparing}
          onQueued={followPreparation} />
      ) : null}
      {preparation ? <SourceJobStatus job={preparation} /> : null}
      {reviewable ? <PreparationReview contextId={contextId} job={preparation} onJob={followPreparation} /> : null}
    </section>
  );
}
