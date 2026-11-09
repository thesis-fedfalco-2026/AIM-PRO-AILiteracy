import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { readable } from './model';
import type { Finding, JsonValue } from './reviewApi';
import { JsonText, ScrollRegion } from './parts';

const isRecord = (value: JsonValue): value is Record<string, JsonValue> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function FindingTable({ heading, findings }: { heading: string; findings: Finding[] }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <>
      <h4 id={id}>{heading}</h4>
      <ScrollRegion labelledBy={id}>
        <table className="alm-table">
          <thead>
            <tr>
              <th scope="col">{t('review.diagnostics.severity')}</th>
              <th scope="col">{t('review.diagnostics.code')}</th>
              <th scope="col">{t('review.diagnostics.target')}</th>
              <th scope="col">{t('review.diagnostics.reason')}</th>
              <th scope="col">{t('review.diagnostics.resolution')}</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding, index) => (
              <tr key={index}>
                <td>{finding.severity}</td>
                <td><code>{finding.code}</code></td>
                <td>{finding.target}</td>
                <td>{finding.reason}</td>
                <td>{finding.resolution}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </>
  );
}

/** One entry of the generator report: a list, a table of objects, or a value. */
function ReportEntry({ name, value }: { name: string; value: JsonValue }) {
  const { t } = useTranslation();
  const id = useId();
  let body;
  if (Array.isArray(value) && value.length === 0) {
    body = <p>{t('review.diagnostics.empty')}</p>;
  } else if (Array.isArray(value) && value.every(isRecord)) {
    const columns = [...new Set(value.flatMap((row) => Object.keys(row)))];
    body = (
      <ScrollRegion labelledBy={id}>
        <table className="alm-table">
          <thead>
            <tr>{columns.map((column) => <th key={column} scope="col">{readable(column)}</th>)}</tr>
          </thead>
          <tbody>
            {value.map((row, index) => (
              <tr key={index}>{columns.map((column) => <td key={column}><JsonText value={row[column]} /></td>)}</tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    );
  } else if (Array.isArray(value)) {
    body = <ul>{value.map((item, index) => <li key={index}><JsonText value={item} /></li>)}</ul>;
  } else {
    body = <JsonText value={value} />;
  }
  return (
    <>
      <h5 id={id}>{readable(name)}</h5>
      {body}
    </>
  );
}

export interface DiagnosticsProps {
  findings: Finding[];
  contextFindings: Finding[];
  report: Record<string, JsonValue> | null;
}

/** What the proposal and its context report: findings, then the generator report of the explanation. */
export function Diagnostics({ findings, contextFindings, report }: DiagnosticsProps) {
  const { t } = useTranslation();
  const entries = Object.entries(report ?? {});
  const empty = findings.length === 0 && contextFindings.length === 0 && entries.length === 0;
  return (
    <section aria-labelledby="review-diagnostics">
      <h3 id="review-diagnostics">{t('review.diagnostics.heading')}</h3>
      {empty ? <p>{t('review.diagnostics.none')}</p> : null}
      {findings.length > 0 ? <FindingTable heading={t('review.diagnostics.findings')} findings={findings} /> : null}
      {contextFindings.length > 0
        ? <FindingTable heading={t('review.diagnostics.contextFindings')} findings={contextFindings} /> : null}
      {entries.length > 0 ? (
        <>
          <h4>{t('review.diagnostics.report')}</h4>
          {entries.map(([name, value]) => <ReportEntry key={name} name={name} value={value} />)}
        </>
      ) : null}
    </section>
  );
}
