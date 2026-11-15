"""Diagnostic for a possible cause of the historical 503, not attribution.

Use a random key; never lock a demo station or change production lock policy.
"""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.infrastructure.db import Database, advisory_lock


def test_advisory_lock_contention_is_database_scoped_not_search_path_scoped(environment):
    # The standard `client` fixture intentionally shares ONE connection with
    # savepoints. It cannot demonstrate cross-process lock contention.
    db = Database(environment['settings'])
    key = 'phase8a-diagnostic:' + str(uuid4())
    with db.sessions() as holder, db.sessions() as contender:
        assert holder.scalar(text('SELECT pg_backend_pid()')) != contender.scalar(text('SELECT pg_backend_pid()'))
        advisory_lock(holder, key)
        contender.execute(text('SET LOCAL search_path TO pg_catalog'))
        contender.execute(text("SET LOCAL lock_timeout TO '100ms'"))
        with pytest.raises(OperationalError) as caught:
            advisory_lock(contender, key)
        assert caught.value.orig.sqlstate == '55P03'
        contender.rollback()
        holder.rollback()
        advisory_lock(contender, key)
        assert contender.scalar(text('SELECT 1')) == 1
        contender.rollback()
    db.engine.dispose()
