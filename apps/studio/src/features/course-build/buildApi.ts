import type { AuthoringClient, components } from '@alm/api-client';

import { ReviewError } from '../review/reviewApi';
import type { EntityRef, ReviewFailure } from '../review/reviewApi';

type Schemas = components['schemas'];

export type CourseView = Schemas['CourseView'];
export type ExportReport = Schemas['ExportReport'];
export type JobView = Schemas['JobView'];
export type JobStatus = JobView['status'];
export type ProjectProposal = Schemas['ProjectProposal'];
export type SourceDiscovery = Schemas['SourceDiscoveryView'];
export type SourcePreparation = Schemas['SourcePreparationView'];
export type SourcePlan = Schemas['SourcePlan'];
export type ExportTargets = Schemas['ExportTargets'];
export type CoverageRequirement = Schemas['CoverageRequirement'];
export type AimproExport = ExportReport['export'];
export type SyllabusReviews = Schemas['SyllabusReviews'];
export type SyllabusAttempt = SyllabusReviews['attempts'][number];

/** The statuses after which a job never changes again. */
export const FINAL_STATUSES: readonly JobStatus[] = [
  'PROPOSED', 'REJECTED', 'FAILED', 'ABANDONED', 'COMPLETED', 'ACCEPTED', 'DECLINED',
];
/** The statuses after which the worker is done with a job: final, or awaiting the teacher's choice. */
export const ENDED_STATUSES: readonly JobStatus[] = [...FINAL_STATUSES, 'AWAITING_CHOICE'];

export const DISCOVERY = 'discover-aimpro-syllabus-sources';
export const PREPARATION = 'prepare-aimpro-syllabus-sources';
export const CURATOR = 'generate-aimpro-syllabus';
export const REVISION = 'revise-aimpro-syllabus';

/** The Curator grounded by a search query, or by prepared sources that the teacher accepted. */
export type CuratorCommand = {
  export: AimproExport;
  scenario: string;
  competencies: string;
  sourceScope: string;
} & ({ query: string } | { preparedSources: string });

export interface PreparationCommand {
  export: AimproExport;
  scenario: string;
  competencies: string;
  plan: SourcePlan;
}

/** The steps that start a course: create it, upload its AIM-PRO model, draft its syllabus, initialize its project. */
export interface BuildApi {
  /** A new course: a new context and policy for the signed-in creator; the same id again returns the same course. */
  createCourse(csrfToken: string, contextId: string): Promise<CourseView>;
  /** Check the file and store it unchanged; a refused file is a `refused` error whose detail names the reason. */
  uploadExport(contextId: string, csrfToken: string, file: Blob, scenario: string, competencies: string): Promise<ExportReport>;
  /** Queue the Curator on an uploaded export; the same request id returns the same job. */
  queueCurator(contextId: string, csrfToken: string, requestId: string, command: CuratorCommand): Promise<JobView>;
  /** Queue the Curator's revision of a syllabus proposal on which the teacher requested a revision. */
  queueRevision(contextId: string, csrfToken: string, requestId: string, proposalId: string): Promise<JobView>;
  readJob(contextId: string, requestId: string): Promise<JobView>;
  /** The jobs of the course, newest first. */
  listJobs(contextId: string): Promise<JobView[]>;
  /** Queue a search of the course's sources; nothing is selected or used yet. */
  queueDiscovery(contextId: string, csrfToken: string, requestId: string,
    command: { sourceScope: string; queries: { query: string; k: number }[] }): Promise<JobView>;
  readDiscovery(contextId: string, requestId: string): Promise<SourceDiscovery>;
  /** Queue the preparation of the excerpts a teacher picked; it then awaits the teacher's choice. */
  queuePreparation(contextId: string, csrfToken: string, requestId: string, command: PreparationCommand): Promise<JobView>;
  readPreparation(contextId: string, requestId: string): Promise<SourcePreparation>;
  /** How the review agent judged each draft of an ended Curator job, first to last. */
  readSyllabusReviews(contextId: string, requestId: string): Promise<SyllabusReviews>;
  /** Accept or decline prepared sources; only accepted sources ground a Curator job. */
  chooseSources(contextId: string, csrfToken: string, requestId: string, choice: 'ACCEPTED' | 'DECLINED'): Promise<JobView>;
  /** The learning targets and practices of an uploaded export, for coverage requirements. */
  exportTargets(contextId: string, exported: AimproExport, scenario: string, competencies: string): Promise<ExportTargets>;
  /** The exact approved syllabus of the course's current outline. */
  approvedSyllabus(contextId: string, design: EntityRef): Promise<EntityRef>;
  /** Propose a project from that syllabus; the same request id replays the same proposal. */
  initializeProject(contextId: string, csrfToken: string, command: {
    requestId: string; projectId: string; syllabus: EntityRef; baseContext: EntityRef;
  }): Promise<ProjectProposal>;
}

const REASONS: Record<number, ReviewFailure> = {
  401: 'signed-out', 403: 'forbidden', 404: 'unavailable', 409: 'conflict', 422: 'refused',
};

type Answer<T> = { data?: T; error?: Schemas['ErrorBody']; response: Response };

async function settle<T>(call: () => Promise<Answer<T>>): Promise<T> {
  let answer;
  try {
    answer = await call();
  } catch {
    throw new ReviewError('failed', null);
  }
  const { data, error, response } = answer;
  if (data !== undefined && response.ok) return data;
  const detail = typeof error?.detail === 'string' ? error.detail : null;
  throw new ReviewError(REASONS[response.status] ?? 'failed', response.status, detail);
}

export function createBuildApi(client: AuthoringClient): BuildApi {
  const writing = (csrfToken: string) => ({ 'X-CSRF-Token': csrfToken });
  return {
    async createCourse(csrfToken, contextId) {
      return settle(() => client.POST('/courses', { headers: writing(csrfToken), body: { context_id: contextId } }));
    },

    async uploadExport(contextId, csrfToken, file, scenario, competencies) {
      return settle(() => client.POST('/contexts/{context_id}/aimpro-exports', {
        params: { path: { context_id: contextId }, query: { scenario, competencies } },
        headers: { ...writing(csrfToken), 'Content-Type': 'application/octet-stream' },
        // The file goes as it is: the API stores these exact bytes.
        body: file as unknown as string,
        bodySerializer: (body: unknown) => body as Blob,
      }));
    },

    async queueCurator(contextId, csrfToken, requestId, command) {
      const grounding = 'query' in command ? { query: command.query } : { prepared_sources: command.preparedSources };
      return settle(() => client.POST('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: {
          request_id: requestId,
          job: {
            kind: CURATOR, project: command.export, source_scope: command.sourceScope, ...grounding, k: 5,
            scenario: command.scenario, competencies: command.competencies,
          },
        },
      }));
    },

    async queueRevision(contextId, csrfToken, requestId, proposalId) {
      return settle(() => client.POST('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: { request_id: requestId, job: { kind: REVISION, proposal: proposalId } },
      }));
    },

    async readJob(contextId, requestId) {
      return settle(() => client.GET('/contexts/{context_id}/jobs/{request_id}', {
        params: { path: { context_id: contextId, request_id: requestId } },
      }));
    },

    async listJobs(contextId) {
      const listed = await settle(() => client.GET('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
      }));
      return listed.jobs;
    },

    async queueDiscovery(contextId, csrfToken, requestId, { sourceScope, queries }) {
      return settle(() => client.POST('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: { request_id: requestId, job: {
          kind: DISCOVERY,
          discovery: { format: 'aimpro-source-discovery', format_version: 1, source_scope: sourceScope, queries },
        } },
      }));
    },

    async readDiscovery(contextId, requestId) {
      return settle(() => client.GET('/contexts/{context_id}/source-discoveries/{request_id}', {
        params: { path: { context_id: contextId, request_id: requestId } },
      }));
    },

    async queuePreparation(contextId, csrfToken, requestId, command) {
      return settle(() => client.POST('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: {
          request_id: requestId,
          job: { kind: PREPARATION, project: command.export, plan: command.plan, scenario: command.scenario,
            competencies: command.competencies },
        },
      }));
    },

    async readPreparation(contextId, requestId) {
      return settle(() => client.GET('/contexts/{context_id}/source-preparations/{request_id}', {
        params: { path: { context_id: contextId, request_id: requestId } },
      }));
    },

    async readSyllabusReviews(contextId, requestId) {
      return settle(() => client.GET('/contexts/{context_id}/syllabus-reviews/{request_id}', {
        params: { path: { context_id: contextId, request_id: requestId } },
      }));
    },

    async chooseSources(contextId, csrfToken, requestId, choice) {
      return settle(() => client.POST('/contexts/{context_id}/jobs/{request_id}/choice', {
        params: { path: { context_id: contextId, request_id: requestId } },
        headers: writing(csrfToken),
        body: { choice },
      }));
    },

    async exportTargets(contextId, exported, scenario, competencies) {
      return settle(() => client.GET('/contexts/{context_id}/aimpro-exports/{sha256}/targets', {
        params: { path: { context_id: contextId, sha256: exported.sha256 }, query: { scenario, competencies } },
      }));
    },

    async approvedSyllabus(contextId, design) {
      const approved = await settle(() => client.GET('/contexts/{context_id}/designs/{design_id}/versions/{version}/syllabus', {
        params: { path: { context_id: contextId, design_id: design.id, version: design.version } },
      }));
      return approved.syllabus;
    },

    async initializeProject(contextId, csrfToken, { requestId, projectId, syllabus, baseContext }) {
      return settle(() => client.POST('/contexts/{context_id}/projects', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: { request_id: requestId, project_id: projectId, syllabus, base_context: baseContext },
      }));
    },
  };
}
