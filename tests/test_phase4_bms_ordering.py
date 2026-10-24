"""P4-A01: measurement order is independent of transport sequence and arrival time."""
from datetime import timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import func, insert, select, update

from app.application import assets, device as device_service
from app.application.identity import utcnow
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import (DEVICE, PIN, connected, packet, process, row, send,
                         snapshot_packet, telemetry)


def readings(client):
    db = client.app.state.db
    with db.sessions() as session:
        table = db.table('battery_telemetry')
        return [dict(r) for r in session.execute(select(table).where(table.c.battery_id == PIN)
            .order_by(table.c.received_at, table.c.id)).mappings()]


@pytest.mark.parametrize('change', ['lower_seq', 'older_time', 'equal_time_same', 'equal_time_changed'])
def test_measurement_and_sequence_must_both_advance(client, environment, change):
    boot = connected(client, environment)
    first = telemetry(boot, 5, soc=10)
    measured = utcnow() - timedelta(seconds=2)
    first['observed_at'] = measured.isoformat()
    send(client, environment, first)
    before = {name: row(client, name, identity) for name, identity in (
        ('devices', DEVICE), ('batteries', PIN), ('compartments', demo_id('S01:slot:2')))}
    before_readings = readings(client)
    candidate = telemetry(boot, 4 if change == 'lower_seq' else 6,
                          soc=10 if change == 'equal_time_same' else 90)
    delta = 1 if change == 'lower_seq' else -1 if change == 'older_time' else 0
    candidate['observed_at'] = (measured + timedelta(microseconds=delta)).isoformat()
    assert send(client, environment, candidate).status_code == 202
    event = row(client, 'device_events', UUID(candidate['event_id']))
    assert event['accepted'] is False and event['processing_error'] == 'EVENT_OUT_OF_ORDER'
    assert readings(client) == before_readings
    for name, expected in before.items():
        assert row(client, name, expected['id']) == expected
    # The durable rejection and audit commit, but no projection or duplicate audit does.
    db = client.app.state.db
    with db.sessions() as session:
        audit = db.table('audit_events')
        predicate = (audit.c.aggregate_id == event['id'], audit.c.action == 'DEVICE_EVENT_PROCESSED')
        logged = session.execute(select(audit).where(*predicate)).mappings().one()
        assert logged['after_data']['accepted'] is False
        assert logged['after_data']['error'] == 'EVENT_OUT_OF_ORDER'
    receipt = send(client, environment, candidate).json()
    assert receipt == {'event_id': candidate['event_id'], 'duplicate': True, 'processing_state': 'REJECTED'}
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(audit).where(*predicate)) == 1


def test_one_microsecond_newer_measurement_is_accepted(client, environment):
    boot = connected(client, environment)
    first = telemetry(boot, 5, soc=10)
    measured = utcnow() - timedelta(seconds=2)
    first['observed_at'] = measured.isoformat()
    send(client, environment, first)
    newer = telemetry(boot, 6, soc=90)
    newer['observed_at'] = (measured + timedelta(microseconds=1)).isoformat()
    send(client, environment, newer)
    assert row(client, 'device_events', UUID(newer['event_id']))['accepted'] is True
    assert readings(client)[-1]['soc'] == 90


@pytest.mark.parametrize('age_us,accepted', [(0, True), (14999999, True),
                                           (15000000, True), (15000001, False), (-1, False)])
def test_measurement_freshness_exact_boundaries(client, environment, monkeypatch, age_us, accepted):
    fixed = utcnow()
    monkeypatch.setattr(device_service, 'utcnow', lambda: fixed)
    snap = snapshot_packet()
    snap['observed_at'] = fixed.isoformat()
    assert send(client, environment, snap, False).status_code == 202
    process(client, snap['event_id'], fixed)
    body = telemetry(snap['boot_id'])
    body['observed_at'] = (fixed - timedelta(microseconds=age_us)).isoformat()
    assert send(client, environment, body, False).status_code == 202
    process(client, body['event_id'], fixed)
    event = row(client, 'device_events', UUID(body['event_id']))
    assert event['accepted'] is accepted
    assert event['processing_error'] == (None if accepted else 'EVENT_STALE_OR_FUTURE')
    if accepted:
        latest = readings(client)[-1]
        assert latest['received_at'] == fixed
        assert latest['measured_at'] == fixed - timedelta(microseconds=age_us)


@pytest.mark.parametrize('timestamp', ['missing', None, 'invalid', '2026-10-24T12:00:00', 123])
def test_invalid_or_missing_measurement_timestamp_never_enters_inbox(client, environment, timestamp):
    boot = connected(client, environment)
    body = telemetry(boot)
    if timestamp == 'missing':
        del body['observed_at']
    else:
        body['observed_at'] = timestamp
    before = row(client, 'devices', DEVICE)
    response = send(client, environment, body, False)
    assert response.status_code == 422 and response.json()['code'] == 'DEVICE_EVENT_INVALID'
    db = client.app.state.db
    with db.sessions() as session:
        table = db.table('device_events')
        assert session.scalar(select(table.c.id).where(table.c.id == UUID(body['event_id']))) is None
    assert row(client, 'devices', DEVICE) == before


def test_timezone_offset_does_not_make_equal_instant_newer(client, environment):
    boot = connected(client, environment)
    first = telemetry(boot)
    measured = utcnow() - timedelta(seconds=2)
    first['observed_at'] = measured.isoformat()
    send(client, environment, first)
    equal = telemetry(boot, 2)
    equal['observed_at'] = measured.astimezone(timezone(timedelta(hours=7))).isoformat()
    send(client, environment, equal)
    assert row(client, 'device_events', UUID(equal['event_id']))['processing_error'] == 'EVENT_OUT_OF_ORDER'


def test_boot_restart_does_not_reset_measurement_watermark(client, environment):
    boot = connected(client, environment)
    first = telemetry(boot, 5, soc=10)
    measured = utcnow() - timedelta(seconds=2)
    first['observed_at'] = measured.isoformat()
    send(client, environment, first)
    new_boot = connected(client, environment)
    old = telemetry(new_boot, 1, soc=90)
    old['observed_at'] = (measured - timedelta(microseconds=1)).isoformat()
    send(client, environment, old)
    assert row(client, 'device_events', UUID(old['event_id']))['processing_error'] == 'EVENT_OUT_OF_ORDER'
    newer = telemetry(new_boot, 2, soc=20)
    send(client, environment, newer)
    assert row(client, 'device_events', UUID(newer['event_id']))['accepted'] is True
    assert readings(client)[-1]['soc'] == 20


def test_watermark_is_per_pin_not_global_device_event_time(client, environment):
    boot = connected(client, environment)
    send(client, environment,telemetry(boot))
    # Another pin may have been measured earlier; a recent heartbeat also does not
    # set the BMS watermark. Only that pin's accepted measurements establish it.
    send(client, environment, packet(boot=boot, seq=2))
    other = telemetry(boot, 3, battery_id=str(demo_id('S01:battery:3')))
    other['compartment_id'] = str(demo_id('S01:slot:3'))
    other['observed_at'] = (utcnow() - timedelta(seconds=2)).isoformat()
    send(client, environment, other)
    assert row(client, 'device_events', UUID(other['event_id']))['accepted'] is True


def test_unsafe_accepted_sample_also_advances_watermark(client, environment):
    boot = connected(client, environment)
    bad = telemetry(boot, 1, soh=None)
    measured = utcnow() - timedelta(seconds=2)
    bad['observed_at'] = measured.isoformat()
    send(client, environment, bad)
    assert readings(client)[-1]['quality_ok'] is False
    old = telemetry(boot, 2)
    old['observed_at'] = (measured - timedelta(microseconds=1)).isoformat()
    send(client, environment, old)
    assert row(client, 'device_events', UUID(old['event_id']))['processing_error'] == 'EVENT_OUT_OF_ORDER'
    assert row(client, 'batteries', PIN)['lifecycle'] == 'QUARANTINED'
    assert readings(client)[-1]['quality_ok'] is False


def test_unverified_seed_does_not_establish_measurement_watermark(client, environment):
    boot = connected(client, environment)
    with owner(client) as (connection, db):
        table = db.table('battery_telemetry')
        connection.execute(update(table).where(table.c.battery_id == PIN)
                           .values(measured_at=utcnow() + timedelta(days=1)))
    body = telemetry(boot)
    send(client, environment, body)
    assert row(client, 'device_events', UUID(body['event_id']))['accepted'] is True


def test_availability_rejects_legacy_out_of_order_accepted_row_without_rewriting_history(client, environment, auth):
    boot = connected(client, environment)
    with owner(client) as (connection, db):
        connection.execute(update(db.table('batteries')).where(db.table('batteries').c.id == PIN).values(lifecycle='IN_SERVICE'))
        connection.execute(update(db.table('compartments')).where(
            db.table('compartments').c.id == demo_id('S01:slot:2')).values(service_state='ACTIVE'))
    first = telemetry(boot, 5, soc=10)
    measured = utcnow() - timedelta(seconds=2)
    first['observed_at'] = measured.isoformat()
    send(client, environment, first)
    old = telemetry(boot, 6, soc=90)
    old['observed_at'] = (measured - timedelta(microseconds=1)).isoformat()
    send(client, environment, old, False)
    # Reproduce a row persisted by the previous buggy release, in test only.
    with owner(client) as (connection, db):
        events, table = db.table('device_events'), db.table('battery_telemetry')
        event = row(client, 'device_events', UUID(old['event_id']))
        connection.execute(update(events).where(events.c.id == event['id']).values(accepted=True, processed_at=utcnow()))
        from uuid import uuid4
        connection.execute(insert(table).values(id=uuid4(), event_id=event['id'], battery_id=PIN,
            soc=90, soh=95, temperature_c=25, quality_ok=True,
            measured_at=event['observed_at'], received_at=event['received_at']))
    before = readings(client)
    response = client.get(f'/v1/batteries/{PIN}/telemetry', headers=auth())
    assert response.status_code == 200 and response.headers['X-Battery-Available'] == 'false'
    assert response.json()['items'][0]['soc'] == 90  # Preserve historical API ordering.
    assert readings(client) == before
    newer = telemetry(boot, 7, soc=90)
    send(client, environment, newer)
    assert client.get(f'/v1/batteries/{PIN}/telemetry', headers=auth()).headers['X-Battery-Available'] == 'true'
