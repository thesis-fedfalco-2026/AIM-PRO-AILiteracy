"""One ``LearningService`` per request and context, with the context's trusted policy (D10).

A configured directory holds trusted policy files. For each request the file
whose ``policy_ref`` equals the context's ``policies`` reference is the policy;
no match makes the context unavailable. The directory is read on every
request, so an operator installs an approved policy preview by copying the
file, without a restart. A missing context and a missing policy give the same
answer, so the response does not reveal which contexts exist.

The API writes one kind of policy file: the policy of a course created from the
studio (module ``courses``, S09a). It is a new file, written whole or not at
all; an installed file is never changed or removed.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from fastapi import Depends, Request, Response

from learning.contracts import EntityRef
from learning.metamodel import load_contract
from learning.policies import TrustedPolicy
from learning.service import LearningService
from learning.store import LearningStore, StateConflict, resolve_location
from services.api_common.auth import Principal, csrf_protected, current_principal
from services.api_common.errors import ContextUnavailable, error_responses
from services.api_common.registry import ConfigurationError


READ_ERRORS = error_responses(401, 403, 404, 409, 422, 500)
"""What a context read can answer besides 200; 404 includes an unavailable context."""

WRITE_ERRORS = error_responses(401, 403, 404, 409, 422, 500)
"""What a context write can answer besides 200; 403 includes a missing CSRF token, 409 a stale state."""


class PolicyDirectoryError(RuntimeError):
    """The trusted policy directory cannot be read safely; never shown to clients."""


class PolicyDirectory:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_dir():
            raise ConfigurationError('ALM_POLICY_DIR is not a directory')

    def installed(self) -> list[TrustedPolicy]:
        """Every installed policy; every ``*.json`` file must be valid."""
        found = []
        for file in sorted(self.path.glob('*.json')):
            try:
                policy = TrustedPolicy.model_validate_json(file.read_bytes())
            except (ValueError, OSError):
                raise PolicyDirectoryError(f'Trusted policy file is invalid: {file.name}') from None
            if policy.policy_ref.type != 'PolicySet':
                raise PolicyDirectoryError(f'Trusted policy file is invalid: {file.name}')
            found.append(policy)
        return found

    def find(self, ref: EntityRef) -> TrustedPolicy | None:
        """The policy whose ``policy_ref`` is exactly ``ref``."""
        found = [policy for policy in self.installed() if policy.policy_ref == ref]
        if len(found) > 1:
            raise PolicyDirectoryError('A policy reference is installed in more than one file')
        return found[0] if found else None

    def install(self, name: str, policy: TrustedPolicy) -> None:
        """Install ``policy`` as the new file ``name``; a file already there is kept only if it is identical.

        The bytes go to a temporary name that no reader lists, then are linked to
        ``name``: the link fails if ``name`` exists, so an installed file is never
        replaced and a reader never sees a partial file. Any other file under
        ``name`` is a :class:`StateConflict`.
        """
        content = (policy.model_dump_json(indent=2) + '\n').encode('utf-8')
        target = self.path / name
        if target.parent != self.path or target.suffix != '.json':
            raise ValueError('Invalid policy file name')
        temporary = self.path / f'.{name}.{uuid4().hex}.tmp'
        try:
            with temporary.open('xb') as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != content:
                raise StateConflict('A different policy file is installed under this name') from None
        finally:
            temporary.unlink(missing_ok=True)


def _no_agents():
    raise RuntimeError('The API never builds agents; generation runs in the agent job worker')


class ContextServices:
    def __init__(self, store: str, policies: PolicyDirectory):
        backend, path = resolve_location(store)
        if backend == 'sqlite' and not Path(path).is_file():
            # LearningStore would create a new database: never on a read path.
            raise ConfigurationError('ALM_STORE names no existing SQLite database')
        self.store, self.policies, self.contract = store, policies, load_contract()

    def policy_of(self, context_id: str) -> EntityRef | None:
        """The policy reference of an existing context; ``None`` when there is no such context."""
        with LearningStore(self.store) as store:
            if not store.has_context(context_id):
                return None
            return EntityRef.model_validate(store.read_context(context_id).fields['policies'])

    def bootstrap(self, context_id: str, subject_key: str, policy: TrustedPolicy):
        """Create the context with ``policy``, as the CLI ``bootstrap`` does; returns its root."""
        with LearningStore(self.store) as store:
            return LearningService(store, self.contract, policy, _no_agents).bootstrap(context_id, subject_key)

    @contextmanager
    def open(self, context_id: str) -> Iterator[LearningService]:
        """Open the store, resolve the context's policy and close the store when done.

        Use it inside the route function: a SQLite connection serves only the
        thread that opened it.
        """
        with LearningStore(self.store) as store:
            if not store.has_context(context_id):
                raise ContextUnavailable('no such context')
            reference = EntityRef.model_validate(store.read_context(context_id).fields['policies'])
            policy = self.policies.find(reference)
            if policy is None:
                raise ContextUnavailable('policy not installed')
            yield LearningService(store, self.contract, policy, _no_agents)


def open_context(request: Request, context_id: str):
    return request.app.state.contexts.open(context_id)


def context_reader(request: Request, response: Response) -> Principal:
    """The principal of a context read; the response holds private content and is never cached."""
    response.headers['Cache-Control'] = 'no-store'
    return current_principal(request)


def context_writer(response: Response, principal: Principal = Depends(csrf_protected)) -> Principal:
    """The principal of a context write: CSRF-protected, and the response is never cached."""
    response.headers['Cache-Control'] = 'no-store'
    return principal
