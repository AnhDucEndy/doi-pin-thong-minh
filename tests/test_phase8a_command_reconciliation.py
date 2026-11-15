"""P8-REC-0.1: ledger quiescence is separate from positive custody proof.

Only the command-age fixture is aged (as in P7 deadline tests). No custody,
command outcome or evidence timestamp is updated to make settlement succeed.
Reboot/snapshot messages drive the real inbox/worker and produce UNKNOWN.
"""
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from app.application import recovery
from app.application.identity import utcnow
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import row, snapshot_packet, send
from test_phase7 import paid
from test_phase7_deadline import acknowledged
from test_phase8a_settlement import evidence, settle, physical_snapshot
from test_phase5 import race_environment


def prepare(client, environment, auth, *, ledger='EXECUTED', age=61, committed=False):
    if committed:
        from test_phase6 import book, consent, outcome
        from app.workers import payment
        actor = auth('customer')
        swap = book(client, environment, actor, environment['seed_db'])
        assert consent(client, actor, swap).status_code == 202
        payment.tick(client.app.state.db, transport=outcome)
    else:
        swap = paid(client, environment, auth)
    _, command = acknowledged(client, environment, swap, 'pickup')
    from contextlib import contextmanager
    @contextmanager
    def writer():
        if committed:
            with environment['seed_db'].sessions.begin() as session:
                yield session, environment['seed_db']
        else:
            with owner(client) as value:
                yield value
    with writer() as (session, db):
        table = db.table('device_commands')
        created = utcnow()-timedelta(seconds=age)
        session.execute(update(table).where(table.c.id == command['id']).values(
            created_at=created, expires_at=created+timedelta(seconds=15)))
    snapshot = snapshot_packet(str(uuid4()), 1)
    db = client.app.state.db
    with db.sessions() as session:
        table = db.table('device_commands')
        snapshot['payload']['command_ledger'] = [{'command_id': str(c['id']),
            'status': ledger if c['id'] == command['id'] else 'EXECUTED'} for c in
            session.execute(select(table).where(table.c.swap_id == UUID(swap['id']))).mappings()]
        slots = db.table('compartments')
        for slot in snapshot['payload']['slots']:
            current = session.execute(select(slots).where(slots.c.id == UUID(slot['compartment_id']))).mappings().one()
            slot.update(present=current['observed_present'], observed_serial=current['observed_serial'])
            if slot['compartment_id'] == swap['supply_compartment_id']:
                slot.update(present=False, observed_serial=None)
    assert send(client, environment, snapshot).status_code == 202
    assert row(client, 'device_events', UUID(snapshot['event_id']))['accepted'] is True
    assert row(client, 'device_commands', command['id'])['state'] == 'UNKNOWN'
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
    tech = auth('technician')
    case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    return swap, command, tech, case


def facts(client, swap):
    db = client.app.state.db
    with db.sessions() as session:
        holds, payment, audit, commands = [db.table(t) for t in
            ('resource_reservations', 'payments', 'audit_events', 'device_commands')]
        identity = UUID(swap['id'])
        return {
            'holds': len(session.execute(select(holds).where(holds.c.swap_id == identity, holds.c.released_at.is_(None))).all()),
            'payment': dict(session.execute(select(payment).where(payment.c.swap_id == identity)).mappings().one()),
            'audit': [dict(a) for a in session.execute(select(audit).where(audit.c.action == 'MANUAL_RECOVERY_SETTLED', audit.c.correlation_id == identity)).mappings()],
            'commands': [dict(c) for c in session.execute(select(commands).where(commands.c.swap_id == identity).order_by(commands.c.id)).mappings()],
            'pin': row(client, 'batteries', UUID(swap['new_battery_id'])),
        }


def test_executed_positive_proof_commits_once_without_repairing_command(client, environment, auth):
    swap, command, tech, case = prepare(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY')
    before = facts(client, swap)
    with client.app.state.db.sessions() as session:
        assert recovery.quiet(session, client.app.state.db, row(client, 'swap_transactions', UUID(swap['id']))) is False
    key = str(uuid4())
    result = settle(client, swap, tech, case, op, key)
    assert result.status_code == 200, result.text
    assert result.json()['new_pin_delivered'] == 'YES'
    assert settle(client, swap, tech, case, op, key).json() == result.json()
    after = facts(client, swap)
    assert after['commands'] == before['commands']
    assert after['payment'] == before['payment']
    assert after['holds'] == 0 and len(after['audit']) == 1
    assert after['audit'][0]['after_data']['reconciled_command_ids'] == [str(command['id'])]
    assert after['pin']['holder_user_id'] == demo_id('customer')


@pytest.mark.parametrize('fault', ['no_positive_proof', 'unknown_ledger', 'not_executed_conflict',
    'before_deadline', 'wrong_serial', 'boot_changed', 'stale_snapshot'])
def test_unresolved_or_conflicting_evidence_keeps_custody_payment_and_holds(client, environment, auth, fault):
    swap, command, tech, case = prepare(client, environment, auth,
        ledger={'unknown_ledger': 'UNKNOWN', 'not_executed_conflict': 'NOT_EXECUTED'}.get(fault, 'EXECUTED'),
        age=30 if fault == 'before_deadline' else 61)
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY',
        result='UNKNOWN' if fault == 'no_positive_proof' else 'OBSERVED',
        serial='WRONG-SERIAL' if fault == 'wrong_serial' else None)
    if fault == 'boot_changed':
        physical_snapshot(client, environment, swap, swap['supply_compartment_id'], boot=uuid4())
    before = facts(client, swap)
    if fault == 'stale_snapshot':
        with patch('app.application.recovery.utcnow', return_value=utcnow()+timedelta(seconds=16)):
            result = settle(client, swap, tech, case, op)
    else:
        result = settle(client, swap, tech, case, op)
    assert result.status_code in (409, 422), result.text
    assert facts(client, swap) == before
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'


def test_executed_manual_decision_rolls_back_all_writes_on_audit_error(client, environment, auth):
    swap, command, tech, case = prepare(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY')
    before = facts(client, swap)
    with patch('app.application.recovery.audit', side_effect=RuntimeError('TEST_MANUAL_AUDIT_FAILURE')):
        with pytest.raises(RuntimeError, match='TEST_MANUAL_AUDIT_FAILURE'):
            settle(client, swap, tech, case, op)
    assert facts(client, swap) == before
    assert row(client, 'recovery_operations', UUID(op['id']))['consumed_at'] is None
    assert settle(client, swap, tech, case, op).status_code == 200


def test_freshness_expires_during_ledger_read_without_partial_settlement(client, environment, auth, monkeypatch):
    swap, _, tech, case = prepare(client, environment, auth)
    case, op = evidence(client, environment, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY')
    before = facts(client, swap)
    original = recovery.quiet
    def slow_read(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(recovery, 'utcnow', lambda: clock)
        return result
    clock = utcnow()+timedelta(seconds=16)
    monkeypatch.setattr(recovery, 'quiet', slow_read)
    response = settle(client, swap, tech, case, op)
    assert response.status_code == 422 and response.json()['code'] == 'EVIDENCE_REQUIRED'
    assert facts(client, swap) == before


def test_two_backend_apps_settle_once_on_separate_postgresql_connections(race_environment):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.main import create_app
    env = race_environment
    with TestClient(create_app(env['settings'])) as first, TestClient(create_app(env['settings'])) as second:
        def auth(name):
            response = first.post('/v1/auth/login', json={'username': name, 'password': env['passwords'][name]})
            assert response.status_code == 200
            return {'Authorization': 'Bearer '+response.json()['access_token']}
        swap, _, tech, case = prepare(first, env, auth, committed=True)
        case, op = evidence(first, env, auth, swap, tech, case, purpose='VERIFY_NEW_DELIVERY')
        before = facts(first, swap)
        with first.app.state.db.sessions() as a, second.app.state.db.sessions() as b:
            assert a.scalar(text('select pg_backend_pid()')) != b.scalar(text('select pg_backend_pid()'))
        gate = Barrier(2)
        def submit(http):
            gate.wait(timeout=10)
            return settle(http, swap, tech, case, op)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [first, second]))
        assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
        after = facts(first, swap)
        assert len(after['audit']) == 1 and after['holds'] == 0
        assert after['commands'] == before['commands'] and after['payment'] == before['payment']
        assert after['pin']['version'] == before['pin']['version']+1
