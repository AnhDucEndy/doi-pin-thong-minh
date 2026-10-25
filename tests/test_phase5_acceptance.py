"""Independent acceptance probes. Expectations derive from INVARIANTS/SM-03a/CT01-02.

Only isolated PostgreSQL fixtures; no production changes and no business patches.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update

from app.application import reservations as service
from app.application.identity import DomainError, utcnow
from app.config import ROOT
from app.main import create_app
from app.seed import demo_id
from test_phase1 import headers
from test_phase2 import owner
from test_phase4 import row, send, snapshot_packet, telemetry
from test_phase5 import (prepare, login, qr, verify, verified, reserve, cancel,
                        second_customer, race_environment, PIN, SLOT)


def evidence(name, value):
    out = ROOT / 'docs/PHASE5_ACCEPTANCE'
    out.mkdir(parents=True, exist_ok=True)
    (out / (name + '.json')).write_text(json.dumps(value, default=str, indent=2) + '\n', encoding='utf-8')


def holds(http, identity):
    db = http.app.state.db
    with db.sessions() as s:
        t = db.table('resource_reservations')
        return [dict(x) for x in s.execute(select(t).where(t.c.swap_id == UUID(identity))).mappings()]


@pytest.mark.parametrize('slot_number', [1, 2])
def test_old_closed_snapshot_cannot_authorize_reservation(client, environment, auth, slot_number):
    """No synthetic accepted evidence: all snapshots pass the actual inbox + worker."""
    boot = prepare(client, environment)
    customer = auth('customer')
    swap = verified(client, environment, customer)
    identity = demo_id(f'S01:slot:{slot_number}')
    old_closed = snapshot_packet(boot, 3)
    newer_open = snapshot_packet(boot, 2)
    newer_open['payload']['slots'][slot_number - 1]['door_state'] = 'OPEN'
    assert send(client, environment, newer_open).status_code == 202
    assert row(client, 'device_events', UUID(newer_open['event_id']))['accepted'] is True
    assert row(client, 'compartments', identity)['door_state'] == 'OPEN'
    assert send(client, environment, old_closed).status_code == 202
    old_event = row(client, 'device_events', UUID(old_closed['event_id']))
    response = reserve(client, customer, swap)
    after = row(client, 'compartments', identity)
    evidence('STALE_DOOR_' + str(slot_number), {
        'schema': client.app.state.settings.schema, 'new_open_observed_at': newer_open['observed_at'],
        'old_closed_observed_at': old_closed['observed_at'], 'old_sequence': 3,
        'old_event_accepted': old_event['accepted'], 'processing_error': old_event['processing_error'],
        'door_before': 'OPEN', 'door_after': after['door_state'],
        'reserve_status': response.status_code, 'reserve_state': response.json().get('state'),
        'holds': holds(client, swap['id']), 'physical_commands_created': 0})
    assert response.json().get('state') != 'RESERVED', 'Stale CLOSED snapshot authorized three resource holds'
    assert after['door_state'] == 'OPEN', 'An older observation replaced the newer door projection'


def test_qr_consumed_at_verification_even_when_reservation_has_no_resources(client, environment, auth):
    prepare(client, environment)
    customer = auth('customer'); code = qr(client, customer)
    first = verify(client, environment, code['qr_token'])
    assert first.status_code == 201
    with owner(client) as (s, db):
        t = db.table('compartments')
        s.execute(update(t).where(t.c.id == SLOT).values(service_state='MAINTENANCE'))
    result = reserve(client, customer, first.json())
    assert result.json()['state'] == 'CANCELLED'
    assert holds(client, first.json()['id']) == []
    assert row(client, 'qr_challenges', UUID(code['challenge_id']))['consumed_at'] is not None
    assert verify(client, environment, code['qr_token']).json()['code'] == 'QR_ALREADY_USED'


def test_failure_on_second_hold_insert_rolls_back_first_hold(client, environment, auth):
    prepare(client, environment); customer = auth('customer')
    swap = verified(client, environment, customer); count = 0
    connection = client.app.state.test_connection
    def fail(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        if statement.lstrip().upper().startswith('INSERT INTO') and 'resource_reservations' in statement:
            count += 1
            if count == 2:
                raise DomainError(422, 'ACCEPTANCE_INJECTED_STORAGE_FAILURE')
    event.listen(connection, 'before_cursor_execute', fail)
    try:
        result = reserve(client, customer, swap)
    finally:
        event.remove(connection, 'before_cursor_execute', fail)
    assert count == 2 and result.status_code == 422
    assert holds(client, swap['id']) == []
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'VERIFIED'
    assert reserve(client, customer, swap).json()['state'] == 'RESERVED'


def test_two_expiration_workers_close_and_audit_once(race_environment):
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http, env, env['seed_db']); customer = login(http, env)
        swap = verified(http, env, customer); assert reserve(http, customer, swap).json()['state'] == 'RESERVED'
        deadline = row(http, 'swap_transactions', UUID(swap['id']))['reservation_expires_at']
        barrier = Barrier(2)
        def expire():
            barrier.wait(); return service.expire(http.app.state.db, deadline)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: expire(), range(2)))
        assert sum(results) == 1
        assert row(http, 'swap_transactions', UUID(swap['id']))['state'] == 'CANCELLED'
        assert len(holds(http, swap['id'])) == 3 and all(h['released_at'] for h in holds(http, swap['id']))
        with env['seed_db'].sessions() as s:
            t = env['seed_db'].table('audit_events')
            assert s.scalar(select(func.count()).select_from(t).where(t.c.aggregate_id == UUID(swap['id']), t.c.action == 'CANCEL_RESERVATION')) == 1


@pytest.mark.parametrize('same_key', [False, True])
def test_rfid_concurrent_reads_no_implicit_reservation(race_environment, same_key):
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http, env, env['seed_db']); admin = login(http, env, 'admin')
        value = 'acceptance-' + uuid4().hex
        created = http.post(f'/v1/users/{demo_id("customer")}/credentials', headers=headers(admin), json={'rfid_value': value})
        assert created.status_code == 201
        key = uuid4(); barrier = Barrier(2)
        def read(i):
            barrier.wait(); return verify(http, env, value, 'RFID', key if same_key else uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(read, range(2)))
        assert sorted(r.status_code for r in responses) == ([201, 201] if same_key else [201, 409])
        if same_key: assert responses[0].json()['id'] == responses[1].json()['id']
        else: assert next(r for r in responses if r.status_code == 409).json()['code'] == 'ACTIVE_TRANSACTION'
        with env['seed_db'].sessions() as s:
            assert s.scalar(select(func.count()).select_from(env['seed_db'].table('resource_reservations'))) == 0
            assert s.scalar(select(func.count()).select_from(env['seed_db'].table('swap_transactions'))) == 1


def test_rfid_revocation_competes_with_verify(race_environment):
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        prepare(http, env, env['seed_db']); admin = login(http, env, 'admin')
        value = 'acceptance-' + uuid4().hex
        created = http.post(f'/v1/users/{demo_id("customer")}/credentials', headers=headers(admin), json={'rfid_value': value}).json()
        barrier = Barrier(2)
        def revoke():
            barrier.wait(); return http.post(f'/v1/credentials/{created["id"]}/revoke', headers=headers(admin))
        def read():
            barrier.wait(); return verify(http, env, value, 'RFID')
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(revoke), pool.submit(read)
            revoked, verified_result = a.result(), b.result()
        assert revoked.status_code == 200 and verified_result.status_code in (201, 401)
        assert verify(http, env, value, 'RFID').json()['code'] == 'CREDENTIAL_INVALID'
        with env['seed_db'].sessions() as s:
            t = env['seed_db'].table('swap_transactions')
            assert s.scalar(select(func.count()).select_from(t)) == (1 if verified_result.status_code == 201 else 0)


def test_revoke_user_session_then_retry_cannot_read_historical_receipt(client, environment, auth):
    prepare(client, environment); customer = auth('customer')
    swap = verified(client, environment, customer); key = uuid4()
    booked = reserve(client, customer, swap, key); assert booked.json()['state'] == 'RESERVED'
    assert client.post('/v1/auth/logout', headers=headers(customer)).status_code == 200
    retry = reserve(client, customer, swap, key)
    assert retry.status_code == 401 and retry.json()['code'] == 'SESSION_REVOKED'
    assert len(holds(client, swap['id'])) == 3


def test_user_locked_while_reserved_can_still_expire(client, environment, auth):
    prepare(client, environment); customer = auth('customer'); admin = auth('admin')
    swap = verified(client, environment, customer); booked = reserve(client, customer, swap).json()
    user = row(client, 'users', demo_id('customer'))
    response = client.patch(f'/v1/users/{user["id"]}', headers=headers(admin), json={'expected_version':user['version'], 'state':'LOCKED'})
    assert response.status_code == 200
    assert cancel(client, customer, booked).status_code == 401
    db = client.app.state.db
    deadline = row(client, 'swap_transactions', UUID(swap['id']))['reservation_expires_at']
    service.expire(db, deadline)
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'CANCELLED'
    assert all(h['released_at'] for h in holds(client, swap['id']))


@pytest.mark.parametrize('guard', ['consent', 'return_evidence', 'pickup_evidence'])
def test_expiration_respects_handoff_evidence(client, environment, auth, guard):
    prepare(client, environment); customer = auth('customer'); swap = verified(client, environment, customer)
    booked = reserve(client, customer, swap).json()
    column = {'consent':'consented_at','return_evidence':'return_observed_at','pickup_evidence':'pickup_observed_at'}[guard]
    with owner(client) as (s, db):
        t = db.table('swap_transactions'); s.execute(update(t).where(t.c.id == UUID(swap['id'])).values(**{column:utcnow()}))
    before = holds(client, swap['id'])
    service.expire(client.app.state.db, row(client, 'swap_transactions', UUID(swap['id']))['reservation_expires_at'])
    assert cancel(client, customer, booked).json()['code'] == 'RECONCILIATION_REQUIRED'
    assert holds(client, swap['id']) == before


def test_rfid_identity_cannot_be_reassigned_to_another_customer(client, environment, auth):
    admin = auth('admin'); value = 'acceptance-' + uuid4().hex
    first = client.post(f'/v1/users/{demo_id("customer")}/credentials', headers=headers(admin), json={'rfid_value':value})
    assert first.status_code == 201
    # Another valid Customer already present in isolated migration fixture.
    db = client.app.state.db
    with db.sessions() as s:
        t = db.table('users'); other = s.scalar(select(t.c.id).where(t.c.username == 'migration-survivor'))
    conflict = client.post(f'/v1/users/{other}/credentials', headers=headers(admin), json={'rfid_value':value})
    assert conflict.status_code == 409 and conflict.json()['code'] == 'RESOURCE_CONFLICT'
    assert row(client, 'credentials', UUID(first.json()['id']))['user_id'] == demo_id('customer')


@pytest.mark.parametrize('extra_supply', [False, True])
def test_competing_customers_single_pin_or_single_return_slot(race_environment, extra_supply):
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        boot = prepare(http, env, env['seed_db']); a = login(http, env); b = second_customer(http, env)
        if extra_supply:
            pin3, slot3 = demo_id('S01:battery:3'), demo_id('S01:slot:3')
            with env['seed_db'].sessions.begin() as s:
                t = env['seed_db'].table('compartments'); s.execute(update(t).where(t.c.id == slot3).values(service_state='ACTIVE'))
                t = env['seed_db'].table('batteries'); s.execute(update(t).where(t.c.id == pin3).values(lifecycle='IN_SERVICE'))
            packet = telemetry(boot, 2)
            packet['compartment_id'] = str(slot3); packet['payload']['battery_id'] = str(pin3)
            assert send(http, env, packet).status_code == 202
            assert row(http, 'device_events', UUID(packet['event_id']))['accepted'] is True
        swaps = [verified(http, env, x) for x in (a,b)]; barrier = Barrier(2)
        def book(pair):
            barrier.wait(); return reserve(http, *pair)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(book, zip((a,b), swaps)))
        assert sorted(r.json().get('state') for r in results) == ['CANCELLED', 'RESERVED']
        winner = next(r.json() for r in results if r.json()['state'] == 'RESERVED')
        loser = next(r.json() for r in results if r.json()['state'] == 'CANCELLED')
        assert len(holds(http, winner['id'])) == 3 and not holds(http, loser['id'])
        assert winner['return_compartment_id'] == str(SLOT)
        with env['seed_db'].sessions() as s:
            t = env['seed_db'].table('resource_reservations')
            rows = s.execute(select(t).where(t.c.released_at.is_(None))).mappings().all()
            assert len(rows) == 3
            assert len({r['compartment_id'] for r in rows if r['compartment_id']}) == 2
            assert len({r['battery_id'] for r in rows if r['battery_id']}) == 1


@pytest.mark.parametrize('slot_number', [1, 2])
def test_strictly_older_closed_snapshot_cannot_authorize_reservation(client, environment, auth, slot_number):
    """Separate probe: enforce strict timestamp inequality; retain the original probes."""
    boot = prepare(client, environment)
    customer = auth('customer'); swap = verified(client, environment, customer)
    identity = demo_id(f'S01:slot:{slot_number}')
    newer = snapshot_packet(boot, 2)
    older = snapshot_packet(boot, 3)
    from datetime import datetime
    older['observed_at'] = (datetime.fromisoformat(newer['observed_at']) - timedelta(seconds=1)).isoformat()
    newer['payload']['slots'][slot_number - 1]['door_state'] = 'OPEN'
    assert datetime.fromisoformat(older['observed_at']) < datetime.fromisoformat(newer['observed_at'])
    assert send(client, environment, newer).status_code == 202
    assert row(client, 'device_events', UUID(newer['event_id']))['accepted'] is True
    assert row(client, 'compartments', identity)['door_state'] == 'OPEN'
    assert send(client, environment, older).status_code == 202
    rejected = row(client, 'device_events', UUID(older['event_id']))
    response = reserve(client, customer, swap)
    db = client.app.state.db
    with db.sessions() as s:
        commands = s.scalar(select(func.count()).select_from(db.table('device_commands')))
        audit = db.table('audit_events')
        audits = [dict(x) for x in s.execute(select(audit).where(audit.c.aggregate_id == UUID(older['event_id']))).mappings()]
    evidence('STRICTLY_OLDER_DOOR_' + str(slot_number), {
        'schema': client.app.state.settings.schema, 'newer_open':newer, 'older_closed':older,
        'accepted':rejected['accepted'], 'processing_error':rejected['processing_error'],
        'received_at':rejected['received_at'], 'processed_at':rejected['processed_at'],
        'door_after':row(client, 'compartments', identity)['door_state'],
        'response_status':response.status_code, 'response':response.json(),
        'holds':holds(client, swap['id']), 'commands_count':commands, 'event_audit':audits})
    assert response.json().get('state') != 'RESERVED', 'Strictly older CLOSED observation allowed reservation'
    assert row(client, 'compartments', identity)['door_state'] == 'OPEN'
