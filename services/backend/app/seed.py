"""Idempotent demo seed. Never reset passwords, locations or existing policy revisions."""
import hashlib
import os
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import insert, select
from app.config import ROOT, Settings, approved_policy
from app.domain.identity import digest, hasher
from app.infrastructure.db import Database, advisory_lock
from app.application.identity import utcnow
from app.domain.bms import BMSPayload


def demo_id(name):
    return uuid5(NAMESPACE_URL, 'doi-pin-demo:' + name)


def seed(db, passwords, device_keys):
    policy = approved_policy()
    if any(len(value) < 12 or value.startswith('REPLACE_') for value in passwords.values()):
        raise ValueError('Demo account passwords must be supplied and at least 12 characters')
    if any(len(value) < 24 or value.startswith('REPLACE_') for value in device_keys.values()):
        raise ValueError('Demo device keys must be supplied and at least 24 characters')
    with db.sessions.begin() as session:
        advisory_lock(session, 'foundation:seed')

        def add(table_name, identity, **values):
            table = db.table(table_name)
            existing = session.execute(select(table).where(table.c.id == identity)).first()
            if not existing:
                session.execute(insert(table).values(id=identity, **values))

        for username, role in [('admin', 'ADMIN'), ('customer', 'CUSTOMER'), ('technician', 'TECHNICIAN')]:
            add('users', demo_id(username), username=username, password_hash=hasher.hash(passwords[username]), role=role)
        policy_table = db.table('demo_policies')
        existing = session.execute(select(policy_table).where(policy_table.c.revision == 1)).mappings().first()
        if existing and (existing['parameters'] != policy or existing['review_status'] != policy['decision_status']):
            raise ValueError('Existing policy revision differs; do not overwrite it')
        if not existing:
            approved = ROOT / 'doi-pin-giai-doan-2/handoff/decisions.approved.json'
            add('demo_policies', demo_id('policy:1'), revision=1, parameters=policy,
                review_status=policy['decision_status'], approval_evidence={
                    'authority': 'user', 'approved_on': '2026-10-23',
                    'source': 'doi-pin-giai-doan-2/handoff/decisions.approved.json',
                    'sha256': hashlib.sha256(approved.read_bytes()).hexdigest()})
        for station_no in (1, 2):
            code = f'S{station_no:02}'
            station_id = demo_id(code)
            add('stations', station_id, code=code, name=f'Trạm mô phỏng {station_no}', address=f'Địa điểm demo {station_no}')
            add('devices', demo_id('device:' + code), station_id=station_id, serial='DEMO-' + code,
                key_hash=digest(device_keys[code]))
            for slot in range(1, 7):
                compartment = demo_id(f'{code}:slot:{slot}')
                add('compartments', compartment, station_id=station_id, slot_no=slot)
                if slot > 1:
                    add('batteries', demo_id(f'{code}:battery:{slot}'), serial=f'{code}-B{slot:03}',
                        family=policy['battery_family'], lifecycle='REGISTERED',
                        location_kind='COMPARTMENT', compartment_id=compartment)
        add('batteries', demo_id('customer:initial-battery'), serial='CUSTOMER-B001', family=policy['battery_family'],
            lifecycle='REGISTERED', location_kind='CUSTOMER', holder_user_id=demo_id('customer'))
        assignments = db.table('user_station_assignments')
        if not session.execute(select(assignments).where(assignments.c.user_id == demo_id('technician'),
                               assignments.c.station_id == demo_id('S01'))).first():
            session.execute(insert(assignments).values(user_id=demo_id('technician'), station_id=demo_id('S01')))

        # Raw simulation samples only. Never fabricate accepted/processed physical evidence,
        # heartbeat, door projections or lifecycle. Re-running never refreshes a sample.
        samples = [(2, 80, 80, 40, []), (3, 79, 90, 25, []), (4, 90, 79, 25, []),
                   (5, 90, 90, 41, []), (6, None, None, None, [])]
        for code in ('S01', 'S02'):
            for slot, soc, soh, temperature, faults in samples:
                identity = demo_id(f'f3:sample:{code}:{slot}')
                readings = db.table('battery_telemetry')
                if session.execute(select(readings.c.id).where(
                    readings.c.battery_id == demo_id(f'{code}:battery:{slot}'),
                    readings.c.id != demo_id(f'f3:reading:{code}:{slot}'))).first():
                    continue  # Never put a new unverified sample ahead of existing device/user history.
                measured = utcnow()
                payload = {'battery_id': str(demo_id(f'{code}:battery:{slot}')), 'soc': soc, 'soh': soh,
                           'temperature_c': temperature, 'fault_codes': faults}
                BMSPayload.model_validate(payload)
                add('device_events', identity, device_id=demo_id('device:' + code), boot_id=demo_id('f3:unverified-boot'),
                    seq=slot, kind='TELEMETRY', compartment_id=demo_id(f'{code}:slot:{slot}'), observed_at=measured,
                    received_at=measured, payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                    payload=payload, accepted=False, processing_error='SIMULATION_SEED_UNVERIFIED')
                events = db.table('device_events')
                # Preserve the event's original timestamp even if a previous seed stopped between inserts.
                received = session.scalar(select(events.c.received_at).where(events.c.id == identity))
                add('battery_telemetry', demo_id(f'f3:reading:{code}:{slot}'), event_id=identity,
                    battery_id=demo_id(f'{code}:battery:{slot}'), soc=soc, soh=soh, temperature_c=temperature,
                    fault_codes=faults, measured_at=received, received_at=received, quality_ok=False)


def main():
    settings = Settings(os.environ['MIGRATION_DATABASE_URL'], os.getenv('DATABASE_SCHEMA', 'doi_pin'))
    db = Database(settings)
    seed(db, {name: os.environ[f'DEMO_{name.upper()}_PASSWORD'] for name in ('admin', 'customer', 'technician')},
         {code: os.environ[f'DEMO_DEVICE_KEY_{code}'] for code in ('S01', 'S02')})
    db.engine.dispose()
    print('Demo seed ready: 3 roles, 2 stations, 12 slots, 11 batteries; 10 unverified BMS samples; no physical evidence fabricated')


if __name__ == '__main__':
    main()
