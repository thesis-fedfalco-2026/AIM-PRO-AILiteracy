import type { RouteObject } from 'react-router';
import { useParams } from 'react-router';

import { CoursePage } from '../course/CoursePage';
import { ProposalPage } from './ProposalPage';
import { ReviewInboxPage } from './ReviewInboxPage';

// A new context or proposal is a new page: its state never carries over (key).
function InboxRoute() {
  const { contextId = '' } = useParams();
  return <ReviewInboxPage key={contextId} contextId={contextId} />;
}

function CourseRoute() {
  const { contextId = '' } = useParams();
  return <CoursePage key={contextId} contextId={contextId} />;
}

function ProposalRoute() {
  const { contextId = '', proposalId = '' } = useParams();
  return <ProposalPage key={`${contextId}/${proposalId}`} contextId={contextId} proposalId={proposalId} />;
}

export const reviewRoutes: RouteObject[] = [
  { path: 'contexts/:contextId/course', element: <CourseRoute /> },
  { path: 'contexts/:contextId/review', element: <InboxRoute /> },
  { path: 'contexts/:contextId/review/:proposalId', element: <ProposalRoute /> },
];
