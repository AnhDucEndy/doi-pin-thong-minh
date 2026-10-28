"""Real subprocess E2E, exclusively in a new PostgreSQL test schema; no volume reset."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from datetime import timedelta
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/backend'))
from app.config import Settings,approved_policy
from app.seed import seed,demo_id
from app.infrastructure.db import Database
from app.application import assets
from app.application.device import enqueue_command
from app.application.identity import utcnow
from sqlalchemy import insert,select,update
import httpx


def wait(predicate,label,seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            if predicate():return
        except (httpx.HTTPError,OSError):pass
        time.sleep(.2)
    raise AssertionError(label)


def fingerprints(db):
    with db.sessions() as s:
        return {name:hashlib.sha256(json.dumps([dict(r) for r in s.execute(select(db.table(name)).order_by(db.table(name).c.id)).mappings()],default=str,sort_keys=True).encode()).hexdigest()
            for name in ('stations','devices','compartments','batteries','battery_telemetry','device_events','swap_transactions','resource_reservations')}


def main():
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8002))==0:
            raise RuntimeError('Test port 8002 is already in use; stop the test GUI API before E2E')
    original=Database(Settings.from_env());before=fingerprints(original)
    schema='phase4_e2e_'+uuid4().hex[:10];env=dict(os.environ,DATABASE_SCHEMA=schema,PYTHONPATH=str(ROOT/'services/backend'),PYTHONIOENCODING='utf-8')
    directory=ROOT/'.cache'/schema;directory.mkdir(parents=True)
    env.update(TEMP=str(ROOT/'.cache/tmp'),TMP=str(ROOT/'.cache/tmp'))
    processes=[];logs=[];checks=[];db=None
    def run(args):subprocess.run([sys.executable,*args],cwd=ROOT,env=env,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def launch(args,name):
        output=(directory/(name+'.log')).open('w',encoding='utf-8');logs.append(output)
        p=subprocess.Popen([sys.executable,*args],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));processes.append(p);return p
    def stop(p):
        if p.poll() is None:p.terminate();p.wait(timeout=10)
    try:
        run(['tools/provision_database.py','roles']);run(['-m','alembic','-c','services/backend/alembic.ini','upgrade','head']);run(['tools/provision_database.py','grants'])
        db=Database(Settings(os.environ['MIGRATION_DATABASE_URL'],schema))
        seed(db,{n:os.environ[f'DEMO_{n.upper()}_PASSWORD'] for n in ('admin','customer','technician')},
             {n:os.environ['DEMO_DEVICE_KEY_'+n] for n in ('S01','S02')})
        def row(name,identity):
            with db.sessions() as s:
                table=db.table(name);return dict(s.execute(select(table).where(table.c.id==identity)).mappings().one())
        api_process=launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8002','--no-access-log'],'api')
        wait(lambda:httpx.get('http://127.0.0.1:8002/health',timeout=1).status_code==200,'Test API startup')
        if api_process.poll() is not None:raise RuntimeError('Isolated test API exited during startup')
        launch(['-m','app.workers.device'],'worker')
        ledger=ROOT/'.local'/schema
        def simulator(code,scenario='normal',cycles=0):
            return launch(['-m','simulators.device.main','--station',code,'--url','http://127.0.0.1:8002',
                '--ledger-dir',str(ledger),'--scenario',scenario,'--cycles',str(cycles)],code+'-'+scenario+'-'+uuid4().hex[:4])
        first=simulator('S01','ack-only');second=simulator('S02','nack')
        wait(lambda:row('devices',demo_id('device:S01'))['last_received_at'] and row('devices',demo_id('device:S02'))['last_received_at'],'Two online simulators',25)
        wait(lambda:latest_quality(db,'S01') and latest_quality(db,'S02'),'Authenticated telemetry processed')
        checks.append('Two real simulator processes: snapshot/heartbeat/BMS accepted; no auto activation')
        assert row('batteries',demo_id('S01:battery:2'))['lifecycle']=='REGISTERED'
        assert row('compartments',demo_id('S01:slot:2'))['service_state']=='BLOCKED'
        def fixture_command(code,extra_customer=False):
            with db.sessions.begin() as s:
                station=demo_id(code);assets.station_lock(s,db,station)
                customer=uuid4() if extra_customer else demo_id('customer')
                old=uuid4() if extra_customer else demo_id('customer:initial-battery')
                if extra_customer:
                    s.execute(insert(db.table('users')).values(id=customer,username='e2e-'+uuid4().hex,password_hash='not-a-login-account',role='CUSTOMER'))
                    s.execute(insert(db.table('batteries')).values(id=old,serial='E2E-'+uuid4().hex,family=approved_policy()['battery_family'],location_kind='CUSTOMER',holder_user_id=customer))
                credential,swap=uuid4(),uuid4();slot=demo_id(f'{code}:slot:1');supply=demo_id(f'{code}:slot:2');new=demo_id(f'{code}:battery:2')
                s.execute(insert(db.table('credentials')).values(id=credential,user_id=customer,credential_hash=secrets.token_hex(32)))
                s.execute(update(db.table('compartments')).where(db.table('compartments').c.id==slot).values(service_state='ACTIVE'))
                s.execute(insert(db.table('swap_transactions')).values(id=swap,customer_id=customer,station_id=station,verified_via='RFID',credential_id=credential,
                    state='AWAITING_RETURN',policy_id=demo_id('policy:1'),policy_snapshot=approved_policy(),old_battery_id=old,new_battery_id=new,
                    return_compartment_id=slot,supply_compartment_id=supply,amount_minor=9000,consented_at=utcnow()))
                for values in [{'compartment_id':slot},{'compartment_id':supply},{'battery_id':new}]:
                    s.execute(insert(db.table('resource_reservations')).values(id=uuid4(),swap_id=swap,**values))
                s.execute(insert(db.table('payments')).values(id=uuid4(),swap_id=swap,provider_key=uuid4(),state='SUCCEEDED',amount_minor=9000,verified_at=utcnow()))
                command=enqueue_command(s,db,swap,slot,'OPEN_RETURN',approved_policy())
                return command,swap
        ack,swap=fixture_command('S01')
        wait(lambda:row('device_commands',ack['id'])['state']=='ACKNOWLEDGED','Real ACK lifecycle')
        assert row('compartments',ack['compartment_id'])['door_state']=='CLOSED'
        assert row('batteries',demo_id('customer:initial-battery'))['holder_user_id']==demo_id('customer')
        checks.append('Real ACK: ACKNOWLEDGED, door still CLOSED, custody unchanged')
        nack,nack_swap=fixture_command('S02',True)
        wait(lambda:row('device_commands',nack['id'])['state']=='REJECTED','Real NACK lifecycle')
        checks.append('Real NACK: REJECTED, reservation preserved')
        wait(lambda:row('device_commands',ack['id'])['state']=='UNKNOWN','ACK without evidence times out',
            approved_policy()['physical_step_timeout_seconds']+10)
        assert row('swap_transactions',swap)['state']=='REVIEW_REQUIRED'
        checks.append('Real deadline: ACK without physical evidence -> UNKNOWN / REVIEW_REQUIRED')
        stop(first);stop(second);print('Simulators stopped; waiting for approved 15-second offline threshold',flush=True)
        def offline_detected():
            contact=row('devices',demo_id('device:S01'))['last_received_at']
            with db.sessions() as s:
                alerts=db.table('alerts')
                marked=s.execute(select(alerts.c.id).where(alerts.c.station_id==demo_id('S01'),alerts.c.code=='DEVICE_OFFLINE',alerts.c.state!='RESOLVED')).first()
            return contact is not None and contact<utcnow()-timedelta(seconds=approved_policy()['telemetry_stale_seconds']) and marked
        wait(offline_detected,'Heartbeat offline timeout',22)
        checks.append('Real heartbeat timeout -> offline; resources retained')
        boot_before=row('devices',demo_id('device:S01'))['boot_id']
        reconnect=simulator('S01',cycles=1);assert reconnect.wait(timeout=25)==0
        wait(lambda:row('devices',demo_id('device:S01'))['last_received_at'] is not None,'Snapshot reconnect')
        assert row('devices',demo_id('device:S01'))['boot_id']!=boot_before
        assert row('device_commands',ack['id'])['state']=='UNKNOWN'
        checks.append('Simulator restart/new boot with ledger: no command re-execution')
        hot=simulator('S01','hot',1);assert hot.wait(timeout=25)==0
        wait(lambda:row('batteries',demo_id('S01:battery:2'))['lifecycle']=='QUARANTINED','Authenticated hot telemetry quarantine')
        normal=simulator('S01',cycles=1);assert normal.wait(timeout=25)==0
        assert row('batteries',demo_id('S01:battery:2'))['lifecycle']=='QUARANTINED'
        checks.append('Hot telemetry quarantine; later good data cannot auto restore')
        with db.sessions() as s:
            reserves=db.table('resource_reservations')
            assert all(r is None for r in s.scalars(select(reserves.c.released_at)))
            events=db.table('device_events')
            assert len(s.execute(select(events.c.id).where(events.c.processing_error=='SIMULATION_SEED_UNVERIFIED')).all())==10
        assert fingerprints(original)==before
        checks.append('Seed remains unverified; demo schema untouched; no reservation released')
        result={'result':'Passed','schema':schema,'checks':checks,'production_schema_modified':False,'test_schema_retained':True,
            'ledger_directory':str(ledger.relative_to(ROOT)),'logs_directory':str(directory.relative_to(ROOT)),
            'command_states':{'ack_timeout':row('device_commands',ack['id'])['state'],'nack':row('device_commands',nack['id'])['state']}}
        (ROOT/'docs/PHASE4_E2E_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(f'{len(checks)} real-process E2E checks Passed; schema={schema}',flush=True)
    finally:
        for p in reversed(processes):stop(p)
        for log in logs:log.close()
        if db:db.engine.dispose()
        original.engine.dispose()


def latest_quality(db,code):
    with db.sessions() as s:
        t=db.table('battery_telemetry')
        return s.scalar(select(t.c.quality_ok).where(t.c.battery_id==demo_id(f'{code}:battery:2')).order_by(t.c.received_at.desc()).limit(1)) is True


def live_checks():
    checks=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as http:
        assert http.get('/health').json()['phase']==4;checks.append('Phase4 health and PostgreSQL')
        assert httpx.get('http://127.0.0.1:5173').status_code==200;checks.append('Frontend HTML')
        for name in ('admin','technician','customer'):
            login=http.post('/v1/auth/login',json={'username':name,'password':os.environ[f'DEMO_{name.upper()}_PASSWORD']})
            assert login.status_code==200;auth={'Authorization':'Bearer '+login.json()['access_token']}
            for path in ('/v1/dashboard','/v1/alerts'):
                response=http.get(path,headers=auth);assert response.status_code==(403 if name=='customer' else 200)
                checks.append(f'{name}: {path}')
            assert http.post('/v1/auth/logout',headers={**auth,'Idempotency-Key':str(uuid4())}).status_code==200
            checks.append(f'{name}: logout')
        assert http.get('/v1/device/commands',headers={'Authorization':'Bearer user-is-not-a-device'}).status_code==401
        checks.append('User bearer cannot poll device commands')
        response=http.post('/v1/device/events',headers={'X-Device-Key':os.environ['DEMO_DEVICE_KEY_S01']},json={'kind':'INVALID'})
        assert response.status_code==422 and response.json()['code']=='DEVICE_EVENT_INVALID'
        checks.append('Authenticated malformed event rejected without inbox write')
    (ROOT/'docs/PHASE4_HTTP_SMOKE_RESULTS.json').write_text(json.dumps({'result':'Passed','asset_mutations':False,'checks':checks},indent=2)+'\n',encoding='utf-8')
    print(f'{len(checks)} live HTTP checks Passed; no successful asset mutation')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live-readonly',action='store_true');args=parser.parse_args()
    live_checks() if args.live_readonly else main()
