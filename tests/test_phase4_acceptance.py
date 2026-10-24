"""Independent Phase 4 acceptance probes; only rollback PostgreSQL fixtures.

No demo mutations and no production implementation changes.
"""
from datetime import timedelta
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update

from app.application.identity import utcnow
from app.config import ROOT
from app.seed import demo_id
from test_phase2 import owner
from test_phase1 import headers
from test_phase4 import (DEVICE, PIN, SLOT, connected, row, send,
                         snapshot_packet, telemetry)


@pytest.mark.parametrize('case', ['expired', 'lower_sequence', 'older_measurement'])
def test_acceptance_late_telemetry_never_replaces_newer_measurement(client, environment, case):
    boot = connected(client, environment)
    first = telemetry(boot, 5, soc=91)
    # Both measurements are inside TTL for the older_measurement case. Sequence
    # alone cannot prove the measurement timestamp is newer.
    first['observed_at'] = (utcnow() - timedelta(seconds=2)).isoformat()
    assert send(client, environment, first).status_code == 202
    before = row(client, 'devices', DEVICE)
    late = telemetry(boot, 4 if case == 'lower_sequence' else 6, soc=10)
    late['observed_at'] = (utcnow() - timedelta(seconds=30 if case == 'expired' else 4)).isoformat()
    assert send(client, environment, late).status_code == 202
    event = row(client, 'device_events', UUID(late['event_id']))
    assert event['accepted'] is False, 'Older BMS measurement was accepted as the latest reading'
    assert row(client, 'devices', DEVICE) == before
    db = client.app.state.db
    with db.sessions() as session:
        table = db.table('battery_telemetry')
        latest = session.execute(select(table).where(table.c.battery_id == PIN)
            .order_by(table.c.received_at.desc(), table.c.id.desc()).limit(1)).mappings().one()
        assert latest['soc'] == 91


def test_acceptance_incomplete_snapshot_rejection_is_atomic(client, environment):
    before = row(client, 'compartments', SLOT)
    packet = snapshot_packet()
    packet['payload']['slots'].pop()
    assert send(client, environment, packet).status_code == 202
    event = row(client, 'device_events', UUID(packet['event_id']))
    assert event['processing_error'] == 'SNAPSHOT_INCOMPLETE'
    assert row(client, 'devices', DEVICE)['boot_id'] is None
    assert row(client, 'compartments', SLOT) == before


def test_acceptance_duplicate_telemetry_has_exactly_one_reading(client, environment):
    boot = connected(client, environment)
    packet = telemetry(boot)
    assert send(client, environment, packet).status_code == 202
    before = row(client, 'devices', DEVICE)
    replay = send(client, environment, packet)
    assert replay.json()['duplicate'] is True
    assert replay.json()['processing_state'] == 'PROCESSED'
    assert row(client, 'devices', DEVICE) == before
    db = client.app.state.db
    with db.sessions() as session:
        table = db.table('battery_telemetry')
        assert len(session.execute(select(table.c.id).where(
            table.c.event_id == UUID(packet['event_id']))).all()) == 1


def test_acceptance_older_good_soc_cannot_override_newer_low_soc(client, environment, auth):
    boot = connected(client, environment)
    # Fixture states only; actual measurements still enter through authenticated
    # receive + worker, not fabricated accepted telemetry rows.
    with owner(client) as (connection, db):
        connection.execute(update(db.table('batteries')).where(db.table('batteries').c.id == PIN)
            .values(lifecycle='IN_SERVICE'))
        connection.execute(update(db.table('compartments')).where(
            db.table('compartments').c.id == demo_id('S01:slot:2')).values(service_state='ACTIVE'))
    admin = auth()
    first = telemetry(boot, 5, soc=10)
    first['observed_at'] = (utcnow() - timedelta(seconds=2)).isoformat()
    send(client, environment, first)
    path = f'/v1/batteries/{PIN}/telemetry'
    before = client.get(path, headers=admin)
    assert before.headers['X-Battery-Available'] == 'false'
    older = telemetry(boot, 6, soc=90)
    older['observed_at'] = (utcnow() - timedelta(seconds=4)).isoformat()
    send(client, environment, older)
    after = client.get(path, headers=admin)
    event = row(client, 'device_events', UUID(older['event_id']))
    evidence = {'schema': environment['settings'].schema,
        'newer_measurement': {'seq': 5, 'soc': 10, 'observed_at': first['observed_at']},
        'older_arrival': {'seq': 6, 'soc': 90, 'observed_at': older['observed_at'],
            'accepted': event['accepted'], 'processing_error': event['processing_error']},
        'before_available': before.headers['X-Battery-Available'],
        'after_available': after.headers['X-Battery-Available'],
        'latest_api_reading': after.json()['items'][0],
        'lifecycle': row(client, 'batteries', PIN)['lifecycle'],
        'test_only': True, 'transaction_rolled_back_by_fixture': True}
    (ROOT / 'docs/PHASE4_ACCEPTANCE/LATE_TELEMETRY_FINDING.json').write_text(
        json.dumps(evidence, default=str, indent=2) + '\n', encoding='utf-8')
    assert after.headers['X-Battery-Available'] == 'false', 'Older good SOC made the pin available despite newer low SOC'


def test_acceptance_alert_mutation_roles_and_scope_rejected_atomically(client, auth):
    foreign, own = uuid4(), uuid4()
    with owner(client) as (connection, db):
        for identity, code in [(foreign, 'S02'), (own, 'S01')]:
            connection.execute(insert(db.table('alerts')).values(id=identity,
                station_id=demo_id(code), dedup_key=str(identity), code='ACCEPTANCE_SIMULATED_FAULT'))
    tech, customer, admin = auth('technician'), auth('customer'), auth()
    for actor, identity, expected in [(tech, foreign, 'STATION_FORBIDDEN'),
        (customer, own, 'FORBIDDEN'), (admin, own, 'FORBIDDEN')]:
        before = row(client, 'alerts', identity)
        response = client.post(f'/v1/alerts/{identity}/acknowledge',
            headers=headers(actor), json={'expected_version': before['version']})
        assert response.status_code == 403 and response.json()['code'] == expected
        assert row(client, 'alerts', identity) == before
