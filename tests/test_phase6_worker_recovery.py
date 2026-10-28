"""P6-A03 recovery, fail-closed retry budget and durable payment dispatch."""
import os
import sys
import subprocess
import time
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from psycopg.errors import LockNotAvailable, QueryCanceled, UndefinedTable
from fastapi.testclient import TestClient

from app.config import ROOT
from app.application import assets
from app.application.identity import utcnow
from app.workers import payment as worker, retry
from test_phase5 import race_environment, login
from test_phase6 import book, consent, payment, callback, counts, private_keys, outcome
from test_phase6_blocker_fix import audit_count
from test_phase4 import DEVICE, row, packet, send


@pytest.mark.parametrize('cause', [QueryCanceled, UndefinedTable])
def test_non_lock_database_error_is_not_retried(monkeypatch, cause):
    sleeps = []
    monkeypatch.setattr(retry.time, 'sleep', sleeps.append)
    def fail(): raise OperationalError('hidden', {}, cause('failure'))
    with pytest.raises(OperationalError): retry.run_tick(fail, 'test')
    assert not sleeps


def test_bounded_backoff_and_no_sensitive_log(monkeypatch, caplog):
    sleeps = []; calls = []
    monkeypatch.setattr(retry.time, 'sleep', sleeps.append)
    def fail():
        calls.append(1)
        raise OperationalError('sensitive-sql', {}, LockNotAvailable('private-payload'))
    with pytest.raises(OperationalError): retry.run_tick(fail, 'test')
    assert len(calls) == 3 and sleeps == [1.0, 2.0]
    assert 'worker_lock_exhausted' in caplog.text
    assert 'sensitive-sql' not in caplog.text and 'private-payload' not in caplog.text


def test_payment_and_device_processes_recover_same_schema(race_environment, tmp_path):
    env = race_environment; processes = []; handles = []
    try:
        with TestClient(create_app(env['settings'])) as http:
            actor = login(http, env); swap = book(http, env, actor, env['seed_db'])
            assert consent(http, actor, swap).status_code == 202
            p = payment(http, actor, swap); assert callback(http, p).status_code == 202
            db = env['seed_db']; device = row(http, 'devices', DEVICE)
            event = packet(boot=device['boot_id'], seq=device['last_seq'] + 1)
            assert send(http, env, event, False).status_code == 202
            paths = []
            with db.sessions.begin() as holder:
                assets.station_lock(holder, db, UUID(swap['station_id']))
                for module in ('payment', 'device'):
                    path = tmp_path/(module + '.log'); paths.append(path)
                    log = path.open('w', encoding='utf-8'); handles.append(log)
                    processes.append(subprocess.Popen([sys.executable, '-m', 'app.workers.'+module, '--once'],
                        cwd=ROOT, env=dict(os.environ, DATABASE_SCHEMA=env['settings'].schema),
                        stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
                deadline = time.monotonic() + 15
                while not all('worker_lock_retry' in x.read_text(encoding='utf-8') for x in paths):
                    assert all(p.poll() is None for p in processes)
                    assert time.monotonic() < deadline, 'Workers must report real lock timeout'
                    time.sleep(.05)
                assert payment(http, actor, swap)['state'] == 'CREATED'
                assert row(http, 'device_events', UUID(event['event_id']))['processed_at'] is None
            # Release same-schema holder. No process restart or synthetic DB change.
            for process in processes: assert process.wait(timeout=30) == 0
            assert all('worker_lock_recovered' in x.read_text(encoding='utf-8') for x in paths)
            assert payment(http, actor, swap)['state'] == 'SUCCEEDED'
            assert row(http, 'device_events', UUID(event['event_id']))['accepted'] is True
            assert audit_count(db, p['id'], 'PAYMENT_SUCCEEDED') == 1
            assert counts(db)['holds'] == 3
            # Phase7 now schedules OPEN_RETURN after verified settlement. Depending
            # on which --once worker acquires the station lock first, it is either
            # queued here or left for the next tick. Neither order proves custody.
            with db.sessions() as s:
                commands = list(s.execute(select(db.table('device_commands'))).mappings())
            assert len(commands) <= 1
            for command in commands:
                assert command['swap_id'] == UUID(swap['id']) and command['kind'] == 'OPEN_RETURN'
                assert command['state'] == 'QUEUED' and command['evidence_event_id'] is None
            current = row(http, 'swap_transactions', UUID(swap['id']))
            assert current['state'] == 'AWAITING_RETURN'
            assert current['return_observed_at'] is None and current['pickup_observed_at'] is None
            assert row(http, 'batteries', current['old_battery_id'])['holder_user_id'] == current['customer_id']
            assert row(http, 'batteries', current['new_battery_id'])['compartment_id'] == current['supply_compartment_id']
            assert callback(http, p).status_code == 202
            worker.process_events(db)
            assert audit_count(db, p['id'], 'PAYMENT_SUCCEEDED') == 1
            with db.sessions() as s:
                assert all(s.scalars(select(db.table('payment_events').c.processed_at)))
    finally:
        for process in processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=10)
        for handle in handles: handle.close()


from app.main import create_app


def test_post_dispatch_lock_failure_queries_same_key(race_environment, monkeypatch):
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor = login(http, env); swap = book(http, env, actor, env['seed_db'])
        assert consent(http, actor, swap).status_code == 202
        db = env['seed_db']; p = payment(http, actor, swap); calls = []
        holder = db.sessions(); transaction = None
        def transport(payload, query=False):
            nonlocal transaction
            calls.append((query, payload['provider_key']))
            if not query:
                transaction = holder.begin()
                assets.station_lock(holder, db, UUID(swap['station_id']))
            return outcome(payload, query)
        def backoff(delay):
            # Reaching backoff proves failed settlement transaction was unwound.
            assert payment(http, actor, swap)['state'] == 'PENDING'
            assert audit_count(db, p['id'], 'PAYMENT_SUCCEEDED') == 0
            transaction.rollback(); holder.close()
        monkeypatch.setattr(retry.time, 'sleep', backoff)
        try:
            retry.run_tick(lambda: worker.tick(db, transport=transport), 'payment')
            # Claim deadline remains durable; no POST while waiting for query deadline.
            assert calls == [(False, p['provider_key'])]
            box = db.table('outbox_messages')
            with db.sessions() as s: due = s.scalar(select(box.c.next_attempt_at))
            worker.tick(db, now=due, transport=transport)
            assert calls == [(False, p['provider_key']), (True, p['provider_key'])]
            assert payment(http, actor, swap)['state'] == 'SUCCEEDED'
            assert audit_count(db, p['id'], 'PAYMENT_SUCCEEDED') == 1
            assert counts(db)['holds'] == 3 and counts(db)['device_commands'] == 0
        finally:
            holder.close()
