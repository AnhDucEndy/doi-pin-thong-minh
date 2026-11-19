"""Native PostgreSQL storage checks; inserted rows below are NOT physical proof.

No SQL sets NO, settled custody or Payment SUCCEEDED. Certificate issuance
positives must use the later authenticated simulator/three-source workflow.
"""
from datetime import timedelta
import os
import subprocess
import sys
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, insert, select, text, update, delete
from sqlalchemy.exc import DBAPIError

from app.application.identity import utcnow
from app.config import ROOT
from app.domain.recovery import canonical_hash
from app.seed import demo_id
from test_phase6 import book

TABLES = ('refund_eligibility_certificates', 'refund_certificate_redemptions',
          'refund_certificate_revocations')


def test_new_head_grants_constraints_and_no_backfill(environment):
    schema = environment['settings'].schema
    with environment['owner'].connect() as c:
        assert c.scalar(text('select version_num from alembic_version')) == '0010_no_delivery_eligibility'
        for name in TABLES:
            qualified = schema+'.'+name
            for privilege in ('SELECT', 'INSERT'):
                assert c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,:p)"),
                                {'n': qualified, 'p': privilege})
            for privilege in ('UPDATE', 'DELETE'):
                assert not c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,:p)"),
                                    {'n': qualified, 'p': privilege})
            assert c.scalar(text('select count(*) from '+name)) == 0
        assert c.scalar(text('select count(*) from recovery_operations')) == 0
        assert c.scalar(text('select count(*) from recovery_attestations')) == 0
        for column in ('issued_by', 'issuer_session_id'):
            assert c.scalar(text("select count(*) from information_schema.columns where table_schema=:s "
                                 "and table_name='refund_eligibility_certificates' and column_name=:c"),
                            {'s':schema, 'c':column}) == 1
        # Historical stage/append-only triggers remain, no third proof shortcut.
        assert c.scalar(text("select count(*) from pg_trigger where tgrelid=to_regclass(:n) "
                             "and not tgisinternal"), {'n': schema+'.recovery_attestations'}) == 2


def operation_fixture(client, environment, auth):
    swap = book(client, environment, auth('customer'))
    db = client.app.state.db
    with db.sessions.begin() as s:
        row = dict(s.execute(select(db.table('swap_transactions')).where(
            db.table('swap_transactions').c.id == UUID(swap['id']))).mappings().one())
        new = s.execute(select(db.table('batteries')).where(
            db.table('batteries').c.id == row['new_battery_id'])).mappings().one()
        device = s.execute(select(db.table('devices')).where(
            db.table('devices').c.station_id == row['station_id'])).mappings().one()
        case_id, identity, now = uuid4(), uuid4(), utcnow()
        # Storage-only OPEN/UNKNOWN case. No physical conclusion is inserted.
        s.execute(insert(db.table('recovery_cases')).values(
            id=case_id, swap_id=row['id'], resolution_note='STORAGE_CONSTRAINT_FIXTURE'))
        ctx = jsonable_encoder(dict(protocol_version='0.3',purpose='VERIFY_NO_DELIVERY',
            operation_id=identity,case_id=case_id,swap_id=row['id'],station_id=row['station_id'],
            device_id=device['id'],customer_id=row['customer_id'],created_by=demo_id('technician'),
            new_battery_id=new['id'],expected_serial=new['serial'],
            supply_compartment_id=row['supply_compartment_id'],
            return_compartment_id=row['return_compartment_id'],base_case_version=1,
            base_swap_version=row['version'],created_at=now,expires_at=now+timedelta(seconds=120)))
        hashed = canonical_hash(ctx)
        ctx['context_hash'] = hashed
        values = dict(id=identity,protocol_version='0.3',case_id=case_id,swap_id=row['id'],
            station_id=row['station_id'],customer_id=row['customer_id'],pin_id=new['id'],
            expected_serial=new['serial'],purpose='VERIFY_NO_DELIVERY',context=ctx,
            context_hash=hashed,created_by=demo_id('technician'),created_at=now,
            expires_at=now+timedelta(seconds=120),base_case_version=1,base_swap_version=row['version'])
    return db, row, values


@pytest.mark.parametrize('changes', [
    {'protocol_version':None}, {'protocol_version':'0.2'},
    {'purpose':'VERIFY_OLD_POSSESSION'}, {'pin_id':None}, {'expected_serial':'wrong'},
    {'customer_id':demo_id('technician')}, {'station_id':demo_id('S02')},
])
def test_operation_protocol_scope_binding_is_enforced(client, environment, auth, changes):
    db, swap, values = operation_fixture(client, environment, auth)
    with db.sessions.begin() as s:
        with pytest.raises(DBAPIError):
            with s.begin_nested():
                s.execute(insert(db.table('recovery_operations')).values(**{**values, **changes}))
        assert s.scalar(select(db.table('recovery_operations').c.id)) is None
        case = s.execute(select(db.table('recovery_cases'))).mappings().one()
        assert case['new_pin_delivered']=='UNKNOWN' and case['old_pin_settled'] is False


def test_storage_accepts_readonly_context_but_no_cross_stage_proof(client, environment, auth):
    db, swap, values = operation_fixture(client, environment, auth)
    with db.sessions.begin() as s:
        s.execute(insert(db.table('recovery_operations')).values(**values))
        table = db.table('recovery_attestations')
        for stage in ('LEGACY','PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT','RECONCILIATION_INSPECTION'):
            with pytest.raises(DBAPIError):
                with s.begin_nested():
                    s.execute(insert(table).values(id=uuid4(),event_id=uuid4(),
                        operation_id=values['id'],stage=stage,source_kind='TECHNICIAN',
                        actor_user_id=demo_id('technician'),observed_at=utcnow(),received_at=utcnow(),
                        payload={'context_hash':values['context_hash']},payload_hash='0'*64))
        assert s.scalar(select(table.c.id)) is None
        # Runtime has no mutation privilege on these retained evidence tables.
        for name in TABLES:
            with pytest.raises(DBAPIError):
                with s.begin_nested():
                    s.execute(delete(db.table(name)))
            with pytest.raises(DBAPIError):
                with s.begin_nested():
                    key = 'validated_at' if name=='refund_eligibility_certificates' else (
                        'redeemed_at' if name=='refund_certificate_redemptions' else 'revoked_at')
                    s.execute(update(db.table(name)).values(**{key:utcnow()}))


def test_0009_upgrade_preserves_marker_and_old_grants(environment, monkeypatch):
    schema='b1b_upgrade_'+uuid4().hex[:12]
    monkeypatch.setenv('DATABASE_SCHEMA',schema)
    subprocess.run([sys.executable,str(ROOT/'tools/provision_database.py'),'roles'],check=True)
    config=Config(str(ROOT/'services/backend/alembic.ini'))
    command.upgrade(config,'0009_refund_foundation')
    engine=create_engine(os.environ['MIGRATION_DATABASE_URL'],hide_parameters=True,
                         connect_args={'options':f'-csearch_path={schema},public'})
    marker=uuid4()
    with engine.begin() as c:
        c.execute(text("insert into users(id,username,password_hash,role) "
                       "values(:id,'b1b-migration-marker','not-a-login-account','CUSTOMER')"),{'id':marker})
        before=dict(c.execute(text('select * from users where id=:id'),{'id':marker}).mappings().one())
        for name in TABLES[:2]:
            assert not c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'INSERT')"),
                                {'n':schema+'.'+name})
    command.upgrade(config,'head');command.upgrade(config,'head')
    with engine.connect() as c:
        assert dict(c.execute(text('select * from users where id=:id'),{'id':marker}).mappings().one())==before
        for name in ('recovery_operations','recovery_attestations',*TABLES):
            assert c.scalar(text('select count(*) from '+name))==0
        assert c.scalar(text('select version_num from alembic_version'))=='0010_no_delivery_eligibility'
    engine.dispose()  # Schema deliberately retained.
