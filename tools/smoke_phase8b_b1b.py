"""Isolated real-process B1b acceptance tooling; never imported by production.

Actual APIs, device/payment workers, command Simulator and charge mock each run
as independent OS processes. Refund jobs remain inert. Retain every schema,
ledger and artifact; stop only child processes created by this invocation.
"""
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import UUID,uuid4
from xml.etree.ElementTree import Element,SubElement,ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services/backend'),str(ROOT/'tests'),str(ROOT/'tools')]
import httpx
from sqlalchemy import create_engine,select,text
from app.config import Settings
from app.seed import demo_id
from app.domain.recovery import canonical_hash
from conftest import environment


def app():
    """Explicit test factory only. Production imports neither this nor its hooks."""
    from app.main import create_app
    from app.application import refund_audit
    gate=Path(os.environ['B1B_GATE_DIR']).resolve()
    if not gate.is_relative_to(ROOT/'.cache'):raise RuntimeError('TEST_GATE_WORKSPACE_REQUIRED')
    mode=os.environ['B1B_GATE_MODE'];instance=create_app()
    if mode=='postcommit-crash':
        @instance.middleware('http')
        async def lose_response(request,call_next):
            response=await call_next(request)
            if request.url.path.endswith('/refund') and request.method=='POST' and response.status_code==202:
                (gate/'commit-ready.json').write_text(json.dumps({'os_pid':os.getpid()}),encoding='utf8')
                os._exit(87)
            return response
    elif mode in ('certificate-wait','confirmation-wait'):
        from app.application import no_delivery
        original=no_delivery.audit
        def after_certificate(session,db,actor,case,action,*args,**kwargs):
            original(session,db,actor,case,action,*args,**kwargs)
            if (mode=='certificate-wait' and action=='ND_CERTIFICATE_ISSUED') or (mode=='confirmation-wait' and action=='ND_HUMAN_ATTESTED' and actor.get('role')=='CUSTOMER'):
                (gate/'certificate-ready.json').write_text(json.dumps({'os_pid':os.getpid(),
                    'pg_pid':session.scalar(text('select pg_backend_pid()'))}),encoding='utf8')
                wait(lambda:(gate/'certificate-release').exists(),'certificate transaction barrier',8)
        no_delivery.audit=after_certificate
    else:
        original=refund_audit.request_record
        def after_audit(session,*args,**kwargs):
            original(session,*args,**kwargs)
            (gate/'audit-ready.json').write_text(json.dumps({'os_pid':os.getpid(),
                'pg_pid':session.scalar(text('select pg_backend_pid()'))}),encoding='utf8')
            wait(lambda:(gate/'release').exists(),'test transaction gate',8)
        refund_audit.request_record=after_audit
    return instance


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        return probe.getsockname()[1]


def wait(condition,description,seconds=25):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        result=condition()
        if result:return result
        time.sleep(.08)  # Bounded observation poll, not race/timestamp manipulation.
    raise RuntimeError('WAIT_TIMEOUT: '+description)


def crash_simulator():
    """Test-only actual process barrier; no production fault switches."""
    from simulators.device.main import Simulator
    runtime=Path(os.environ['B1B_SOURCE_RUNTIME']).resolve()
    if not runtime.is_relative_to(ROOT/'.cache'):raise RuntimeError('TEST_RUNTIME_REQUIRED')
    sim=Simulator('S01',os.environ['DEMO_DEVICE_KEY_S01'],base_url=os.environ['B1B_SOURCE_URL'],
                  ledger=runtime/'ledgers/S01.sqlite3',scenario='physical')
    original=sim._execute_command;stage=os.environ['B1B_SOURCE_STAGE']
    def boundary(command,body):
        result=original(command,body) if stage=='after' else None
        (runtime/'source-ready.json').write_text(json.dumps({'os_pid':os.getpid(),'stage':stage,
            'command_id':command['id'],'model_result':result}),encoding='utf8')
        wait(lambda:(runtime/'source-release').exists(),'actual model transaction crash barrier',10)
        return original(command,body) if stage=='before' else result
    sim._execute_command=boundary
    try:
        while True:sim.cycle();time.sleep(.2)
    finally:sim.close()


def main():
    scenario=sys.argv[sys.argv.index('--scenario')+1] if '--scenario' in sys.argv else 'A'
    allowed={'A','B','B-kill-before','B-kill-after','C-reject','C-expiry','E-inbox','D-decide-same','D-decide-other','D-confirm-wins','D-reject-wins','E-intent-first','D-freshness-wait','D-precommit','D-postcommit','D-same-key','D-other-key','D-assignment-first','D-assignment-after',
             'D-witness-logout-first','D-witness-logout-after','D-caller-logout-first','D-caller-logout-after',
             'D-user-state-first','D-user-state-after','D-role-first','D-role-after'}
    if scenario not in allowed:raise ValueError('Unsupported scenario')
    out=Path(os.environ['B1B_REPORT_DIR']).resolve()
    runtime=ROOT/'.cache'/('b1b_real_'+uuid4().hex)
    runtime.mkdir();ledger=runtime/'ledgers';ledger.mkdir()
    reports=[];checks=[];children=[];logs=[]
    previous_schema=os.environ.get('DATABASE_SCHEMA')
    factory=environment.__wrapped__();fixture=next(factory);db=fixture['seed_db']
    # pg_stat_activity redacts other-role wait columns from the migrator. Use
    # the existing administrative account read-only for diagnostics only; never
    # grant runtime/migrator broader privileges merely to satisfy a probe.
    observer_engine=create_engine(os.environ['DATABASE_ADMIN_URL'],hide_parameters=True,
        connect_args={'connect_timeout':5,'options':'-cdefault_transaction_read_only=on'})
    api_ports=(free_port(),free_port());mock_port=free_port()
    if len(set((*api_ports,mock_port)))!=3:raise RuntimeError('PORT_ALLOCATION_COLLISION')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'services/backend')+os.pathsep+str(ROOT),PYTHONIOENCODING='utf8',
        __PYVENV_LAUNCHER__=sys.executable,
        DATABASE_SCHEMA=fixture['settings'].schema,PAYMENT_MOCK_URL='http://127.0.0.1:'+str(mock_port),
        PAYMENT_LEDGER_PATH=str(ledger/'charge.sqlite3'),PAYMENT_SERVICE_KEY=secrets.token_urlsafe(36),
        PAYMENT_CALLBACK_KEY=secrets.token_urlsafe(36),
        **{'DEMO_DEVICE_KEY_'+k:v for k,v in fixture['keys'].items()})
    private={'schema':fixture['settings'].schema,'passwords':fixture['passwords'],'keys':fixture['keys']}
    (runtime/'private.json').write_text(json.dumps(private),encoding='utf8')
    def launch(args,name,**extra):
        log=(runtime/(name+'.log')).open('x',encoding='utf8');logs.append(log)
        # Windows venv redirectors have a different PID from their interpreter.
        # The verified launcher context retains venv/site-packages while this
        # direct interpreter PID is the actual server/worker/Simulator we own.
        proc=subprocess.Popen([sys._base_executable,*args],cwd=ROOT,env={**env,**extra},stdout=log,stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(proc);return proc
    def stop(proc):
        if proc.poll() is None:proc.terminate();proc.wait(timeout=20)
    def read(name,**values):
        table=db.table(name)
        with db.sessions() as s:
            return [dict(r) for r in s.execute(select(table).where(*[table.c[k]==v for k,v in values.items()])).mappings()]
    def safe_request(client,method,path,*,expected,**kwargs):
        response=getattr(client,method.lower())(path,**kwargs)
        try:code=response.json().get('code')
        except (ValueError,AttributeError):code=None
        reports.append({'method':method.upper(),'path':path,'status':response.status_code,'business_code':code})
        if response.status_code!=expected:
            raise RuntimeError(f'HTTP_EXPECTATION: {method} {path}: {response.status_code}/{code}')
        return response.json()
    def check(name,condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition:raise AssertionError(name)
    try:
        gate_mode=('postcommit-crash' if scenario=='D-postcommit' else 'audit-wait')
        if scenario in ('D-decide-same','D-decide-other'):gate_mode='certificate-wait'
        if scenario in ('D-confirm-wins','D-reject-wins'):gate_mode='confirmation-wait'
        gated=scenario in {'D-confirm-wins','D-reject-wins','E-intent-first','D-decide-same','D-decide-other','D-precommit','D-postcommit','D-same-key','D-other-key'} or scenario.endswith('-after')
        apis=[launch(['-m','uvicorn','tools.smoke_phase8b_b1b:app' if i==0 and gated else 'app.main:create_app',
                     '--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],
                     'api'+str(i),PGAPPNAME='b1b-real-'+runtime.name+'-api'+str(i),
                     B1B_GATE_DIR=str(runtime),B1B_GATE_MODE=gate_mode) for i,port in enumerate(api_ports)]
        provider=launch(['-m','simulators.payment.main','--port',str(mock_port),'--scenario','success'],'charge-mock')
        with httpx.Client(base_url='http://127.0.0.1:'+str(api_ports[0]),timeout=20,trust_env=False) as first, \
             httpx.Client(base_url='http://127.0.0.1:'+str(api_ports[1]),timeout=20,trust_env=False) as second:
            def ready(client,proc):
                if proc.poll() is not None:raise RuntimeError('OWNED_API_EXITED')
                try:return client.get('/health').status_code==200
                except httpx.HTTPError:return False
            wait(lambda:ready(first,apis[0]) and ready(second,apis[1]),'both API listeners')
            worker=launch(['-m','app.workers.device'],'device-worker',PGAPPNAME='b1b-real-'+runtime.name+'-device')
            charge_worker=launch(['-m','app.workers.payment'],'charge-worker')
            def simulator(name,operation=None):
                if scenario in ('B-kill-before','B-kill-after') and name=='sim-initial':
                    return launch(['tools/smoke_phase8b_b1b.py','--source-crash-child'],name,
                        B1B_SOURCE_RUNTIME=str(runtime),B1B_SOURCE_URL=str(first.base_url).rstrip('/'),
                        B1B_SOURCE_STAGE='before' if scenario=='B-kill-before' else 'after')
                args=['-m','simulators.device.main','--station','S01','--url',str(first.base_url).rstrip('/'),
                      '--ledger-dir',str(ledger),'--scenario','crash-after-ledger' if scenario=='B' else 'nack']
                if operation:args+=['--service-operation',operation]
                return launch(args,name,SERVICE_TECHNICIAN_TOKEN=tech['Authorization'].split(' ',1)[1] if operation else '')
            sim=simulator('sim-initial')
            def login(name,client=first):
                value=safe_request(client,'POST','/v1/auth/login',expected=200,
                    json={'username':name,'password':fixture['passwords'][name]})
                return {'Authorization':'Bearer '+value['access_token']}
            tech,customer,admin=login('technician'),login('customer'),login('admin')
            def hs(actor,key=None):return {**actor,'Idempotency-Key':str(key or uuid4())}
            def current_snapshot():
                rows=read('device_events',device_id=demo_id('device:S01'),kind='SNAPSHOT')
                rows=[r for r in rows if r['accepted'] and r['processed_at']]
                return max(rows,key=lambda r:r['observed_at']) if rows else None
            snapshot=wait(current_snapshot,'actual processed Simulator snapshot')
            def quality_ready():
                readings=read('battery_telemetry',battery_id=demo_id('S01:battery:2'))
                return any(v['quality_ok'] and v['measured_at']>=snapshot['observed_at'] for v in readings)
            wait(quality_ready,'actual processed BMS')
            pin=read('batteries',id=demo_id('S01:battery:2'))[0]
            safe_request(first,'POST','/v1/batteries/'+str(pin['id'])+'/actions',expected=200,headers=hs(tech),json={
                'expected_version':pin['version'],'action':'ACTIVATE','reason':'Actual current model setup',
                'evidence_event_id':str(current_snapshot()['id'])})
            for number in (1,2):
                slot=read('compartments',id=demo_id('S01:slot:'+str(number)))[0]
                safe_request(first,'POST','/v1/compartments/'+str(slot['id'])+'/actions',expected=200,headers=hs(tech),json={
                    'expected_version':slot['version'],'action':'RESTORE','reason':'Actual current snapshot',
                    'evidence_event_id':str(current_snapshot()['id'])})
            qr=safe_request(first,'POST','/v1/qr-challenges',expected=201,headers=hs(customer),json={'station_id':str(demo_id('S01'))})
            swap=safe_request(first,'POST','/v1/device/verifications',expected=201,
                headers={'X-Device-Key':fixture['keys']['S01'],'Idempotency-Key':str(uuid4())},
                json={'method':'QR','credential':qr['qr_token']})
            swap=safe_request(first,'POST','/v1/swaps/'+swap['id']+'/reserve',expected=200,headers=hs(customer),json={'expected_version':swap['version']})
            check('Reservation is really RESERVED',swap['state']=='RESERVED')
            safe_request(first,'POST','/v1/swaps/'+swap['id']+'/consent',expected=202,headers=hs(customer),json={
                'expected_version':swap['version'],'quoted_amount_minor':swap['amount_minor'],'currency':'VND','accept':True})
            identity=UUID(swap['id'])
            if scenario in ('B-kill-before','B-kill-after'):
                ready_file=runtime/'source-ready.json'
                wait(ready_file.exists,'actual SQLite effect boundary',30)
                source_ready=json.loads(ready_file.read_text(encoding='utf8'))
                check('Controlled source process is really running',source_ready['os_pid']==sim.pid and sim.poll() is None)
                if scenario=='B-kill-after':check('Actual model writes happened before uncommitted crash',source_ready['model_result']=='EXECUTED')
                def model_rows():
                    with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                        return {n:c.execute('SELECT * FROM '+n+' ORDER BY 1').fetchall() for n in ('slots','commands','service_positions')}
                before_crash=model_rows();sim.kill();sim.wait(timeout=10)
                check('Actual kill rolls back SQLite model transaction',model_rows()==before_crash)
                (out/'source_crash.json').write_text(json.dumps({'ready':source_ready,'exit_code':sim.returncode,
                    'model_rollback_verified':True},indent=2),encoding='utf8')
                sim=simulator('sim-after-source-kill')
            wait(lambda:read('swap_transactions',id=identity)[0]['state']=='REVIEW_REQUIRED','actual NACK -> review',35)
            check('Charge really verified SUCCEEDED',read('payments',swap_id=identity)[0]['state']=='SUCCEEDED')
            check('One OPEN_RETURN with expected refusal/uncertainty',len(read('device_commands',swap_id=identity))==1 and
                  read('device_commands',swap_id=identity)[0]['state']==('UNKNOWN' if scenario.startswith('B') else 'REJECTED'))
            def protected():
                return {name:read(name,**filters) for name,filters in (
                    ('batteries',{}),('payments',{'swap_id':identity}),('resource_reservations',{'swap_id':identity}))}
            before=protected();url='/v1/swaps/'+swap['id']+'/recovery'
            case=safe_request(first,'GET',url,expected=200,headers=tech)
            case=safe_request(first,'POST',url+'/evidence',expected=200,headers=hs(tech),json={
                'protocol_version':'0.3','expected_version':case['version'],'note':'Real-process readonly inspection',
                'statement':{'kind':'BEGIN_OPERATION','purpose':'VERIFY_NO_DELIVERY'}})
            operation=case['operation']['operation_id']
            # Restart preserves the actual model and journal. It must establish
            # a new current boot before producing this operation's observation.
            stop(sim);sim=simulator('sim-inspection',operation)
            if scenario.startswith('B'):
                def fenced():
                    with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                        return c.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1
                wait(fenced,'readonly fence despite unresolved actual command')
                stop(sim)
                check('UNKNOWN never becomes a positive receipt',not read('recovery_attestations',operation_id=UUID(operation)) and not read('refund_eligibility_certificates'))
                old_boot=read('devices',id=demo_id('device:S01'))[0]['boot_id']
                sim=simulator('sim-unknown-restart')
                wait(lambda:read('devices',id=demo_id('device:S01'))[0]['boot_id']!=old_boot,'new actual boot after UNKNOWN')
                stop(sim)
                payment=read('payments',swap_id=identity)[0]
                safe_request(first,'POST','/v1/payments/'+str(payment['id'])+'/refund',expected=422,headers=hs(admin),
                    json={'expected_version':payment['version'],'reason':'UNKNOWN must remain in review'})
                check('No financial intent from UNKNOWN',not read('refunds') and not read('refund_attempts') and not read('refund_certificate_redemptions') and not read('outbox_messages',kind='REFUND'))
                check('UNKNOWN protects custody/charge/holds',protected()==before)
                with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                    check('Restart retains UNKNOWN and zero effects',c.execute('SELECT status,effects FROM commands').fetchone()==('UNKNOWN',0))
                    check('Unresolved receipt remains absent',c.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==0)
                    check('Fence survives unresolved restart',c.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1)
                (out/'real_process.json').write_text(json.dumps({'scenario':scenario,'schema':fixture['settings'].schema,
                    'runtime':runtime.name,'api_pids':[p.pid for p in apis],'checks':checks,'http':reports},indent=2),encoding='utf8')
                return 0
            def received():
                items=read('recovery_attestations',operation_id=UUID(operation),source_kind='SIMULATOR')
                return items[0] if items else None
            receipt=wait(received,'real Simulator accepted 0.3 receipt',35)
            stop(sim)
            wait(lambda:not [r for r in read('device_events',device_id=demo_id('device:S01')) if not r['processed_at']
                 and r['processing_error']!='SIMULATION_SEED_UNVERIFIED'],'worker drained actual trailing sources')
            case=safe_request(first,'GET',url,expected=200,headers=tech)
            ref={'protocol_version':'0.3','operation_id':operation,'context_hash':case['operation']['context_hash'],
                 'stage':'NO_DELIVERY_INSPECTION','receipt_id':str(receipt['id']),'receipt_hash':receipt['payload_hash']}
            case=safe_request(first,'POST',url+'/evidence',expected=200,headers=hs(tech),json={
                'protocol_version':'0.3','expected_version':case['version'],'note':'Technician independent proof',
                'statement':{**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':case['operation']['expected_serial'],'observation':'CONFIRM'}})
            if scenario in ('C-reject','C-expiry'):
                previous_context=dict(case['operation']);previous_id=operation
                if scenario=='C-reject':
                    safe_request(second,'POST',url+'/confirmations',expected=201,headers=hs(customer),json={**ref,'confirm':False})
                    case=safe_request(first,'GET',url,expected=200,headers=tech)
                    safe_request(first,'POST',url+'/evidence',expected=422,headers=hs(tech),json={
                        'protocol_version':'0.3','expected_version':case['version'],'note':'REJECT cannot be outvoted',
                        'statement':{**ref,'kind':'VERIFY_NO_DELIVERY_DECIDE'}})
                    check('REJECT never issues certificate',not read('refund_eligibility_certificates'))
                else:
                    # Keep actual telemetry running while the real 120s operation
                    # expires. No accelerated clock, modified timestamp or TTL.
                    sim=simulator('sim-expiry-clock')
                    expiry=datetime.fromisoformat(previous_context['expires_at'].replace('Z','+00:00'))
                    wait(lambda:datetime.now(timezone.utc)>=expiry,'real operation TTL',125)
                    stop(sim)
                    with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                        check('TTL never releases durable fence',c.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1)
                case=safe_request(first,'GET',url,expected=200,headers=tech)
                case=safe_request(first,'POST',url+'/evidence',expected=200,headers=hs(tech),json={
                    'protocol_version':'0.3','expected_version':case['version'],'note':'Current readonly successor',
                    'statement':{'kind':'BEGIN_OPERATION','purpose':'VERIFY_NO_DELIVERY','predecessor_id':previous_id}})
                operation=case['operation']['operation_id']
                check('Successor has immutable predecessor binding',operation!=previous_id and case['operation']['predecessor_id']==previous_id
                      and case['operation']['predecessor_context_hash']==previous_context['context_hash'])
                check('Old context/expiry are unchanged',read('recovery_operations',id=UUID(previous_id))[0]['context']==previous_context)
                sim=simulator('sim-successor-inspection',operation)
                receipt=wait(received,'new current successor receipt',35)
                stop(sim)
                wait(lambda:not [r for r in read('device_events',device_id=demo_id('device:S01')) if not r['processed_at']
                     and r['processing_error']!='SIMULATION_SEED_UNVERIFIED'],'successor trailing source processing')
                case=safe_request(first,'GET',url,expected=200,headers=tech)
                ref={'protocol_version':'0.3','operation_id':operation,'context_hash':case['operation']['context_hash'],
                     'stage':'NO_DELIVERY_INSPECTION','receipt_id':str(receipt['id']),'receipt_hash':receipt['payload_hash']}
                case=safe_request(first,'POST',url+'/evidence',expected=200,headers=hs(tech),json={
                    'protocol_version':'0.3','expected_version':case['version'],'note':'New current successor Technician proof',
                    'statement':{**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':case['operation']['expected_serial'],'observation':'CONFIRM'}})
                with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                    check('Atomic fence handover retains one active fence',c.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1
                          and c.execute('SELECT count(*) FROM recovery_station_fence').fetchone()[0]==2)
                    check('Original receipt is retained',c.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==2)
            if scenario in ('D-confirm-wins','D-reject-wins'):
                first_confirm=scenario=='D-confirm-wins'
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first_human=pool.submit(first.post,url+'/confirmations',headers=hs(customer),json={**ref,'confirm':first_confirm})
                    wait((runtime/'certificate-ready.json').exists,'actual human proof write barrier',5)
                    ready=json.loads((runtime/'certificate-ready.json').read_text())
                    check('Human barrier is actual first API PID',ready['os_pid']==apis[0].pid)
                    second_human=pool.submit(second.post,url+'/confirmations',headers=hs(customer),json={**ref,'confirm':not first_confirm})
                    with observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                        diagnostic=wait(lambda:[dict(r) for r in observer.execute(text(
                            'select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),
                            {'holder':ready['pg_pid']}).mappings()],'actual conflicting human statement lock',3)
                    (runtime/'certificate-release').write_text('release')
                    winner=first_human.result(timeout=10);loser=second_human.result(timeout=10)
                check('First human statement commits exactly once',winner.status_code==201 and winner.json()['confirmed']==first_confirm)
                check('Conflicting statement cannot overwrite winner',loser.status_code==409 and loser.json()['code']=='RECOVERY_ATTESTATION_EXISTS')
                check('One immutable Customer source',len(read('recovery_attestations',operation_id=UUID(operation),source_kind='CUSTOMER'))==1)
                (out/'human_lock.json').write_text(json.dumps({'holder':ready,'waiters':diagnostic},indent=2))
                if not first_confirm:
                    latest=safe_request(second,'GET',url,expected=200,headers=tech)
                    safe_request(second,'POST',url+'/evidence',expected=422,headers=hs(tech),json={
                        'protocol_version':'0.3','expected_version':latest['version'],'note':'REJECT wins over conflicting CONFIRM',
                        'statement':{**ref,'kind':'VERIFY_NO_DELIVERY_DECIDE'}})
                    check('REJECT winner cannot produce financial eligibility',not read('refund_eligibility_certificates') and not read('refunds'))
                    check('REJECT race preserves protected facts',protected()==before)
                    (out/'real_process.json').write_text(json.dumps({'scenario':scenario,'schema':fixture['settings'].schema,
                        'api_pids':[p.pid for p in apis],'checks':checks,'http':reports},indent=2))
                    return 0
            else:
                safe_request(second,'POST',url+'/confirmations',expected=201,headers=hs(customer),json={**ref,'confirm':True})
            case=safe_request(first,'GET',url,expected=200,headers=tech)
            decide_body={'protocol_version':'0.3','expected_version':case['version'],
                'note':'Backend evaluate current three sources','statement':{**ref,'kind':'VERIFY_NO_DELIVERY_DECIDE'}}
            if scenario in ('D-decide-same','D-decide-other'):
                decide_key=uuid4()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first_decide=pool.submit(first.post,url+'/evidence',headers=hs(tech,decide_key),json=decide_body)
                    wait((runtime/'certificate-ready.json').exists,'actual certificate write barrier',5)
                    ready=json.loads((runtime/'certificate-ready.json').read_text())
                    check('Certificate barrier is actual first API PID',ready['os_pid']==apis[0].pid)
                    next_decide=pool.submit(second.post,url+'/evidence',headers=hs(tech,decide_key if scenario=='D-decide-same' else uuid4()),json=decide_body)
                    with observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                        diagnostic=wait(lambda:[dict(r) for r in observer.execute(text(
                            'select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),
                            {'holder':ready['pg_pid']}).mappings()],'actual competing certificate lock',3)
                    check('Certificate competitor uses distinct waiting PostgreSQL PID',
                          all(r['pid']!=ready['pg_pid'] and r['wait_event_type']=='Lock' for r in diagnostic))
                    (runtime/'certificate-release').write_text('release')
                    decided=first_decide.result(timeout=10);other=next_decide.result(timeout=10)
                check('First certificate commits with valid authority',decided.status_code==200)
                check('Competing certificate request serializes',other.status_code==(200 if scenario=='D-decide-same' else 409))
                if scenario=='D-decide-same':check('Certificate replay is exact',other.json()==decided.json())
                check('One certificate and one issue audit',len(read('refund_eligibility_certificates'))==1 and
                      sum(a['action']=='ND_CERTIFICATE_ISSUED' for a in read('audit_events'))==1)
                (out/'certificate_lock.json').write_text(json.dumps({'holder':ready,'waiters':diagnostic},indent=2))
                case=decided.json()
            else:
                case=safe_request(first,'POST',url+'/evidence',expected=200,headers=hs(tech),json=decide_body)
            check('Certificate NO with old obligation still false',case['new_pin_delivered']=='NO' and not case['old_pin_settled'])
            payment=read('payments',swap_id=identity)[0];key=uuid4();body={'expected_version':payment['version'],'reason':'Real-process first refund intent'}
            refund_path='/v1/payments/'+str(payment['id'])+'/refund'
            if scenario=='D-freshness-wait':
                from app.application.assets import station_lock
                until=datetime.fromisoformat(case['certificate']['valid_until'].replace('Z','+00:00'))
                wait(lambda:(until-datetime.now(timezone.utc)).total_seconds()<2,'real proof near expiry outside locks',16)
                with db.sessions() as held,ThreadPoolExecutor(max_workers=1) as pool:
                    station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
                    fresh_at_start=datetime.now(timezone.utc)<until
                    future=pool.submit(first.post,refund_path,headers=hs(admin),json=body)
                    with observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                        diagnostic=wait(lambda:[dict(r) for r in observer.execute(text(
                            'select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),
                            {'holder':holder}).mappings()],'fresh request actually waits on station',1)
                    wait(lambda:datetime.now(timezone.utc)>until,'original freshness expires during observed lock wait',3)
                    held.rollback();refused=future.result(timeout=10)
                check('Source was fresh before actual PostgreSQL wait',fresh_at_start and bool(diagnostic))
                check('Expired proof is rechecked after lock wait',refused.status_code==422 and refused.json()['code']=='EVENT_STALE')
                check('Freshness refusal has zero financial partial writes',not read('refunds') and not read('refund_attempts')
                      and not read('refund_certificate_redemptions') and not read('outbox_messages',kind='REFUND'))
                check('Freshness refusal preserves protected facts',protected()==before)
                (out/'real_process.json').write_text(json.dumps({'scenario':scenario,'schema':fixture['settings'].schema,
                    'api_pids':[p.pid for p in apis],'checks':checks,'lock_diagnostics':diagnostic,
                    'valid_until':until.isoformat(),'http_status':refused.status_code,'business_code':refused.json()['code']},indent=2))
                return 0
            if scenario=='E-inbox':
                # Freeze only the owned worker process, never source clocks.
                stop(worker);sim=simulator('sim-pending-reboot')
                wait(lambda:any(not r['processed_at'] and r['processing_error']!='SIMULATION_SEED_UNVERIFIED'
                     for r in read('device_events',device_id=demo_id('device:S01'))),'actual unprocessed source inbox')
                until=datetime.fromisoformat(case['certificate']['valid_until'].replace('Z','+00:00'))
                check('Pending-inbox refusal tested before certificate expiry',datetime.now(timezone.utc)<until)
                safe_request(first,'POST',refund_path,expected=409,headers=hs(admin),json=body)
                check('Inbox-only source is not an accepted projection',read('recovery_cases',swap_id=identity)[0]['new_pin_delivered']=='NO'
                      and not read('refund_certificate_revocations'))
                worker=launch(['-m','app.workers.device'],'device-worker-restarted',PGAPPNAME='b1b-restarted-device')
                wait(lambda:read('refund_certificate_revocations'),'actual worker accepted reboot revocation')
                safe_request(second,'POST',refund_path,expected=422,headers=hs(admin),json=body)
                check('Accepted reboot invalidates old physical proof',read('recovery_cases',swap_id=identity)[0]['new_pin_delivered']=='UNKNOWN')
                check('No financial partials from pending/contradictory proof',not read('refunds') and not read('refund_attempts')
                      and not read('refund_certificate_redemptions') and not read('outbox_messages',kind='REFUND'))
                check('Evidence conflict retains protected facts',protected()==before)
                (out/'real_process.json').write_text(json.dumps({'scenario':scenario,'schema':fixture['settings'].schema,
                    'runtime':runtime.name,'api_pids':[p.pid for p in apis],'checks':checks,'http':reports},indent=2),encoding='utf8')
                return 0
            order=[]
            if scenario in ('A','C-reject','C-expiry','D-decide-same','D-decide-other','D-confirm-wins'):
                refund=safe_request(first,'POST',refund_path,expected=202,headers=hs(admin,key),json=body)
            else:
                def change_authority():
                    if 'logout' in scenario:
                        victim=customer if 'witness' in scenario else admin
                        return second.post('/v1/auth/logout',headers=hs(victim))
                    if 'user-state' in scenario or 'role' in scenario:
                        current_user=read('users',id=demo_id('technician'))[0]
                        return second.patch('/v1/users/'+str(demo_id('technician')),headers=hs(admin),
                            json={'expected_version':current_user['version'],**({'role':'CUSTOMER'} if 'role' in scenario else {'state':'LOCKED'})})
                    return second.put('/v1/users/'+str(demo_id('technician'))+'/station-assignments',headers=hs(admin),json={'station_ids':[]})
                def request_intent(client=first,request_key=key):
                    try:
                        result=client.post(refund_path,headers=hs(admin,request_key),json=body)
                        return {'status':result.status_code,'body':result.json()}
                    except httpx.HTTPError as exc:
                        return {'transport_error':type(exc).__name__}
                with ThreadPoolExecutor(max_workers=2) as pool:
                    if scenario.startswith('D-') and scenario.endswith('-first'):
                        from app.application.assets import station_lock
                        with db.sessions() as held,observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                            station_lock(held,db,demo_id('S01'));holder=held.scalar(text('select pg_backend_pid()'))
                            future=pool.submit(request_intent)
                            def lock_waits():
                                return [dict(r) for r in observer.execute(text('select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),{'holder':holder}).mappings()]
                            diagnostic=wait(lock_waits,'actual request station wait',3)
                            if scenario=='D-role-first':
                                # Baseline forbids changing the role of an assigned
                                # Technician. Remove assignment legally first;
                                # never bypass USER_REFERENCED with SQL.
                                safe_request(second,'PUT','/v1/users/'+str(demo_id('technician'))+'/station-assignments',expected=200,
                                             headers=hs(admin),json={'station_ids':[]})
                            changed=change_authority()
                            check('Authority change really commits first',changed.status_code==200)
                            if 'logout' in scenario:
                                safe_request(second,'GET','/v1/me',expected=401,headers=customer if 'witness' in scenario else admin)
                            order.append('authority_change_committed_before_station_release');held.rollback()
                            refused=future.result(timeout=15)
                        check('Revoke-first refuses old authority',refused.get('status')==(403 if 'assignment' in scenario else 401))
                        check('No partial financial writes',not read('refunds') and not read('refund_attempts') and not read('refund_certificate_redemptions') and not read('outbox_messages',kind='REFUND'))
                        check('Protected facts preserved on refusal',protected()==before)
                        (out/'real_process.json').write_text(json.dumps({'scenario':scenario,'schema':fixture['settings'].schema,
                            'api_pids':[p.pid for p in apis],'order':order,'lock_diagnostics':diagnostic,'http_status':refused['status'],
                            'checks':checks,'http':reports},indent=2),encoding='utf8')
                        return 0
                    future=pool.submit(request_intent)
                    ready_file=runtime/('commit-ready.json' if scenario=='D-postcommit' else 'audit-ready.json')
                    wait(ready_file.exists,'test factory decision boundary',5)
                    ready=json.loads(ready_file.read_text(encoding='utf8'));order.append('first_reached_'+ready_file.stem)
                    if scenario=='D-precommit':
                        check('Crash barrier is actual Backend OS PID',ready['os_pid']==apis[0].pid)
                        apis[0].kill();apis[0].wait(timeout=10)
                        lost=future.result(timeout=10)
                        wait(lambda:not read('refunds'),'rollback after actual Backend kill',3)
                        check('Actual process crash before commit rolls back intent',
                              bool(lost.get('transport_error')) and not read('refund_attempts') and not read('refund_certificate_redemptions')
                              and not read('outbox_messages',kind='REFUND') and not [a for a in read('audit_events') if a['action']=='REFUND_REQUEST_CREATED'])
                        check('Rollback preserves review version',read('swap_transactions',id=identity)[0]['state']=='REVIEW_REQUIRED')
                        order.append('rollback_observed');refund=safe_request(second,'POST',refund_path,expected=202,headers=hs(admin,key),json=body)
                    elif scenario=='D-postcommit':
                        lost=future.result(timeout=10);apis[0].wait(timeout=10)
                        check('Actual process exits after committed intent before response',bool(lost.get('transport_error')) and apis[0].returncode==87 and len(read('refunds'))==1)
                        order.append('commit_observed_before_retry');refund=safe_request(second,'POST',refund_path,expected=202,headers=hs(admin,key),json=body)
                    else:
                        if scenario=='E-intent-first':
                            sim=simulator('sim-reboot-during-redemption')
                            competitor=None
                        elif scenario.endswith('-after'):
                            competitor=pool.submit(change_authority)
                        else:
                            competitor=pool.submit(request_intent,second,key if scenario=='D-same-key' else uuid4())
                        with observer_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                            def lock_waits():
                                return [dict(r) for r in observer.execute(text('select pid,wait_event_type,pg_blocking_pids(pid) blockers from pg_stat_activity where :holder=any(pg_blocking_pids(pid))'),{'holder':ready['pg_pid']}).mappings()]
                            diagnostic=wait(lock_waits,'actual competing PostgreSQL lock wait',3)
                        (out/'lock_wait.json').write_text(json.dumps({'holder':ready['pg_pid'],
                            'waiters':diagnostic,'api_pids':[p.pid for p in apis]},indent=2),encoding='utf8')
                        check('Different PostgreSQL PID really waits',all(r['pid']!=ready['pg_pid'] and r['wait_event_type']=='Lock' for r in diagnostic))
                        (runtime/'release').write_text('release',encoding='utf8')
                        first_result=future.result(timeout=10)
                        check('Authority-first intent commits',first_result.get('status')==202)
                        refund=first_result['body']
                        if scenario=='E-intent-first':
                            wait(lambda:read('refund_certificate_revocations'),'accepted reboot after committed intent')
                            check('Projection changes only after intent commits',read('recovery_cases',swap_id=identity)[0]['new_pin_delivered']=='UNKNOWN')
                            check('Accepted contradiction preserves committed intent',len(read('refunds'))==1 and read('refunds')[0]['state']=='REQUESTED')
                        else:other=competitor.result(timeout=10)
                        if scenario=='E-intent-first':pass
                        elif scenario.endswith('-after'):
                            if scenario=='D-role-after':
                                check('Role update waits then preserves USER_REFERENCED policy',other.status_code==409 and other.json()['code']=='USER_REFERENCED')
                            else:
                                check('Authority change commits after intent releases locks',other.status_code==200)
                        else:
                            check('Competing intent is serialized',other['status']==(202 if scenario=='D-same-key' else 409))
                        order.append('first_committed_then_competitor_completed')
                    (out/'ordering.json').write_text(json.dumps({'scenario':scenario,'ready':ready,'order':order,
                        'api_pids':[p.pid for p in apis],'diagnostic':locals().get('diagnostic',[])},indent=2),encoding='utf8')
            if scenario=='D-caller-logout-after':
                safe_request(second,'POST',refund_path,expected=401,headers=hs(admin,key),json=body)
                admin=login('admin',second)
            replay=safe_request(second,'POST','/v1/payments/'+str(payment['id'])+'/refund',expected=202,headers=hs(admin,key),json=body)
            check('Cross-process replay returns exact same intent',refund==replay)
            conflict=second.post('/v1/payments/'+str(payment['id'])+'/refund',headers=hs(admin,key),
                                 json={**body,'reason':'Conflicting body must never reuse committed key'})
            check('Same key with changed body is conflicting',conflict.status_code==409 and conflict.json()['code']=='IDEMPOTENCY_CONFLICT')
            check('Protected custody/charge/holds unchanged',protected()==before)
            check('Exactly one REQUESTED Refund',len(read('refunds',payment_id=payment['id']))==1 and refund['state']=='REQUESTED')
            check('One generation0 registry',len(read('refund_attempts',refund_id=UUID(refund['id'])))==1)
            check('One certificate redemption',len(read('refund_certificate_redemptions',refund_id=UUID(refund['id'])))==1)
            boxes=read('outbox_messages',kind='REFUND')
            check('Inert outbox: no dispatch attempt',len(boxes)==1 and boxes[0]['attempts']==0 and boxes[0]['delivered_at'] is None)
            audits=read('audit_events')
            check('One refund success audit',sum(a['action']=='REFUND_REQUEST_CREATED' for a in audits)==1)
            check('One redemption audit',sum(a['action']=='ND_CERTIFICATE_REDEEMED' for a in audits)==1)
            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                check('No physical command effects',c.execute('SELECT coalesce(sum(effects),0) FROM commands').fetchone()[0]==0)
                check('Durable station fence retained',c.execute("SELECT count(*) FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()[0]==1)
                expected_receipts=2 if scenario in ('C-reject','C-expiry') else 1
                check('Exactly one immutable receipt per inspected operation',
                      c.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==expected_receipts
                      and c.execute('SELECT count(DISTINCT operation_id) FROM nd_receipts').fetchone()[0]==expected_receipts)
            with sqlite3.connect((ledger/'charge.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
                check('One actual mock charge, no refund provider',c.execute('SELECT count(*) FROM charges').fetchone()[0]==1)
            (out/'real_process.json').write_text(json.dumps({'schema':fixture['settings'].schema,'runtime':runtime.name,
                'api_pids':[p.pid for p in apis],'worker_pids':[worker.pid,charge_worker.pid],'swap_id':swap['id'],
                'operation_id':operation,'certificate_id':case['certificate']['certificate_id'],
                'checks':checks,'http':reports,'scenario':scenario,'provider_refund_effects':'NOT IMPLEMENTED / NOT INVOKED'},indent=2),encoding='utf8')
        return 0
    finally:
        for child in reversed(children):stop(child)
        for log in logs:log.close()
        factory.close()
        observer_engine.dispose()
        if previous_schema is None:os.environ.pop('DATABASE_SCHEMA',None)
        else:os.environ['DATABASE_SCHEMA']=previous_schema
        if sys.exc_info()[0] is not None and not any(not c['passed'] for c in checks):
            checks.append({'name':'Interrupted workflow: '+sys.exc_info()[0].__name__,'passed':False})
        suite=Element('testsuite',name='B1b real-process '+scenario,tests=str(len(checks)),
                      failures=str(sum(not c['passed'] for c in checks)),errors='0',skipped='0')
        for check_ in checks:
            node=SubElement(suite,'testcase',name=check_['name'],classname='B1b.RealProcess.'+scenario)
            if not check_['passed']:SubElement(node,'failure').text=check_['name']
        ElementTree(suite).write(out/'results.xml',encoding='utf8',xml_declaration=True)


if __name__=='__main__':
    if '--source-crash-child' in sys.argv:crash_simulator()
    else:sys.exit(main())
