"""Real elapsed-time expiry in the synchronous P7 fixture; isolated PostgreSQL."""
import time
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import select

from app.application import device
from app.application.identity import DomainError, utcnow
from app.config import approved_policy
from app.seed import demo_id
from test_phase4 import row
from test_phase5 import prepare, verified
from test_phase7 import paid, drive


@pytest.mark.parametrize('boundary', ['verification', 'enqueue'])
def test_fixture_without_heartbeat_expires_before_deadline_assertion(
        client, environment, auth, boundary, record_property):
    actor = auth('customer')
    swap = None
    if boundary == 'verification':
        prepare(client, environment)
    else:
        swap = paid(client, environment, auth)
    db = client.app.state.db
    initial = row(client, 'devices', demo_id('device:S01'))
    policy = approved_policy()
    # Do not replace timestamps or extend the policy. Like a suspended test
    # process, this fixture emits no further heartbeat during real elapsed time.
    def pause():
        time.sleep(policy['telemetry_stale_seconds'] + 1)
        current = row(client, 'devices', initial['id'])
        age = (utcnow() - current['last_received_at']).total_seconds()
        record_property('heartbeat_age_seconds', age)
        record_property('boot_unchanged', current['boot_id'] == initial['boot_id'])
        assert current == initial and age > policy['telemetry_stale_seconds']
    with db.sessions() as session:
        for name in ('device_commands', 'recovery_operations', 'recovery_closure_intents'):
            assert session.execute(select(db.table(name).c.id)).first() is None
    if swap is None:
        pause()
        with pytest.raises(AssertionError, match='STATION_OFFLINE'):
            verified(client, environment, actor)
        return
    charge = row(client, 'payments', _payment_id(db, UUID(swap['id'])))
    before = row(client, 'swap_transactions', UUID(swap['id']))
    allowed = device.command_allowed
    def pause_at_interlock(*args):
        pause()
        return allowed(*args)
    # Resources are checked before enqueue. Suspend at the actual failing
    # boundary, so the production enqueue guard must check the clock again.
    with patch.object(device, 'command_allowed', pause_at_interlock):
        with pytest.raises(DomainError) as raised:
            drive(client, swap['id'])
    assert raised.value.code == 'COMMAND_INTERLOCK_FAILED'
    assert row(client, 'swap_transactions', UUID(swap['id'])) == before
    assert row(client, 'payments', charge['id']) == charge
    with db.sessions() as session:
        assert session.execute(select(db.table('device_commands').c.id)).first() is None


def _payment_id(db, swap_id):
    with db.sessions() as session:
        table = db.table('payments')
        return session.scalar(select(table.c.id).where(table.c.swap_id == swap_id))
