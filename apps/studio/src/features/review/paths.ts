/** Studio paths of the review module, relative to the studio base path. */
export const inboxPath = (contextId: string) => `/contexts/${encodeURIComponent(contextId)}/review`;

export const proposalPath = (contextId: string, proposalId: string) =>
  `${inboxPath(contextId)}/${encodeURIComponent(proposalId)}`;

export const coursePath = (contextId: string) => `/contexts/${encodeURIComponent(contextId)}/course`;

export const buildPath = (contextId: string) => `/contexts/${encodeURIComponent(contextId)}/build`;

export const syllabusEditPath = (contextId: string, proposalId: string) => `${proposalPath(contextId, proposalId)}/edit`;
