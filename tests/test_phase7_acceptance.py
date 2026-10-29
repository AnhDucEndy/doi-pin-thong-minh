"""Independent deadline probe: physical window must hold at custody decision."""
from datetime import timedelta
from uuid import UUID
import pytest
from sqlalchemy import update
from app.application import swaps
from app.application.identity import utcnow
from app.seed import demo_id
from test_phase2 import owner
from test_phase4 import row, packet, send
from test_phase6 import counts
from test_phase7 import paid, drive, command, physical

@pytest.mark.parametrize('step', ['return','pickup'])
def test_physical_deadline_rechecked_at_custody(client, environment, auth, monkeypatch, step):
    swap=paid(client,environment,auth);drive(client,swap['id'])
    if step=='pickup':
        physical(client,environment,swap,'OPEN_RETURN');drive(client,swap['id'])
    kind='OPEN_RETURN' if step=='return' else 'OPEN_SUPPLY'
    cmd=command(client,swap,kind)
    client.get('/v1/device/commands',headers={'X-Device-Key':environment['keys']['S01']})
    dev=row(client,'devices',demo_id('device:S01'))
    assert send(client,environment,packet('COMMAND_ACK',str(dev['boot_id']),dev['last_seq']+1,
        {'result':'ACCEPTED','reason':'received'},compartment_id=str(cmd['compartment_id']),swap_id=swap['id'],command_id=str(cmd['id']))).status_code==202
    with owner(client) as (session,db):
        t=db.table('device_commands');created=utcnow()-timedelta(seconds=50)
        session.execute(update(t).where(t.c.id==cmd['id']).values(created_at=created,expires_at=created+timedelta(seconds=15)))
    pin=UUID(swap['old_battery_id'] if step=='return' else swap['new_battery_id'])
    before=row(client,'batteries',pin)
    # Simulate processing crossing the 60s deadline after command_event's check.
    # Evidence is still <15s old at the final clock; approved TTL is unchanged.
    monkeypatch.setattr(swaps,'utcnow',lambda:created+timedelta(seconds=61))
    physical(client,environment,swap,kind)
    after=row(client,'batteries',pin)
    current=row(client,'swap_transactions',UUID(swap['id']))
    assert after['location_kind']==before['location_kind'], f"custody changed after deadline: {before['location_kind']} -> {after['location_kind']}; state={current['state']}"
    assert counts(client.app.state.db)['holds']==3
