"""Module ``courses``: a teacher creates a course from the studio (S09a).

A course is a new context in PREPARATION/DRAFT with a trusted policy of its
own. The operator's course template (``ALM_COURSE_TEMPLATE``, read on every
request, never written by the API) names the subjects who may create courses
and the source scopes a new course receives. The API writes the new course's
policy as a new file in ``ALM_POLICY_DIR``: the creator, alone, administers
that context and nothing else. An installed policy file is never changed.

The same request again returns the same course, and completes a creation
interrupted after its policy file was written. An id that a context or an
installed policy already uses is a 409.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from starlette.exceptions import HTTPException

from learning.contracts import EntityRef, Record, Text
from learning.policies import AuthorizationError, ScopeGrant, SubjectGrant, TrustedPolicy
from services.api_common.auth import Principal, csrf_protected
from services.api_common.errors import error_responses
from services.api_common.registry import ApiModule, ConfigurationError


COURSE_ID = r'^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$'
CREATOR_ROLES = ['ADMINISTRATOR', 'CONTENT_RESPONSIBLE']
CREATOR_ACTIONS = ['read', 'bootstrap', 'propose', 'decide', 'apply', 'interact']
TAKEN = 'A course or a policy already uses this id'


class CourseTemplate(Record):
    """Installed by an operator: who may create courses, and the source scopes (name → sources) of a new course."""
    format: Literal[1]
    creators: tuple[Text, ...] = Field(min_length=1)
    source_scopes: dict[Text, tuple[Text, ...]] = Field(default_factory=dict)


class CourseRequest(Record):
    context_id: str = Field(pattern=COURSE_ID, description='The new course id: lowercase letters, digits and hyphens')


class CourseView(Record):
    context_id: Text
    policy_ref: EntityRef


def load_template(path: Path) -> CourseTemplate:
    try:
        return CourseTemplate.model_validate_json(Path(path).read_bytes())
    except (ValueError, OSError):
        raise ConfigurationError('ALM_COURSE_TEMPLATE is not a valid course template') from None


def course_policy(template: CourseTemplate, context_id: str, creator: str) -> TrustedPolicy:
    """The policy of a new course: the creator administers this context only, with the template's source scopes."""
    return TrustedPolicy(
        policy_ref=EntityRef(type='PolicySet', id='course:' + context_id, version='1'),
        subjects={creator: SubjectGrant(roles=CREATOR_ROLES, actions={context_id: CREATOR_ACTIONS})},
        scopes={name: ScopeGrant(contexts=[context_id], subjects=[creator], sources=list(sources))
                for name, sources in template.source_scopes.items()})


def _names(policy: TrustedPolicy, context_id: str) -> bool:
    return (any(context_id in grant.actions for grant in policy.subjects.values()) or
            any(context_id in scope.contexts for scope in policy.scopes.values()))


def configure(app, settings) -> None:
    app.state.course_template = settings.course_template


def course_writer(response: Response, principal: Principal = Depends(csrf_protected)) -> Principal:
    response.headers['Cache-Control'] = 'no-store'
    return principal


router = APIRouter(tags=['courses'])


@router.post('/courses', response_model=CourseView, responses=error_responses(401, 403, 409, 422, 500),
             summary='Create a course: a new PREPARATION/DRAFT context with a new policy for its creator')
def create(body: CourseRequest, request: Request, principal: Principal = Depends(course_writer)):
    template = load_template(request.app.state.course_template)
    if principal.subject_key not in template.creators:
        raise AuthorizationError('Course creation is not authorized')
    contexts = request.app.state.contexts
    policy = course_policy(template, body.context_id, principal.subject_key)
    current = contexts.policy_of(body.context_id)
    if current is None:
        others = [p for p in contexts.policies.installed()
                  if p != policy and (p.policy_ref == policy.policy_ref or _names(p, body.context_id))]
        if others:
            raise HTTPException(409, TAKEN)
        contexts.policies.install(f'course-{body.context_id}-1.json', policy)
        try:
            contexts.bootstrap(body.context_id, principal.subject_key, policy)
        except ValueError:
            # The same request, running at the same time, created the context first.
            if contexts.policy_of(body.context_id) != policy.policy_ref:
                raise
    elif current != policy.policy_ref or contexts.policies.find(current) != policy:
        raise HTTPException(409, TAKEN)
    return CourseView(context_id=body.context_id, policy_ref=policy.policy_ref)


MODULE = ApiModule('courses', router)
