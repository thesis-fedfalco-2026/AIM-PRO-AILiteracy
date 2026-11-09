"""Run store-backed test cases on SQLite and, when configured, on PostgreSQL.

Decorate a ``TestCase`` with :func:`on_both_backends` to register a PostgreSQL
copy of it next to the original. The copy runs only when ``ALM_TEST_POSTGRES_URL``
names a local test database (a ``postgresql://`` URL); each test then works in
its own new schema, dropped at cleanup. Without the variable the copies are
reported as skipped, so the offline suite needs no database service.
"""

from functools import wraps
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4


POSTGRES_URL_ENV = 'ALM_TEST_POSTGRES_URL'
NETWORK_TARGETS = ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo')


def postgres_url():
    return os.environ.get(POSTGRES_URL_ENV) or None


def backend(case):
    return getattr(case, 'store_backend', 'sqlite')


def on_both_backends(cls):
    """Register ``<Name>PostgreSQL``, the same tests on a PostgreSQL store, in the class's module."""
    name = cls.__name__ + 'PostgreSQL'
    variant = type(name, (cls,), {'store_backend': 'postgresql', '__module__': cls.__module__,
                                  '__qualname__': name, '__doc__': cls.__doc__})
    variant = unittest.skipUnless(postgres_url(), POSTGRES_URL_ENV + ' is not set')(variant)
    setattr(sys.modules[cls.__module__], name, variant)
    return cls


def sqlite_only(test):
    """Skip a test of SQLite files, pragmas or the v1 migration on the other backends."""
    @wraps(test)
    def run(case, *args, **kwargs):
        if backend(case) != 'sqlite':
            case.skipTest('SQLite-specific behaviour')
        return test(case, *args, **kwargs)
    return run


def new_store_location(case, directory, name):
    """A location for a new store of this test: a file in ``directory`` or a new PostgreSQL schema."""
    if backend(case) == 'sqlite':
        return Path(directory) / name
    schema = 'alm_test_' + uuid4().hex
    _administer(f'CREATE SCHEMA "{schema}"')
    case.addCleanup(_administer, f'DROP SCHEMA "{schema}" CASCADE')
    return with_search_path(postgres_url(), schema)


def with_search_path(url, schema):
    """The URL with ``schema`` first on the search path, so the store creates its tables there."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query['options'] = (query.get('options', '') + f' -csearch_path={schema}').strip()
    return urlunsplit(parts._replace(query=urlencode(query, quote_via=quote)))


def _administer(statement):
    import psycopg
    with psycopg.connect(postgres_url(), autocommit=True) as connection:
        connection.execute("SET lock_timeout = '5s'")
        connection.execute(statement)


def postgres_endpoint():
    parts = urlsplit(postgres_url())
    return parts.hostname, str(parts.port or 5432)


def block_network(case, message, *targets):
    """Fail every socket, DNS and extra target call during the test.

    The PostgreSQL copy of a case may resolve only the host and port of
    ``ALM_TEST_POSTGRES_URL``; libpq then connects to that service itself.
    """
    allowed = postgres_endpoint() if backend(case) == 'postgresql' else None
    resolve = socket.getaddrinfo
    forbidden = []

    def guard(target):
        def call(*args, **kwargs):
            if target == 'socket.getaddrinfo' and allowed and _endpoint(*args, **kwargs) == allowed:
                return resolve(*args, **kwargs)
            forbidden.append(target)
            raise AssertionError(message)
        return call

    for target in (*NETWORK_TARGETS, *targets):
        blocker = patch(target, side_effect=guard(target))
        blocker.start()
        case.addCleanup(blocker.stop)
    case.addCleanup(lambda: case.assertEqual(forbidden, [], message))


def _endpoint(host, port=None, *_, **__):
    return host, None if port is None else str(port)
