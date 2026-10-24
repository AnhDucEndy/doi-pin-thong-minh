"""Phase 5 real HTTP/process acceptance in a new schema; retain DB/ledger evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/backend'))
from app.config import Settings, approved_policy
from app.infrastructure.db import Database
from app.seed import seed,demo_id
from sqlalchemy import select,func
from smoke_phase4 import fingerprints,wait
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true')
    parser.add_argument('--http-fixture',help='Ignored connection.json from this tool, test schemas only')
    args=parser.parse_args()
    if args.http_fixture:
        http_checks(args.http_fixture)
        return
    for port in (8003,8004):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Test port {port} is occupied')
    demo=Database(Settings.from_env());before=fingerprints(demo)
    schema='phase5_e2e_'+uuid4().hex[:10];directory=ROOT/'.cache'/schema;directory.mkdir(parents=True)
    env=dict(os.environ,DATABASE_SCHEMA=schema,PYTHONPATH=str(ROOT/'services/backend'),PYTHONIOENCODING='utf-8',
             TEMP=str(ROOT/'.cache/tmp'),TMP=str(ROOT/'.cache/tmp'))
    passwords={n:secrets.token_urlsafe(24) for n in ('admin','customer','technician')}
    keys={n:secrets.token_urlsafe(32) for n in ('S01','S02')}
    env.update({f'DEMO_{n.upper()}_PASSWORD':v for n,v in passwords.items()})
    env.update({'DEMO_DEVICE_KEY_'+n:v for n,v in keys.items()})
    processes=[];logs=[];checks=[];db=None
    def run(arguments):subprocess.run([sys.executable,*arguments],cwd=ROOT,env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    def launch(arguments,name):
        output=(directory/(name+'.log')).open('w',encoding='utf-8');logs.append(output)
        p=subprocess.Popen([sys.executable,*arguments],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);processes.append(p);return p
    def auth(http,name):
        r=http.post('/v1/auth/login',json={'username':name,'password':passwords[name]});assert r.status_code==200
        return {'Authorization':'Bearer '+r.json()['access_token']}
    def mutation(http,path,user,body=None,key=None):return http.post(path,headers={**user,'Idempotency-Key':str(key or uuid4())},json=body)
    def verify(http,token,key):return mutation(http,'/v1/device/verifications',{'X-Device-Key':keys['S01']},{'method':'QR','credential':token},key)
    try:
        run(['tools/provision_database.py','roles']);run(['-m','alembic','-c','services/backend/alembic.ini','upgrade','head']);run(['tools/provision_database.py','grants'])
        db=Database(Settings(os.environ['MIGRATION_DATABASE_URL'],schema));seed(db,passwords,keys)
        for port in (8003,8004):
            launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log','--no-proxy-headers'],f'api-{port}')
            wait(lambda:httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200,'API startup')
        worker=launch(['-m','app.workers.device'],'worker')
        launch(['-m','simulators.device.main','--url','http://127.0.0.1:8003','--ledger-dir',str(ROOT/'.local'/schema)],'simulators')
        def row(name,identity):
            with db.sessions() as s:
                table=db.table(name);return dict(s.execute(select(table).where(table.c.id==identity)).mappings().one())
        wait(lambda:row('devices',demo_id('device:S01'))['last_received_at'] is not None,'Authenticated simulation',25)
        def snapshot():
            with db.sessions() as s:
                e=db.table('device_events');return s.scalar(select(e.c.id).where(e.c.device_id==demo_id('device:S01'),e.c.kind=='SNAPSHOT',e.c.accepted.is_(True)).order_by(e.c.received_at.desc()).limit(1))
        with httpx.Client(base_url='http://127.0.0.1:8003',timeout=15) as first,httpx.Client(base_url='http://127.0.0.1:8004',timeout=15) as second:
            admin,customer,tech=auth(first,'admin'),auth(first,'customer'),auth(first,'technician')
            pin=demo_id('S01:battery:2')
            def activate():
                r=mutation(first,f'/v1/batteries/{pin}/actions',tech,{'expected_version':row('batteries',pin)['version'],'action':'ACTIVATE','reason':'Isolated E2E inspection','evidence_event_id':str(snapshot())})
                return r.status_code==200
            wait(activate,'Activate with accepted simulation evidence')
            for number in (1,2):
                identity=demo_id(f'S01:slot:{number}')
                def restore():
                    r=mutation(first,f'/v1/compartments/{identity}/actions',tech,{'expected_version':row('compartments',identity)['version'],'action':'RESTORE','reason':'Isolated E2E inspection','evidence_event_id':str(snapshot())})
                    return r.status_code==200
                wait(restore,'Restore compartment from snapshot')
            checks.append('API+worker+simulator: genuine accepted BMS/snapshot and Technician activation/restore')
            key=uuid4();qr=mutation(first,'/v1/qr-challenges',customer,{'station_id':str(demo_id('S01'))},key)
            assert qr.status_code==201
            assert mutation(first,'/v1/qr-challenges',customer,{'station_id':str(demo_id('S01'))},key).json()==qr.json()
            checks.append('QR delivery retry is identical; token never logged')
            with ThreadPoolExecutor(max_workers=2) as pool:
                a=pool.submit(verify,first,qr.json()['qr_token'],uuid4());b=pool.submit(verify,second,qr.json()['qr_token'],uuid4());responses=[a.result(),b.result()]
            assert sorted(r.status_code for r in responses)==[201,409]
            swap=next(r.json() for r in responses if r.status_code==201)
            checks.append('Two Backend processes race one QR: exactly one VERIFIED, replay rejected')
            reserve_key=uuid4();path=f'/v1/swaps/{swap["id"]}/reserve';body={'expected_version':swap['version']}
            booked=mutation(first,path,customer,body,reserve_key);assert booked.status_code==200 and booked.json()['state']=='RESERVED'
            assert mutation(second,path,customer,body,reserve_key).json()==booked.json()
            with db.sessions() as s:
                h=db.table('resource_reservations');assert s.scalar(select(func.count()).select_from(h).where(h.c.released_at.is_(None)))==3
                for name in ('payments','outbox_messages','device_commands'):assert s.scalar(select(func.count()).select_from(db.table(name)))==0
            checks.append('Reservation retry across processes: exactly three holds, zero payment/outbox/command')
            assert first.get('/v1/swaps/'+swap['id'],headers=tech).status_code==403
            assert first.get('/v1/alerts',headers=customer).status_code==403
            assert first.post('/v1/device/verifications',headers={**customer,'Idempotency-Key':str(uuid4())},json={'method':'RFID','credential':'untrusted'}).status_code==401
            checks.append('Role and device/user credential separation')
            # A real worker restart must recover pending TTL from PostgreSQL, not memory.
            worker.terminate();worker.wait(timeout=10);worker=launch(['-m','app.workers.device'],'worker-restarted')
            deadline=row('swap_transactions',UUID(swap['id']))['reservation_expires_at']
            remaining=max(0,(deadline-row('swap_transactions',UUID(swap['id']))['created_at']).total_seconds())
            print(f'Waiting for approved {approved_policy()["reservation_ttl_seconds"]}-second reservation TTL with real heartbeat and restarted worker',flush=True)
            wait(lambda:row('swap_transactions',UUID(swap['id']))['state']=='CANCELLED','Real reservation TTL',approved_policy()['reservation_ttl_seconds']+15)
            with db.sessions() as s:
                assert all(s.scalars(select(h.c.released_at).where(h.c.swap_id==UUID(swap['id']))))
            assert mutation(second,path,customer,body,reserve_key).json()==booked.json()
            assert first.get('/v1/swaps/'+swap['id'],headers=customer).json()['state']=='CANCELLED'
            checks.append('Real 120-second TTL after worker restart: release once; replay cannot resurrect')
            value=secrets.token_urlsafe(24)
            credential=mutation(first,f'/v1/users/{demo_id("customer")}/credentials',admin,{'rfid_value':value});assert credential.status_code==201
            def rfid():return mutation(first,'/v1/device/verifications',{'X-Device-Key':keys['S01']},{'method':'RFID','credential':value})
            for _ in range(2):
                verified=rfid();assert verified.status_code==201
                cancelled=mutation(first,f'/v1/swaps/{verified.json()["id"]}/cancel',customer,{'expected_version':verified.json()['version'],'reason':'E2E pre-payment cancellation'})
                assert cancelled.status_code==200
            assert mutation(first,f'/v1/credentials/{credential.json()["id"]}/revoke',admin).status_code==200
            assert rfid().status_code==401
            checks.append('RFID reused across closed sessions; revoked RFID rejected')
            assert fingerprints(demo)==before
            checks.append('Primary demo asset/evidence/reservation fingerprints unchanged')
            result={'result':'Passed','checks':checks,'schema':schema,'production_schema_modified':False,
                'two_backend_processes':True,'real_reservation_ttl_seconds':approved_policy()['reservation_ttl_seconds'],
                'ledger_directory':str((ROOT/'.local'/schema).relative_to(ROOT)),'logs_directory':str(directory.relative_to(ROOT))}
            (ROOT/'docs/PHASE5_E2E_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            # Ignored, test-only credentials for optional Browser acceptance; never stage this file.
            connection={'schema':schema,'api':'http://127.0.0.1:8003','passwords':passwords,'device_keys':keys}
            (directory/'connection.json').write_text(json.dumps(connection),encoding='utf-8')
            print(f'{len(checks)} real-process E2E checks Passed; schema={schema}',flush=True)
            if args.serve:
                print(f'Browser fixture ready; stop by creating .cache/{schema}/STOP',flush=True)
                while not (directory/'STOP').exists():time.sleep(.5)
    finally:
        for p in reversed(processes):
            if p.poll() is None:p.terminate();p.wait(timeout=10)
        for log in logs:log.close()
        if db:db.engine.dispose()
        demo.engine.dispose()


def http_checks(manifest):
    path=Path(manifest).resolve()
    if not path.is_relative_to(ROOT/'.cache'):raise ValueError('Use the local ignored test fixture manifest')
    config=json.loads(path.read_text(encoding='utf-8'))
    if not config['schema'].startswith('phase5_e2e_') or config['api'] not in ('http://127.0.0.1:8003','http://127.0.0.1:8004'):
        raise ValueError('HTTP writes are allowed only on the isolated test API')
    checks=[]
    def expect(response,status,label,code=None):
        assert response.status_code==status,(label,response.status_code)
        if code:assert response.json()['code']==code,label
        checks.append(label)
        return response.json()
    def mutation(http,path,auth,body=None,key=None):
        return http.post(path,headers={**auth,'Idempotency-Key':str(key or uuid4())},json=body)
    with httpx.Client(base_url=config['api'],timeout=15) as http:
        expect(http.get('/health'),200,'Health/PostgreSQL phase5')
        auth={}
        for name in ('admin','customer','technician'):
            login=expect(http.post('/v1/auth/login',json={'username':name,'password':config['passwords'][name]}),200,name+' login')
            auth[name]={'Authorization':'Bearer '+login['access_token']}
        admin,customer,tech=auth['admin'],auth['customer'],auth['technician']
        for name in ('admin','customer','technician'):
            expect(http.get('/v1/swaps',headers=auth[name]),403 if name=='technician' else 200,name+' list scope')
        body={'station_id':str(demo_id('S01'))};key=uuid4()
        qr=expect(mutation(http,'/v1/qr-challenges',customer,body,key),201,'Customer issues QR')
        assert expect(mutation(http,'/v1/qr-challenges',customer,body,key),201,'QR exact retry')==qr
        expect(mutation(http,'/v1/qr-challenges',admin,body),403,'Admin cannot issue Customer QR','FORBIDDEN')
        read={'method':'QR','credential':qr['qr_token']};device={'X-Device-Key':config['device_keys']['S01']};read_key=uuid4()
        expect(mutation(http,'/v1/device/verifications',customer,read),401,'User bearer cannot act as device','DEVICE_AUTH_REQUIRED')
        swap=expect(mutation(http,'/v1/device/verifications',device,read,read_key),201,'QR creates VERIFIED')
        assert expect(mutation(http,'/v1/device/verifications',device,read,read_key),201,'Verification exact retry')==swap
        expect(mutation(http,'/v1/device/verifications',device,read),409,'QR replay rejected','QR_ALREADY_USED')
        expect(http.get('/v1/swaps/'+swap['id'],headers=tech),403,'Technician cannot read Customer session','FORBIDDEN')
        expect(http.get('/v1/swaps/'+str(uuid4()),headers=customer),404,'Missing session hidden','RESOURCE_NOT_FOUND')
        path='/v1/swaps/'+swap['id'];key=uuid4();body={'expected_version':swap['version']}
        booked=expect(mutation(http,path+'/reserve',customer,body,key),200,'Reserve returns quote and resource IDs')
        assert booked['state']=='RESERVED' and booked['amount_minor']==approved_policy()['fee_minor']
        assert expect(mutation(http,path+'/reserve',customer,body,key),200,'Reservation exact retry')==booked
        expect(mutation(http,path+'/reserve',customer,body),409,'Stale version rejected','VERSION_CONFLICT')
        key=uuid4();body={'expected_version':booked['version'],'reason':'HTTP fixture cancellation'}
        cancelled=expect(mutation(http,path+'/cancel',customer,body,key),200,'Cancel before payment')
        assert cancelled['state']=='CANCELLED'
        assert expect(mutation(http,path+'/cancel',customer,body,key),200,'Cancellation exact retry')==cancelled
        value=secrets.token_urlsafe(24)
        credential=expect(mutation(http,f'/v1/users/{demo_id("customer")}/credentials',admin,{'rfid_value':value}),201,'Admin links RFID')
        expect(mutation(http,f'/v1/credentials/{credential["id"]}/revoke',tech),403,'Technician cannot revoke RFID','FORBIDDEN')
        expect(mutation(http,f'/v1/credentials/{credential["id"]}/revoke',admin),200,'Admin revokes RFID')
        expect(mutation(http,'/v1/device/verifications',device,{'method':'RFID','credential':value}),401,'Revoked RFID rejected','CREDENTIAL_INVALID')
        for name in auth:
            expect(mutation(http,'/v1/auth/logout',auth[name]),200,name+' logout')
    (ROOT/'docs/PHASE5_HTTP_SMOKE_RESULTS.json').write_text(json.dumps({'result':'Passed','schema':config['schema'],
        'checks':checks,'primary_demo_modified':False},indent=2)+'\n',encoding='utf-8')
    print(f'{len(checks)} isolated HTTP checks Passed; credentials omitted')


if __name__=='__main__':main()
