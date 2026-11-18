"""Independent B1a shared-caller review. Expected RBAC comes from assigned scope.

No production hooks, fabricated physical proof, clocks or financial mutations.
Every fixture has its own retained PostgreSQL schema.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, text

from app.application import assets
from app.config import ROOT
from app.main import create_app
from app.seed import demo_id
from test_phase1 import headers
from test_phase2 import action
from test_phase5 import race_environment, login
from test_phase8b_b1a_transactions import waiters


def facts(db):
    with db.sessions() as s:
        t=db.table('compartments')
        slot=dict(s.execute(select(t).where(t.c.id==demo_id('S01:slot:1'))).mappings().one())
        tables=('payments','refunds','refund_attempts','outbox_messages','resource_reservations','batteries')
        counts={n:s.scalar(select(func.count()).select_from(db.table(n))) for n in tables}
        a=db.table('audit_events')
        audit=[dict(r) for r in s.execute(select(a.c.id,a.c.action,a.c.actor_id,a.c.before_data,a.c.after_data).where(
            a.c.aggregate_id==slot['id'])).mappings()]
        return {'slot':slot,'counts':counts,'slot_audit':audit}


def test_independent_pre_revoked_scope_is_rejected(race_environment):
    env=race_environment
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin')
        revoked=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',
            headers=headers(admin),json={'station_ids':[]})
        assert revoked.status_code==200
        before=facts(env['seed_db'])
        response=action(http,tech)
        assert (response.status_code,response.json()['code'])==(403,'STATION_FORBIDDEN')
        assert facts(env['seed_db'])==before


@pytest.mark.parametrize('boundary',['station','compartment'])
def test_independent_assignment_revoke_during_asset_lock_wait(race_environment,boundary):
    env=race_environment;db=env['seed_db']
    with TestClient(create_app(env['settings'])) as http:
        tech=login(http,env,'technician');admin=login(http,env,'admin')
        assert http.get(f'/v1/stations/{demo_id("S01")}/compartments',headers=tech).status_code==200
        # Approved seed may be BLOCKED until fresh observation. Both ACTIVE and
        # BLOCKED are valid SET_MAINTENANCE sources in the current contract.
        # No fixture state/proof UPDATE is needed to exercise the guarded action.
        before=facts(db);assert before['slot']['service_state'] in ('ACTIVE','BLOCKED')
        with db.sessions() as held,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            if boundary=='station':assets.station_lock(held,db,demo_id('S01'))
            else:assets.get_row(held,db,'compartments',demo_id('S01:slot:1'),lock=True)
            holder=held.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(action,http,tech)
                try:
                    diagnostic=waiters(observer,holder,1)
                    # This is a real Admin endpoint. No direct assignment/auth data UPDATE.
                    revoked=http.put(f'/v1/users/{demo_id("technician")}/station-assignments',
                        headers=headers(admin),json={'station_ids':[]})
                    assert revoked.status_code==200,revoked.text
                    scope=http.get(f'/v1/stations/{demo_id("S01")}/compartments',headers=tech)
                    assert (scope.status_code,scope.json()['code'])==(403,'STATION_FORBIDDEN')
                    committed_at=observer.scalar(text('select clock_timestamp()'))
                    assignment_rows=observer.scalar(text('select count(*) from user_station_assignments where user_id=:id'),{'id':demo_id('technician')})
                    assert assignment_rows==0
                    # Third observable operation after revoke: an authorized
                    # Admin still sees the OLD committed compartment state.
                    # There was no durable acceptance/state change that could
                    # legitimately linearize this asset mutation before revoke.
                    read=http.get(f'/v1/stations/{demo_id("S01")}/compartments',headers=admin)
                    assert read.status_code==200
                    visible=next(x for x in read.json()['items'] if x['id']==str(before['slot']['id']))
                    assert visible['service_state']==before['slot']['service_state']
                    assert visible['version']==before['slot']['version']
                finally:held.rollback()
                response=pending.result(timeout=10)
        after=facts(db)
        result={'boundary':boundary,'schema':env['settings'].schema,'holder_pid':holder,'blocked_sessions':diagnostic,
            'revocation_http':revoked.status_code,'revocation_commit_observed_at':committed_at,
            'current_scope_http':scope.status_code,'assignment_rows_after_commit':assignment_rows,
            'admin_read_after_revoke_http':read.status_code,'admin_observed_slot_before_release':visible,
            'mutation_http':response.status_code,'mutation_body':response.json(),
            'before':before,'after':after,'two_os_api_processes':False,'physical_or_financial_proof_created':False}
        path=ROOT/'docs/PHASE8B_TESTS'/f'independent_scope_{boundary}_{uuid4().hex}.json'
        path.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
        # Independent expected contract: assignment revoked before effective
        # mutation decision must refuse, without slot version/success audit.
        assert response.status_code==403,result
        assert response.json()['code']=='STATION_FORBIDDEN',result
        assert after==before,result
