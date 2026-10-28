"""TC11/TC12: custody requires correlated evidence, not payment or ACK."""
from uuid import UUID
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, update

from app.application import swaps
from app.config import approved_policy
from app.seed import demo_id
from app.workers import payment
from app.workers.device import station_locks
from test_phase2 import owner
from test_phase4 import row, packet, send
from test_phase6 import book, consent, outcome, counts
from test_phase5 import race_environment, login


def drive(client, identity):
    db = client.app.state.db
    with db.sessions.begin() as session:
        station_locks(session, db, demo_id('S01'))
        swaps.advance(session, db, UUID(str(identity)))


def paid(client, environment, auth):
    actor = auth('customer')
    swap = book(client, environment, actor)
    assert consent(client, actor, swap).status_code == 202
    payment.tick(client.app.state.db, transport=outcome)
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'AWAITING_RETURN'
    return swap


def command(client, swap, kind):
    db = client.app.state.db
    with db.sessions() as session:
        t = db.table('device_commands')
        return dict(session.execute(select(t).where(t.c.swap_id == UUID(swap['id']), t.c.kind == kind)).mappings().one())


def physical(client, environment, swap, kind, stages=('open', 'presence', 'close'), wrong=False, process_it=True):
    cmd = command(client, swap, kind)
    response = client.get('/v1/device/commands', headers={'X-Device-Key': environment['keys']['S01']})
    assert response.status_code == 200, response.text
    dev = row(client, 'devices', demo_id('device:S01'))
    old = row(client, 'batteries', UUID(swap['old_battery_id']))
    new = row(client, 'batteries', UUID(swap['new_battery_id']))
    returning = kind == 'OPEN_RETURN'
    bodies = []
    for index, stage in enumerate(stages, 1):
        present = (not returning) if stage == 'open' else returning
        serial = (new['serial'] if not returning else None) if stage == 'open' else (old['serial'] if returning else None)
        if wrong and stage != 'open': serial = 'WRONG-RETURN'
        body = packet('PRESENCE' if stage == 'presence' else 'DOOR', str(dev['boot_id']), dev['last_seq'] + index,
            {'door_state': 'CLOSED' if stage == 'close' else 'OPEN', 'present': present, 'observed_serial': serial},
            compartment_id=str(cmd['compartment_id']), swap_id=swap['id'], command_id=str(cmd['id']))
        assert send(client, environment, body, process_it).status_code == 202
        bodies.append(body)
    return bodies


def test_TC11_full_custody_and_replay(client, environment, auth):
    swap = paid(client, environment, auth)
    drive(client, swap['id']); drive(client, swap['id'])
    assert counts(client.app.state.db)['device_commands'] == 1
    physical(client, environment, swap, 'OPEN_RETURN')
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == 'RETURN_ACCEPTED' and current['return_observed_at']
    old = row(client, 'batteries', UUID(swap['old_battery_id']))
    assert old['holder_user_id'] is None and str(old['compartment_id']) == swap['return_compartment_id']
    assert counts(client.app.state.db)['holds'] == 3
    drive(client, swap['id']); drive(client, swap['id'])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'AWAITING_PICKUP'
    bodies = physical(client, environment, swap, 'OPEN_SUPPLY')
    drive(client, swap['id'])
    done = row(client, 'swap_transactions', UUID(swap['id']))
    assert done['state'] == 'COMPLETED' and done['pickup_observed_at'] and done['closed_at']
    new = row(client, 'batteries', UUID(swap['new_battery_id']))
    assert new['location_kind'] == 'CUSTOMER' and new['holder_user_id'] == done['customer_id']
    assert counts(client.app.state.db)['holds'] == 0
    for body in bodies: assert send(client, environment, body).status_code == 202
    drive(client, swap['id'])
    assert row(client, 'swap_transactions', done['id']) == done
    assert counts(client.app.state.db)['device_commands'] == 2


@pytest.mark.parametrize('stages', [('close',), ('open', 'close'), ('open', 'presence')])
def test_incomplete_chain_never_changes_custody(client, environment, auth, stages):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    old = row(client, 'batteries', UUID(swap['old_battery_id']))
    physical(client, environment, swap, 'OPEN_RETURN', stages)
    drive(client, swap['id'])
    assert row(client, 'batteries', old['id']) == old
    assert counts(client.app.state.db)['holds'] == 3
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] != 'COMPLETED'


def test_wrong_return_reviews_without_custody(client, environment, auth):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    old = row(client, 'batteries', UUID(swap['old_battery_id']))
    physical(client, environment, swap, 'OPEN_RETURN', wrong=True)
    drive(client, swap['id'])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
    assert row(client, 'batteries', old['id']) == old
    assert counts(client.app.state.db)['holds'] == 3


def test_return_persists_when_supply_bms_becomes_unsafe(client, environment, auth):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    physical(client, environment, swap, 'OPEN_RETURN')
    with owner(client) as (session, db):
        t = db.table('batteries')
        session.execute(update(t).where(t.c.id == UUID(swap['new_battery_id'])).values(lifecycle='QUARANTINED'))
    drive(client, swap['id'])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
    assert row(client, 'batteries', UUID(swap['old_battery_id']))['location_kind'] == 'COMPARTMENT'
    assert counts(client.app.state.db)['device_commands'] == 1
    assert counts(client.app.state.db)['holds'] == 3


@pytest.mark.parametrize('state', ['AWAITING_PAYMENT', 'REVIEW_REQUIRED'])
def test_no_command_before_verified_payment_or_during_review(client, environment, auth, state):
    swap = book(client, environment, auth('customer'))
    with owner(client) as (session, db):
        table = db.table('swap_transactions')
        session.execute(update(table).where(table.c.id == UUID(swap['id'])).values(state=state))
    drive(client, swap['id'])
    assert counts(client.app.state.db)['device_commands'] == 0
    assert counts(client.app.state.db)['holds'] == 3


@pytest.mark.parametrize('step', ['return', 'supply'])
def test_final_clock_recheck_before_command(client, environment, auth, monkeypatch, step):
    swap = paid(client, environment, auth)
    if step == 'supply':
        drive(client, swap['id']); physical(client, environment, swap, 'OPEN_RETURN')
    from app.application.identity import utcnow
    future = utcnow() + timedelta(seconds=16)
    if step == 'return':
        from app.application import payments
        monkeypatch.setattr(payments, 'utcnow', lambda: future)
    else: monkeypatch.setattr(swaps, 'utcnow', lambda: future)
    drive(client, swap['id'])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
    assert counts(client.app.state.db)['device_commands'] == (0 if step == 'return' else 1)
    assert counts(client.app.state.db)['holds'] == 3


def test_ACK_is_not_return_custody(client, environment, auth):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    cmd = command(client, swap, 'OPEN_RETURN')
    assert client.get('/v1/device/commands', headers={'X-Device-Key':environment['keys']['S01']}).status_code == 200
    dev = row(client, 'devices', demo_id('device:S01'))
    body = packet('COMMAND_ACK', str(dev['boot_id']), dev['last_seq']+1,
        {'result':'ACCEPTED','reason':'received only'}, compartment_id=str(cmd['compartment_id']),
        swap_id=swap['id'], command_id=str(cmd['id']))
    assert send(client, environment, body).status_code == 202
    drive(client, swap['id'])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == 'AWAITING_RETURN'
    assert row(client, 'batteries', UUID(swap['old_battery_id']))['location_kind'] == 'CUSTOMER'
    assert counts(client.app.state.db)['holds'] == 3


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_inbox_custody_audit_rollback_and_retry(client, environment, auth, monkeypatch, step):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    if step == 'pickup':
        physical(client, environment, swap, 'OPEN_RETURN'); drive(client, swap['id'])
    kind = 'OPEN_RETURN' if step == 'return' else 'OPEN_SUPPLY'
    physical(client, environment, swap, kind, ('open', 'presence'))
    before = row(client, 'swap_transactions', UUID(swap['id']))
    original = swaps.transition
    def fail(*args, **kwargs): raise RuntimeError('injected audit failure before commit')
    monkeypatch.setattr(swaps, 'transition', fail)
    with pytest.raises(RuntimeError, match='injected audit'):
        physical(client, environment, swap, kind, ('close',))
    assert row(client, 'swap_transactions', UUID(swap['id'])) == before
    assert counts(client.app.state.db)['holds'] == 3
    pin = row(client, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
    assert pin['location_kind'] == ('CUSTOMER' if step == 'return' else 'COMPARTMENT')
    db = client.app.state.db
    with db.sessions() as session:
        events = db.table('device_events')
        pending = list(session.scalars(select(events.c.id).where(events.c.processed_at.is_(None),
            events.c.processing_error.is_(None), events.c.swap_id == UUID(swap['id']))))
    assert len(pending) == 1
    monkeypatch.setattr(swaps, 'transition', original)
    from test_phase4 import process
    process(client, pending[0])
    assert row(client, 'swap_transactions', UUID(swap['id']))['state'] == ('RETURN_ACCEPTED' if step == 'return' else 'COMPLETED')


def test_two_workers_one_command_and_one_custody(race_environment):
    from fastapi.testclient import TestClient
    from app.main import create_app
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor = login(http, env); swap = book(http, env, actor, env['seed_db'])
        assert consent(http, actor, swap).status_code == 202
        payment.tick(http.app.state.db, transport=outcome)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:drive(http, swap['id']), range(2)))
        assert counts(http.app.state.db)['device_commands'] == 1
        physical(http, env, swap, 'OPEN_RETURN')
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:drive(http, swap['id']), range(2)))
        assert counts(http.app.state.db)['device_commands'] == 2
        physical(http, env, swap, 'OPEN_SUPPLY')
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:drive(http, swap['id']), range(2)))
        assert row(http, 'swap_transactions', UUID(swap['id']))['state'] == 'COMPLETED'
        assert counts(http.app.state.db)['holds'] == 0


@pytest.mark.parametrize('age,accepted', [(20, True), (61, False)])
def test_acknowledged_physical_window_is_60_seconds(client, environment, auth, age, accepted):
    from app.application.identity import utcnow
    swap = paid(client, environment, auth); drive(client, swap['id'])
    cmd = command(client, swap, 'OPEN_RETURN')
    client.get('/v1/device/commands', headers={'X-Device-Key':environment['keys']['S01']})
    dev = row(client, 'devices', demo_id('device:S01'))
    assert send(client, environment, packet('COMMAND_ACK', str(dev['boot_id']), dev['last_seq']+1,
        {'result':'ACCEPTED','reason':'received'}, compartment_id=str(cmd['compartment_id']),
        swap_id=swap['id'], command_id=str(cmd['id']))).status_code == 202
    # Deterministic elapsed-time fixture, in the per-test rollback transaction.
    with owner(client) as (session, db):
        t = db.table('device_commands'); created = utcnow()-timedelta(seconds=age)
        session.execute(update(t).where(t.c.id==cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
    physical(client, environment, swap, 'OPEN_RETURN')
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert (current['state']=='RETURN_ACCEPTED') == accepted
    assert (row(client,'batteries',UUID(swap['old_battery_id']))['location_kind']=='COMPARTMENT') == accepted
    if not accepted:
        db=client.app.state.db
        with db.sessions() as s:
            t=db.table('device_events')
            assert 'COMMAND_LATE_OR_UNKNOWN' in list(s.scalars(select(t.c.processing_error)))


def test_simulator_equal_clock_waits_for_real_later_sample(tmp_path, monkeypatch):
    from simulators.device import main as simulator
    from app.application.identity import utcnow
    sim=simulator.Simulator('S01','local-test-key-not-a-real-credential',ledger=tmp_path/'clock.sqlite3')
    stamp=utcnow(); samples=iter([stamp.isoformat(),stamp.isoformat(),(stamp+timedelta(milliseconds=1)).isoformat()])
    monkeypatch.setattr(simulator,'now',lambda:next(samples))
    try:
        a=sim.emit('HEARTBEAT',{'health':'OK'}); b=sim.emit('HEARTBEAT',{'health':'OK'})
        assert a['observed_at']<b['observed_at'] and b['seq']==a['seq']+1
    finally:sim.close()


def test_two_event_workers_commit_pickup_once(race_environment):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from test_phase4 import process
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor=login(http,env);swap=book(http,env,actor,env['seed_db'])
        assert consent(http,actor,swap).status_code==202
        payment.tick(http.app.state.db,transport=outcome)
        drive(http,swap['id']);physical(http,env,swap,'OPEN_RETURN');drive(http,swap['id'])
        physical(http,env,swap,'OPEN_SUPPLY',('open','presence'))
        closing=physical(http,env,swap,'OPEN_SUPPLY',('close',),process_it=False)[0]
        assert row(http,'swap_transactions',UUID(swap['id']))['state']=='AWAITING_PICKUP'
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:process(http,closing['event_id']),range(2)))
        assert row(http,'swap_transactions',UUID(swap['id']))['state']=='COMPLETED'
        assert counts(http.app.state.db)['holds']==0
        with http.app.state.db.sessions() as session:
            table=http.app.state.db.table('audit_events')
            actions=list(session.scalars(select(table.c.action).where(table.c.aggregate_id==UUID(swap['id']))))
        assert actions.count('SWAP_COMPLETED')==1
