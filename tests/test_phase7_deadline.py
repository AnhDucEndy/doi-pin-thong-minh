"""P7-A01: independent physical deadline and freshness at locked custody decision."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update

from app.application import swaps
from app.application.identity import utcnow
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import packet, process, row, send
from test_phase5 import race_environment, login
from test_phase6 import book, consent, counts, outcome
from test_phase7 import paid, drive, command, physical


def acknowledged(http, env, swap, step):
    drive(http, swap['id'])
    if step == 'pickup':
        physical(http, env, swap, 'OPEN_RETURN'); drive(http, swap['id'])
    kind = 'OPEN_RETURN' if step == 'return' else 'OPEN_SUPPLY'
    cmd = command(http, swap, kind)
    assert http.get('/v1/device/commands', headers={'X-Device-Key':env['keys']['S01']}).status_code == 200
    dev = row(http, 'devices', demo_id('device:S01'))
    assert send(http, env, packet('COMMAND_ACK', str(dev['boot_id']), dev['last_seq']+1,
        {'result':'ACCEPTED','reason':'received'}, compartment_id=str(cmd['compartment_id']),
        swap_id=swap['id'], command_id=str(cmd['id']))).status_code == 202
    return kind, cmd


def observations(http, swap):
    db = http.app.state.db
    with db.sessions() as session:
        p, a = db.table('payments'), db.table('audit_events')
        payment = dict(session.execute(select(p).where(p.c.swap_id == UUID(swap['id']))).mappings().one())
        actions = list(session.scalars(select(a.c.action).where(a.c.aggregate_id == UUID(swap['id']))))
    return payment, actions


def assert_review(http, swap, step, before, payment):
    current = row(http, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == 'REVIEW_REQUIRED' and current['closed_at'] is None
    assert current['return_observed_at'] is None if step == 'return' else current['return_observed_at'] is not None
    assert current['pickup_observed_at'] is None
    assert row(http, 'batteries', before['id']) == before
    assert counts(http.app.state.db)['holds'] == 3
    assert counts(http.app.state.db)['device_commands'] == (1 if step == 'return' else 2)
    after, actions = observations(http, swap)
    assert after == payment and after['state'] == 'SUCCEEDED'
    assert actions.count('SWAP_RETURN_ACCEPTED') == (0 if step == 'return' else 1)
    assert 'SWAP_COMPLETED' not in actions
    assert actions.count('SWAP_REVIEW_REQUIRED') == 1


@pytest.mark.parametrize('step', ['return', 'pickup'])
@pytest.mark.parametrize('offset', [59.999999, 60, 60.000001, 61])
def test_custody_deadline_boundary_and_replay(client, environment, auth, monkeypatch, step, offset):
    swap = paid(client, environment, auth)
    kind, cmd = acknowledged(client, environment, swap, step)
    with owner(client) as (session, db):
        created = utcnow()-timedelta(seconds=50)
        t = db.table('device_commands')
        session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
    pin = UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id'])
    before = row(client, 'batteries', pin); payment, _ = observations(client, swap)
    monkeypatch.setattr(swaps, 'utcnow', lambda: created+timedelta(seconds=offset))
    bodies = physical(client, environment, swap, kind)
    event = row(client, 'device_events', UUID(bodies[-1]['event_id']))
    assert event['accepted'] and event['processed_at']
    assert row(client, 'device_commands', cmd['id'])['state'] == 'OBSERVED'
    if offset < 60:
        current = row(client, 'swap_transactions', UUID(swap['id']))
        assert current['state'] == ('RETURN_ACCEPTED' if step == 'return' else 'COMPLETED')
        assert row(client, 'batteries', pin)['location_kind'] != before['location_kind']
        assert counts(client.app.state.db)['holds'] == (3 if step == 'return' else 0)
    else:
        assert_review(client, swap, step, before, payment)
        for body in bodies: assert send(client, environment, body).status_code == 202
        drive(client, swap['id'])
        assert_review(client, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_freshness_still_required_inside_physical_window(client, environment, auth, monkeypatch, step):
    swap = paid(client, environment, auth); kind, cmd = acknowledged(client, environment, swap, step)
    before = row(client, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
    payment, _ = observations(client, swap)
    # No command age rewrite: decision <60s, evidence >15s.
    monkeypatch.setattr(swaps, 'utcnow', lambda:cmd['created_at']+timedelta(seconds=20))
    physical(client, environment, swap, kind)
    assert_review(client, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_deadline_crossed_during_final_evidence_read(client, environment, auth, monkeypatch, step):
    from app.application import assets
    swap = paid(client, environment, auth); kind, cmd = acknowledged(client, environment, swap, step)
    with owner(client) as (session, db):
        created = utcnow()-timedelta(seconds=50); t = db.table('device_commands')
        session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
    before = row(client, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
    payment, _ = observations(client, swap)
    clock = {'now':created+timedelta(seconds=59), 'inside':False}
    context, latest = swaps.physical_context, assets.latest_observation
    def enter(*args, **kwargs):
        clock['inside'] = True
        try: return context(*args, **kwargs)
        finally: clock['inside'] = False
    def read(*args, **kwargs):
        result = latest(*args, **kwargs)
        if clock['inside']: clock['now'] = created+timedelta(seconds=60)
        return result
    monkeypatch.setattr(swaps, 'utcnow', lambda:clock['now'])
    monkeypatch.setattr(swaps, 'physical_context', enter)
    monkeypatch.setattr(assets, 'latest_observation', read)
    physical(client, environment, swap, kind)
    assert_review(client, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_review_failure_rolls_back_inbox_then_retry_after_deadline(client, environment, auth, monkeypatch, step):
    swap = paid(client, environment, auth); kind, cmd = acknowledged(client, environment, swap, step)
    with owner(client) as (session, db):
        created = utcnow()-timedelta(seconds=50); t = db.table('device_commands')
        session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
    physical(client, environment, swap, kind, ('open','presence'))
    before = row(client, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
    payment, _ = observations(client, swap)
    closing = physical(client, environment, swap, kind, ('close',), process_it=False)[0]
    original = swaps.transition
    monkeypatch.setattr(swaps, 'utcnow', lambda:created+timedelta(seconds=61))
    def fail(*args, **kwargs): raise RuntimeError('injected review audit failure')
    monkeypatch.setattr(swaps, 'transition', fail)
    with pytest.raises(RuntimeError, match='review audit'):
        process(client, closing['event_id'])
    assert row(client, 'device_events', UUID(closing['event_id']))['processed_at'] is None
    assert row(client, 'batteries', before['id']) == before
    assert counts(client.app.state.db)['holds'] == 3
    monkeypatch.setattr(swaps, 'transition', original)
    process(client, closing['event_id'])
    assert_review(client, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_persisted_observed_command_resumed_after_deadline(client, environment, auth, monkeypatch, step):
    swap = paid(client, environment, auth); kind, cmd = acknowledged(client, environment, swap, step)
    original = swaps.advance
    # Persist accepted evidence first; resume service in a later transaction.
    monkeypatch.setattr(swaps, 'advance', lambda *args:None)
    physical(client, environment, swap, kind)
    monkeypatch.setattr(swaps, 'advance', original)
    with owner(client) as (session, db):
        created = utcnow()-timedelta(seconds=61); t = db.table('device_commands')
        session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
    before = row(client, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
    payment, _ = observations(client, swap)
    drive(client, swap['id']); drive(client, swap['id'])
    assert_review(client, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_two_event_workers_at_expired_custody_decision(race_environment, monkeypatch, step):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.workers import payment as worker
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor = login(http, env); swap = book(http, env, actor, env['seed_db'])
        assert consent(http, actor, swap).status_code == 202
        worker.tick(http.app.state.db, transport=outcome)
        kind, cmd = acknowledged(http, env, swap, step)
        with env['seed_db'].sessions.begin() as session:
            created = utcnow()-timedelta(seconds=50); t = env['seed_db'].table('device_commands')
            session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
        physical(http, env, swap, kind, ('open','presence'))
        closing = physical(http, env, swap, kind, ('close',), process_it=False)[0]
        before = row(http, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
        payment, _ = observations(http, swap)
        monkeypatch.setattr(swaps, 'utcnow', lambda:created+timedelta(seconds=61))
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:process(http, closing['event_id']), range(2)))
        assert_review(http, swap, step, before, payment)


@pytest.mark.parametrize('step', ['return', 'pickup'])
def test_timeout_worker_races_closing_evidence(race_environment, monkeypatch, step):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.workers import payment as worker
    from app.workers.device import expire_station
    from app.config import approved_policy
    env = race_environment
    with TestClient(create_app(env['settings'])) as http:
        actor = login(http, env); swap = book(http, env, actor, env['seed_db'])
        assert consent(http, actor, swap).status_code == 202
        worker.tick(http.app.state.db, transport=outcome)
        kind, cmd = acknowledged(http, env, swap, step)
        with env['seed_db'].sessions.begin() as session:
            created = utcnow()-timedelta(seconds=50); t = env['seed_db'].table('device_commands')
            session.execute(update(t).where(t.c.id == cmd['id']).values(created_at=created, expires_at=created+timedelta(seconds=15)))
        physical(http, env, swap, kind, ('open','presence'))
        closing = physical(http, env, swap, kind, ('close',), process_it=False)[0]
        before = row(http, 'batteries', UUID(swap['old_battery_id'] if step == 'return' else swap['new_battery_id']))
        payment, _ = observations(http, swap)
        expired = created+timedelta(seconds=61)
        monkeypatch.setattr(swaps, 'utcnow', lambda:expired)
        dev = row(http, 'devices', demo_id('device:S01'))
        def timeout():
            with http.app.state.db.sessions.begin() as session:
                expire_station(session, http.app.state.db, dev, approved_policy(), expired)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(process, http, closing['event_id']); b = pool.submit(timeout)
            a.result(); b.result()
        assert row(http, 'swap_transactions', UUID(swap['id']))['state'] == 'REVIEW_REQUIRED'
        assert row(http, 'batteries', before['id']) == before
        assert counts(http.app.state.db)['holds'] == 3
        assert counts(http.app.state.db)['device_commands'] == (1 if step == 'return' else 2)
        after, actions = observations(http, swap)
        assert after == payment and 'SWAP_COMPLETED' not in actions
        assert actions.count('SWAP_RETURN_ACCEPTED') == (0 if step == 'return' else 1)
