"""Deterministic real PG connections; same OS TestClients, not two OS servers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import subprocess
from time import monotonic
from threading import Event
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.exc import DBAPIError

from app.application import assets
from app.config import ROOT
from app.main import create_app
from test_phase1 import headers
from test_phase5 import race_environment, login
from test_phase6 import book, consent, outcome, payment
from app.workers import payment as payment_worker
from test_phase8b_b1a import protected, post


def waiters(observer, holder, count):
    deadline=monotonic()+3
    while monotonic()<deadline:
        rows=observer.execute(text('select pid,pg_blocking_pids(pid) as blockers,wait_event from pg_stat_activity where cardinality(pg_blocking_pids(pid))>0')).mappings().all()
        # Include the idempotency waiter behind a station waiter for same-key requests.
        direct={r['pid'] for r in rows if holder in r['blockers']}
        relevant=[dict(r) for r in rows if r['pid'] in direct or direct.intersection(r['blockers'])]
        if len(relevant)>=count:return relevant
        Event().wait(.02)  # bounded diagnostic poll, not a timing-based race assertion
    pytest.fail('Expected PostgreSQL lock wait was not observed')


@pytest.mark.parametrize('same_key',[False,True])
def test_station_serializes_concurrent_refusal(race_environment,same_key):
    env=race_environment;db=env['seed_db'];key=uuid4()
    with TestClient(create_app(env['settings'])) as http:
        customer=login(http,env);admin=login(http,env,'admin')
        swap=book(http,env,customer,db);assert consent(http,customer,swap).status_code==202
        payment_worker.tick(db,transport=outcome);p=payment(http,customer,swap);before=protected(db)
        with db.sessions() as held, env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,UUID(swap['station_id']))
            holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(post,http,admin,p,key if same_key else uuid4()) for _ in range(2)]
                try:diagnostic=waiters(observer,holder,2)
                finally:held.rollback()
                replies=[f.result(timeout=10) for f in futures]
        assert all((r.status_code,r.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED') for r in replies)
        assert protected(db)==before
        path=ROOT/'docs/PHASE8B_TESTS'/f'lock_{same_key}_{uuid4().hex}.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'schema':env['settings'].schema,'holder_pid':holder,'waiters':diagnostic,
            'http':[(r.status_code,r.json()['code']) for r in replies],'business_state_unchanged':True}),encoding='utf8')


def test_logout_commits_during_station_wait_then_refuses(race_environment):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        customer=login(http,env);admin=login(http,env,'admin')
        swap=book(http,env,customer,db);assert consent(http,customer,swap).status_code==202
        payment_worker.tick(db,transport=outcome);p=payment(http,customer,swap)
        with db.sessions() as held, env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            assets.station_lock(held,db,UUID(swap['station_id']));holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(post,http,admin,p)
                try:
                    diagnostic=waiters(observer,holder,1)
                    logout=http.post('/v1/auth/logout',headers=headers(admin));assert logout.status_code==200
                    assert http.get('/v1/me',headers=admin).status_code==401
                    before=protected(db)  # excludes expected logout mutation from the refusal comparison
                finally:held.rollback()
                response=future.result(timeout=10)
        assert (response.status_code,response.json()['code'])==(401,'SESSION_REVOKED')
        assert protected(db)==before


def test_0008_to_0009_preserves_historical_refund_and_no_backfill(environment,monkeypatch):
    # Storage-only migration fixture; no physical evidence or eligibility claim.
    schema='b1a_upgrade_'+uuid4().hex[:12];monkeypatch.setenv('DATABASE_SCHEMA',schema)
    subprocess.run([os.sys.executable,str(ROOT/'tools/provision_database.py'),'roles'],check=True)
    config=Config(str(ROOT/'services/backend/alembic.ini'));command.upgrade(config,'0008_recovery_reconciliation')
    engine=create_engine(os.environ['MIGRATION_DATABASE_URL'],hide_parameters=True,
        connect_args={'options':f'-csearch_path={schema},public'})
    ids={k:uuid4() for k in ('user','admin','station','policy','qr','swap','payment','refund','key')}
    with engine.begin() as c:
        c.execute(text("INSERT INTO users(id,username,password_hash,role) VALUES (:user,'migration-only','not-login','CUSTOMER'),(:admin,'migration-admin','not-login','ADMIN')"),ids)
        # Reuse the approved immutable policy and a station from the seeded schema.
        old=environment['settings'].schema
        c.execute(text(f'INSERT INTO demo_policies SELECT * FROM {old}.demo_policies'))
        ids['policy']=c.scalar(text('select id from demo_policies limit 1'))
        # Enum types are schema-local; copy only immutable text/UUID station
        # fields and let this target schema apply its own state defaults.
        c.execute(text(f'INSERT INTO stations(id,code,name,address) SELECT id,code,name,address FROM {old}.stations'))
        ids['station']=c.scalar(text('select id from stations limit 1'))
        c.execute(text("INSERT INTO qr_challenges(id,user_id,station_id,token_hash,expires_at) VALUES (:qr,:user,:station,'migration-only',now())"),ids)
        c.execute(text("INSERT INTO swap_transactions(id,customer_id,station_id,verified_via,qr_challenge_id,policy_id,policy_snapshot) VALUES (:swap,:user,:station,'QR',:qr,:policy,'{}')"),ids)
        c.execute(text("INSERT INTO payments(id,swap_id,provider_key,amount_minor,state,verified_at,provider_reference) VALUES (:payment,:swap,:key,9000,'SUCCEEDED',now(),'migration-charge')"),ids)
        c.execute(text("INSERT INTO refunds(id,payment_id,requested_by,provider_key,amount_minor,reason) VALUES (:refund,:payment,:admin,:key,9000,'migration storage')"),ids)
        before=dict(c.execute(text('select * from refunds')).mappings().one())
    command.upgrade(config,'head');command.upgrade(config,'head')
    with engine.connect() as c:
        assert dict(c.execute(text('select * from refunds')).mappings().one())==before
        assert c.scalar(text('select count(*) from refund_attempts'))==0
        assert c.scalar(text('select count(*) from refund_eligibility_certificates'))==0
    engine.dispose()  # schema retained; never DROP or data cleanup


def test_clean_install_direct_to_head(environment,monkeypatch):
    schema='b1a_clean_'+uuid4().hex[:12];monkeypatch.setenv('DATABASE_SCHEMA',schema)
    subprocess.run([os.sys.executable,str(ROOT/'tools/provision_database.py'),'roles'],check=True)
    config=Config(str(ROOT/'services/backend/alembic.ini'));command.upgrade(config,'head')
    engine=create_engine(os.environ['MIGRATION_DATABASE_URL'],hide_parameters=True,
        connect_args={'options':f'-csearch_path={schema},public'})
    with engine.connect() as c:
        assert c.scalar(text('select version_num from alembic_version'))=='0010_no_delivery_eligibility'
        assert c.scalar(text('select count(*) from refunds'))==0
        assert c.scalar(text('select count(*) from refund_retry_permissions'))==0
        assert c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'INSERT')"),{'n':schema+'.refund_attempts'})
        assert c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'INSERT')"),{'n':schema+'.refund_eligibility_certificates'})
        assert not c.scalar(text("select has_table_privilege('doi_pin_runtime',:n,'UPDATE')"),{'n':schema+'.refund_eligibility_certificates'})
    engine.dispose()
