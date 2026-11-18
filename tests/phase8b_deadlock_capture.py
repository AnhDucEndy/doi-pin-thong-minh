"""Opt-in pytest diagnostic, never imported by production; no sensitive params."""
import json
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.config import ROOT

captured = []
lock_samples = []
lock_counts = {}


def locked(conn, cursor, statement, parameters, context, many):
    # Parameter values are deliberately omitted (never headers/authentication).
    normalized = ' '.join(statement.split())
    kind = None
    if normalized.startswith('SELECT ') and 'FROM stations ' in normalized and 'FOR ' in normalized:
        kind = 'station_no_key_update' if 'FOR NO KEY UPDATE' in normalized else 'station_other'
    elif normalized.startswith('SELECT ') and 'FROM users ' in normalized and 'FOR UPDATE' in normalized:
        kind = 'user_for_update'
    elif normalized.startswith('INSERT INTO user_station_assignments '):
        kind = 'assignment_fk_insert'
    if kind:
        lock_counts[kind] = lock_counts.get(kind, 0) + 1
        if len(lock_samples) < 80:
            lock_samples.append({'kind': kind, 'statement': normalized,
                'pid': conn.connection.driver_connection.info.backend_pid})


def failed(context):
    original = context.original_exception
    if getattr(original, 'sqlstate', None) != '40P01':
        return
    diag = original.diag
    captured.append({'sqlstate': original.sqlstate, 'primary': diag.message_primary,
        'detail': diag.message_detail, 'context': diag.context,
        'statement': context.statement, 'backend_pid': context.connection.connection.driver_connection.info.backend_pid})


def pytest_sessionstart(session):
    event.listen(Engine, 'handle_error', failed)
    event.listen(Engine, 'after_cursor_execute', locked)


def pytest_sessionfinish(session, exitstatus):
    event.remove(Engine, 'handle_error', failed)
    event.remove(Engine, 'after_cursor_execute', locked)
    (ROOT/'docs/PHASE8B_TESTS/deadlock_detail.json').write_text(json.dumps({
        'pytest_exit': int(exitstatus), 'deadlocks': captured,
        'executed_lock_counts': lock_counts, 'executed_lock_samples': lock_samples}, indent=2), encoding='utf8')
