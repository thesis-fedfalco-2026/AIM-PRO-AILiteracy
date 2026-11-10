import type { RouteObject } from 'react-router';
import { useParams } from 'react-router';

import { BuildPage } from '../course-build/BuildPage';
import { CoursePage } from '../course/CoursePage';
import { ProposalPage } from './ProposalPage';
import { ReviewInboxPage } from './ReviewInboxPage';
import { SyllabusEditPage } from './SyllabusEditPage';

// A new context or proposal is a new page: its state never carries over (key).
function InboxRoute() {
  const { contextId = '' } = useParams();
  return <ReviewInboxPage key={contextId} contextId={contextId} />;
}

function CourseRoute() {
  const { contextId = '' } = useParams();
  return <CoursePage key={contextId} contextId={contextId} />;
}

function BuildRoute() {
  const { contextId = '' } = useParams();
  return <BuildPage key={contextId} contextId={contextId} />;
}

function ProposalRoute() {
  const { contextId = '', proposalId = '' } = useParams();
  return <ProposalPage key={`${contextId}/${proposalId}`} contextId={contextId} proposalId={proposalId} />;
}

function SyllabusEditRoute() {
  const { contextId = '', proposalId = '' } = useParams();
  return <SyllabusEditPage key={`${contextId}/${proposalId}`} contextId={contextId} proposalId={proposalId} />;
}

export const reviewRoutes: RouteObject[] = [
  { path: 'contexts/:contextId/course', element: <CourseRoute /> },
  { path: 'contexts/:contextId/build', element: <BuildRoute /> },
  { path: 'contexts/:contextId/review', element: <InboxRoute /> },
  { path: 'contexts/:contextId/review/:proposalId', element: <ProposalRoute /> },
  { path: 'contexts/:contextId/review/:proposalId/edit', element: <SyllabusEditRoute /> },
];
