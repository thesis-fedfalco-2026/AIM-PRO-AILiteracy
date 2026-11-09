import type { AuthoringClient, components } from '@alm/api-client';

import { ReviewError } from '../review/reviewApi';
import type { EntityRef, ReviewFailure } from '../review/reviewApi';

type Schemas = components['schemas'];

export type CourseView = Schemas['CourseView'];
export type ExportReport = Schemas['ExportReport'];
export type JobView = Schemas['JobView'];
export type JobStatus = JobView['status'];
export type ProjectProposal = Schemas['ProjectProposal'];

/** The statuses after which a job never changes again. */
export const FINAL_STATUSES: readonly JobStatus[] = ['PROPOSED', 'REJECTED', 'FAILED', 'ABANDONED'];

export interface CuratorCommand {
  export: ExportReport['export'];
  scenario: string;
  competencies: string;
  sourceScope: string;
  query: string;
}

/** The steps that start a course: create it, upload its AIM-PRO model, draft its syllabus, initialize its project. */
export interface BuildApi {
  /** A new course: a new context and policy for the signed-in creator; the same id again returns the same course. */
  createCourse(csrfToken: string, contextId: string): Promise<CourseView>;
  /** Check the file and store it unchanged; a refused file is a `refused` error whose detail names the reason. */
  uploadExport(contextId: string, csrfToken: string, file: Blob, scenario: string, competencies: string): Promise<ExportReport>;
  /** Queue the Curator on an uploaded export; the same request id returns the same job. */
  queueCurator(contextId: string, csrfToken: string, requestId: string, command: CuratorCommand): Promise<JobView>;
  readJob(contextId: string, requestId: string): Promise<JobView>;
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
      return settle(() => client.POST('/contexts/{context_id}/jobs', {
        params: { path: { context_id: contextId } },
        headers: writing(csrfToken),
        body: {
          request_id: requestId,
          job: {
            kind: 'generate-aimpro-syllabus', project: command.export, source_scope: command.sourceScope,
            query: command.query, k: 5, scenario: command.scenario, competencies: command.competencies,
          },
        },
      }));
    },

    async readJob(contextId, requestId) {
      return settle(() => client.GET('/contexts/{context_id}/jobs/{request_id}', {
        params: { path: { context_id: contextId, request_id: requestId } },
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
