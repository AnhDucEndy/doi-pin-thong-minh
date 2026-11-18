"""Preserved deterministic B1a/AssignStations FK lock graph probe.

The historical operation below is a storage-only lock participant, never
accepted physical evidence, eligibility or a custody update.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, event, insert, select, text
from sqlalchemy.exc import DBAPIError

from app.application.identity import utcnow
from app.config import ROOT
from app.domain.recovery import canonical_hash
from app.main import create_app
from app.seed import demo_id
from test_phase5 import race_environment, login
from test_phase6 import book, consent, outcome, payment
from app.workers import payment as payment_worker
from test_phase8b_b1a import post, protected
from test_phase8b_b1a_transactions import waiters


def test_refund_vs_assignment_fk_has_no_lock_cycle(race_environment):
    env=race_environment;db=env['seed_db'];now=utcnow()
    with TestClient(create_app(env['settings'])) as http:
        customer=login(http,env);admin=login(http,env,'admin')
        swap=book(http,env,customer,db);assert consent(http,customer,swap).status_code==202
        payment_worker.tick(db,transport=outcome);p=payment(http,customer,swap)
        case_id,op_id=uuid4(),uuid4()
        with db.sessions.begin() as s:
            s.execute(insert(db.table('recovery_cases')).values(id=case_id,swap_id=UUID(swap['id'])))
            s.execute(insert(db.table('recovery_operations')).values(id=op_id,case_id=case_id,
                swap_id=UUID(swap['id']),station_id=UUID(swap['station_id']),customer_id=demo_id('customer'),
                pin_id=UUID(swap['old_battery_id']),expected_serial='storage-only-not-proof',purpose='VERIFY_OLD_POSSESSION',
                context={},context_hash=canonical_hash({}),created_by=demo_id('technician'),
                created_at=now,expires_at=now+timedelta(seconds=120),consumed_at=now,
                base_case_version=1,base_swap_version=1))
        before=protected(db)
        assignment_error=None; backend_errors=[]
        def database_error(context):
            original=context.original_exception
            backend_errors.append({'sqlstate':getattr(original,'sqlstate',None),
                'primary':getattr(getattr(original,'diag',None),'message_primary',None)})
        event.listen(http.app.state.db.engine,'handle_error',database_error)
        with db.sessions() as assignment,env['owner'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
            # Same row lock and DELETE/INSERT/FK sequence as AssignStations.
            users=db.table('users');assignments=db.table('user_station_assignments')
            assignment.execute(select(users.c.id).where(users.c.id==demo_id('technician')).with_for_update()).one()
            holder=assignment.scalar(text('select pg_backend_pid()'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(post,http,admin,p)
                try:
                    diagnostic=waiters(observer,holder,1)
                    assignment.execute(delete(assignments).where(assignments.c.user_id==demo_id('technician')))
                    try:
                        assignment.execute(insert(assignments).values(user_id=demo_id('technician'),station_id=UUID(swap['station_id'])))
                    except DBAPIError as exc:
                        assignment_error=getattr(exc.orig,'sqlstate',None)
                finally:assignment.rollback()
                response=future.result(timeout=10)
        event.remove(http.app.state.db.engine,'handle_error',database_error)
        after=protected(db)
        with db.sessions() as s:
            case=dict(s.execute(select(db.table('recovery_cases')).where(db.table('recovery_cases').c.id==case_id)).mappings().one())
        result={'schema':env['settings'].schema,'assignment_pg_pid':holder,'observed_waiters':diagnostic,
            'assignment_sqlstate':assignment_error,'refund_http_status':response.status_code,
            'refund_business_code':response.json()['code'],'protected_state_unchanged':before==after,
            'backend_database_errors':backend_errors,
            'case_version':case['version'],'new_pin_delivered':case['new_pin_delivered'],
            'old_pin_settled':case['old_pin_settled'],'fixture_kind':'storage-only history, no accepted proof',
            'two_os_backends':False}
        path=ROOT/'docs/PHASE8B_TESTS'/('lock_graph_'+uuid4().hex+'.json')
        path.write_text(json.dumps(result,indent=2),encoding='utf8')
        assert before==after
        assert case['version']==1 and case['new_pin_delivered']=='UNKNOWN' and not case['old_pin_settled']
        assert assignment_error is None, result
        assert (response.status_code,response.json()['code'])==(422,'REFUND_EVIDENCE_REQUIRED'),result
