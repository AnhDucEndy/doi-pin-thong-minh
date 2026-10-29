"""Independent post-fix integration gaps; preserve original deadline probes."""
from datetime import timedelta
from uuid import UUID
from fastapi.encoders import jsonable_encoder
from app.application import reservations
from app.application.identity import utcnow
from app.config import approved_policy
from app.seed import demo_id
from app.workers import payment
from app.workers.device import expire_station
from test_phase4 import row
from test_phase6 import counts, callback
from test_phase7 import paid, drive, physical
from test_phase7_deadline import acknowledged, observations


def test_return_custody_survives_missing_pickup_and_reservation_expiry(client, environment, auth):
    swap = paid(client, environment, auth)
    _, cmd = acknowledged(client, environment, swap, 'pickup')
    before = row(client, 'batteries', UUID(swap['old_battery_id']))
    assert before['location_kind'] == 'COMPARTMENT'
    p, _ = observations(client, swap)
    future = utcnow()+timedelta(seconds=121)
    reservations.expire(client.app.state.db, future)
    assert counts(client.app.state.db)['holds'] == 3
    dev = row(client, 'devices', demo_id('device:S01'))
    with client.app.state.db.sessions.begin() as session:
        expire_station(session, client.app.state.db, dev, approved_policy(), future)
    drive(client, swap['id'])
    current = row(client, 'swap_transactions', UUID(swap['id']))
    assert current['state'] == 'REVIEW_REQUIRED' and current['pickup_observed_at'] is None
    assert row(client, 'batteries', before['id'])['compartment_id'] == before['compartment_id']
    assert row(client, 'batteries', UUID(swap['new_battery_id']))['location_kind'] == 'COMPARTMENT'
    assert counts(client.app.state.db)['holds'] == 3
    after, actions = observations(client, swap)
    assert after == p and 'SWAP_COMPLETED' not in actions


def test_late_payment_callback_does_not_reopen_completed_swap(client, environment, auth):
    swap = paid(client, environment, auth); drive(client, swap['id'])
    physical(client, environment, swap, 'OPEN_RETURN'); drive(client, swap['id'])
    physical(client, environment, swap, 'OPEN_SUPPLY')
    before = row(client, 'swap_transactions', UUID(swap['id']))
    p, actions = observations(client, swap)
    assert before['state'] == 'COMPLETED'
    for result in ('SUCCEEDED', 'PENDING', 'FAILED'):
        assert callback(client, jsonable_encoder(p), result=result).status_code == 202
        payment.tick(client.app.state.db)
        drive(client, swap['id'])
        assert row(client, 'swap_transactions', before['id']) == before
        assert observations(client, swap)[0] == p
        assert counts(client.app.state.db)['holds'] == 0
        assert counts(client.app.state.db)['device_commands'] == 2
    assert observations(client, swap)[1].count('SWAP_COMPLETED') == 1
