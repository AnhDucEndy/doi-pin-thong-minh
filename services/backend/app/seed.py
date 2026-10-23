"""Idempotent demo seed. Never reset passwords, locations or existing policy revisions."""
import hashlib
import os
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import insert, select
from app.config import ROOT, Settings, approved_policy
from app.domain.identity import digest, hasher
from app.infrastructure.db import Database, advisory_lock


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


def main():
    settings = Settings(os.environ['MIGRATION_DATABASE_URL'], os.getenv('DATABASE_SCHEMA', 'doi_pin'))
    db = Database(settings)
    seed(db, {name: os.environ[f'DEMO_{name.upper()}_PASSWORD'] for name in ('admin', 'customer', 'technician')},
         {code: os.environ[f'DEMO_DEVICE_KEY_{code}'] for code in ('S01', 'S02')})
    db.engine.dispose()
    print('Demo seed ready: 3 roles, 2 stations, 12 blocked/unknown slots, 11 located batteries; no telemetry fabricated')


if __name__ == '__main__':
    main()
