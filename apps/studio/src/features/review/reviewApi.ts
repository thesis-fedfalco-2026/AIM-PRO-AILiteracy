import type { AuthoringClient, components } from '@alm/api-client';

type Schemas = components['schemas'];

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

/** An ALM record as the API returns it; the API sends JSON, so `fields` are JSON values. */
export type Entity = Omit<Schemas['Entity'], 'fields'> & { fields: Record<string, JsonValue> };
export type EntityRef = Schemas['EntityRef'];
export type Finding = Schemas['Finding'];
export type DecisionKind = Schemas['DecisionRequest']['decision'];
export type SyllabusProposalView = Schemas['SyllabusProposalView'];
export type SyllabusDraft = Schemas['SyllabusDraft-Input'];

export interface PendingProposal {
  proposal: Entity;
  candidates: Entity[];
  /** The key of the payload shown; a decision sends it back (S06). */
  reviewPayloadKey: string;
}

export interface Inbox {
  context: Entity;
  /** The latest revision of every record the subject may see. */
  entities: Entity[];
  findings: Finding[];
  /** Newest first, as the API lists them. */
  pending: PendingProposal[];
}

/**
 * Why a review request did not succeed, from the API status:
 * `conflict` (409: reload and review again), `refused` (422: the core refused, see
 * `detail`), `forbidden` (403), `unavailable` (404: no such context or its policy
 * is not installed), `signed-out` (401) and `failed` (anything else, or no answer).
 */
export type ReviewFailure = 'conflict' | 'refused' | 'forbidden' | 'unavailable' | 'signed-out' | 'failed';

export class ReviewError extends Error {
  constructor(readonly reason: ReviewFailure, readonly status: number | null, readonly detail: string | null = null) {
    super(`Review request failed: ${reason}${status === null ? '' : ` (${status})`}`);
    this.name = 'ReviewError';
  }
}

export interface ReviewApi {
  /** The context summary and the pending proposals, read together. */
  inbox(contextId: string): Promise<Inbox>;
  /** Record a decision on the exact revision and payload the reviewer saw; returns the `HumanDecision`. */
  decide(contextId: string, csrfToken: string, decision: {
    target: EntityRef; decision: DecisionKind; reason: string; reviewPayloadKey: string;
  }): Promise<Entity>;
  /** Apply an approved proposal; the same `operationId` replays the same `StateChange`. */
  apply(contextId: string, csrfToken: string, proposal: EntityRef, operationId: string): Promise<Entity>;
  /** One proposal with its candidates, whatever its status (S09c2). */
  proposal(contextId: string, proposalId: string): Promise<PendingProposal>;
  /** A syllabus proposal with its texts, compared with the proposal it refines and the applied syllabus (S09b). */
  syllabusProposal(contextId: string, proposalId: string): Promise<SyllabusProposalView>;
  /** Propose the teacher's own syllabus in place of a syllabus proposal; the same request id replays it. */
  editSyllabus(contextId: string, csrfToken: string, edit: {
    requestId: string; proposalId: string; draft: SyllabusDraft;
  }): Promise<EntityRef>;
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

const asEntity = (entity: Schemas['Entity']) => entity as Entity;

export function createReviewApi(client: AuthoringClient): ReviewApi {
  return {
    async inbox(contextId) {
      const path = { context_id: contextId };
      const [summary, pending] = await Promise.all([
        settle(() => client.GET('/contexts/{context_id}', { params: { path } })),
        settle(() => client.GET('/contexts/{context_id}/pending-proposals', { params: { path } })),
      ]);
      return {
        context: asEntity(summary.context),
        entities: summary.entities.map(asEntity),
        findings: summary.findings,
        pending: pending.proposals.map((item) => ({
          proposal: asEntity(item.proposal),
          candidates: item.candidates.map(asEntity),
          reviewPayloadKey: item.review_payload_key,
        })),
      };
    },

    async decide(contextId, csrfToken, { target, decision, reason, reviewPayloadKey }) {
      return asEntity(await settle(() => client.POST('/contexts/{context_id}/decisions', {
        params: { path: { context_id: contextId } },
        headers: { 'X-CSRF-Token': csrfToken },
        body: { target, decision, reason, review_payload_key: reviewPayloadKey },
      })));
    },

    async apply(contextId, csrfToken, proposal, operationId) {
      return asEntity(await settle(() => client.POST('/contexts/{context_id}/applications', {
        params: { path: { context_id: contextId } },
        headers: { 'X-CSRF-Token': csrfToken },
        body: { proposal, operation_id: operationId },
      })));
    },

    async proposal(contextId, proposalId) {
      const item = await settle(() => client.GET('/contexts/{context_id}/proposals/{proposal_id}', {
        params: { path: { context_id: contextId, proposal_id: proposalId } },
      }));
      return { proposal: asEntity(item.proposal), candidates: item.candidates.map(asEntity),
        reviewPayloadKey: item.review_payload_key };
    },

    async syllabusProposal(contextId, proposalId) {
      return settle(() => client.GET('/contexts/{context_id}/syllabus-proposals/{proposal_id}', {
        params: { path: { context_id: contextId, proposal_id: proposalId } },
      }));
    },

    async editSyllabus(contextId, csrfToken, { requestId, proposalId, draft }) {
      const edited = await settle(() => client.POST('/contexts/{context_id}/syllabus-edits', {
        params: { path: { context_id: contextId } },
        headers: { 'X-CSRF-Token': csrfToken },
        body: { request_id: requestId, proposal: proposalId, draft },
      }));
      return edited.proposal;
    },
  };
}
