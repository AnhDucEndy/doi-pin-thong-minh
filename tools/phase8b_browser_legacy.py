"""Isolated Browser-only P8-REC-0.1 fixture; no production imports this module.

Reuse the real return-boundary fixture and the verified IPC publisher unchanged.
Only the Browser records human statements and requests settlement.
"""
from smoke_phase8a import *
import time
from phase8a_manual_operator import publish_state


def device(directory):
    from simulators.device.main import Simulator
    from simulators.device.service import perform, flush
    from app.config import approved_policy
    assert directory.resolve().is_relative_to(ROOT/'.cache')
    assert os.environ['DATABASE_SCHEMA'].startswith('phase5_test_')
    sim = Simulator('S01', os.environ['DEMO_DEVICE_KEY_S01'],
        base_url=os.environ['P8_OPERATOR_URL'], ledger=directory/'ledgers/S01.sqlite3', scenario='physical')
    try:
        next_cycle = 0
        while not (directory/'stop').exists():
            if time.monotonic() >= next_cycle:
                sim.cycle(); flush(sim)
                next_cycle = time.monotonic()+approved_policy()['telemetry_interval_seconds']
            for request in sorted(directory.glob('request-*.json')):
                result = request.with_suffix('.result.json')
                if result.exists() or request.name.endswith('.result.json'):
                    continue
                packet = json.loads(request.read_text())
                assert packet['action'] == 'HANDOVER'
                tasks = sim.http.get('/v1/device/recovery-tasks'); tasks.raise_for_status()
                task = next(t for t in tasks.json()['items'] if t['operation_id'] == packet['operation_id'])
                assert task.get('protocol_version') is None and task['purpose'] == 'RETURN_OLD_TO_CUSTOMER'
                state = perform(sim, task, technician_token=os.environ['SERVICE_TECHNICIAN_TOKEN'])
                flush(sim)
                # Receipt transport alone is not a processed physical snapshot.
                # Wait for the worker to accept the actual post-effect model.
                sim.cycle()
                packet = json.loads(sim.conn.execute('SELECT observation FROM service_operations WHERE id=?',
                    (packet['operation_id'],)).fetchone()[0])
                check_db = Database(Settings.from_env())
                try:
                    def projected():
                        events = check_db.table('device_events')
                        with check_db.sessions() as session:
                            rows = session.execute(select(events).where(events.c.kind=='SNAPSHOT',
                                events.c.accepted.is_(True),events.c.processed_at.is_not(None),
                                events.c.observed_at>=datetime.fromisoformat(packet['observed_at']))).mappings()
                            return any(any(s['compartment_id']==task['return_compartment_id']
                                and s['present'] is False and s['door_state']=='CLOSED'
                                for s in row['payload']['slots']) for row in rows)
                    wait(projected,'Actual post-handover snapshot processed',10)
                finally:
                    check_db.engine.dispose()
                with result.open('x', encoding='utf8') as stream:
                    json.dump({'completed': state == 'OBSERVED', 'service_state': state}, stream)
            time.sleep(.1)
    finally:
        sim.close()


def run():
    primary = int(os.environ['P8_TEST_API_PORT']); web_port = int(os.environ['P8_MANUAL_WEB_PORT'])
    for port in (primary, primary+1, web_port):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    demo = Database(Settings.from_env()); before = fingerprints(demo)
    factory = environment.__wrapped__(); fixture = next(factory); db = fixture['seed_db']
    directory = ROOT/'.cache'/('p8-legacy-browser-'+uuid4().hex)
    directory.mkdir(exist_ok=False); ledger = directory/'ledgers'; ledger.mkdir(exist_ok=False)
    env = dict(os.environ, DATABASE_SCHEMA=fixture['settings'].schema,
        PYTHONPATH=os.pathsep.join([str(ROOT/'services/backend'),str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT)]),
        **{'DEMO_DEVICE_KEY_'+code:key for code,key in fixture['keys'].items()})
    url = f'http://127.0.0.1:{primary}'; web_url = f'http://127.0.0.1:{web_port}/'
    env.update(P7_BOUNDARY=str(directory/'return-committed.txt'), P8_OPERATOR_URL=url, DEV_API_TARGET=url)
    children, logs = [], []
    def launch(args, name, node=False):
        log = (directory/(name+'.log')).open('x', encoding='utf8'); logs.append(log)
        child = subprocess.Popen((['node'] if node else [sys.executable])+[str(x) for x in args],
            cwd=ROOT/'apps/web' if node else ROOT, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(child); return child
    def stop(child):
        if child.poll() is None:
            child.terminate(); child.wait(15)
    def read(name):
        with db.sessions() as session:
            return [dict(r) for r in session.execute(select(db.table(name))).mappings()]
    report = {'status':'FAILED','schema':fixture['settings'].schema,'runtime':str(directory.relative_to(ROOT))}
    browser = None
    try:
        with TestClient(create_app(fixture['settings'])) as http:
            customer = login(http, fixture); swap = book(http, fixture, customer, db)
            assert consent(http, customer, swap).status_code == 202
            payment.tick(http.app.state.db, transport=outcome)
        for port in (primary, primary+1):
            launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'], 'api-'+str(port))
            wait(lambda:httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200,'API ready')
        worker = launch(['tools/phase7_acceptance_process.py','worker'],'return-boundary-worker')
        physical = launch(['-m','simulators.device.main','--station','S01','--url',url,'--ledger-dir',ledger,'--scenario','physical'],'return-simulator')
        wait(lambda:(directory/'return-committed.txt').exists(),'Real return custody committed',45)
        stop(worker); stop(physical)
        with db.sessions.begin() as session:
            table = db.table('swap_transactions')
            current = session.execute(select(table).where(table.c.id==UUID(swap['id']))).mappings().one()
            assert current['state']=='RETURN_ACCEPTED'
            review(session,db,current,'TEST_SERVICE_HANDOVER')
        launch(['-m','app.workers.device'],'device-worker')
        with httpx.Client(base_url=url,timeout=20) as http:
            tech = login(http,fixture,'technician')
            env['SERVICE_TECHNICIAN_TOKEN'] = tech['Authorization'].removeprefix('Bearer ')
            def case():
                response = http.get(f"/v1/swaps/{swap['id']}/recovery",headers=tech)
                response.raise_for_status(); return response.json()
            report['before'] = {'case':case(),'payments':read('payments'),'batteries':read('batteries'),
                'commands':read('device_commands'),'holds':read('resource_reservations')}
            launch(['-m','tools.phase8b_browser_legacy','--device',directory],'legacy-operator')
            web = launch([ROOT/'apps/web/node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(web_port),'--strictPort'],'web',node=True)
            wait(lambda:httpx.get(web_url+'health').status_code==200,'Web ready',25)
            publish_state(directory,case())
            with (directory/'private.json').open('x',encoding='utf8') as stream:
                json.dump({'passwords':fixture['passwords']},stream)
            with (directory/'manual.json').open('x',encoding='utf8') as stream:
                json.dump({'schema':fixture['settings'].schema,'swap_id':swap['id'],'frontend':web_url,
                    'backend':url,'ledger':str(ledger),'ready':True,'web_pid':web.pid},stream)
            env['PW_RUNTIME']=str(directory)
            browser = launch([ROOT/'apps/web/node_modules/@playwright/test/cli.js','test','legacy-recovery.spec.ts'],'playwright',node=True)
            while browser.poll() is None:
                publish_state(directory,case()); time.sleep(.2)
            report['browser_exit']=browser.returncode
            assert browser.returncode==0,'Browser failed; no retry'
            final=case(); transaction=next(r for r in read('swap_transactions') if str(r['id'])==swap['id'])
            report['after']={'case':final,'payments':read('payments'),'batteries':read('batteries'),
                'commands':read('device_commands'),'holds':read('resource_reservations'),
                'operations':read('recovery_operations'),'attestations':read('recovery_attestations'),
                'audit':read('audit_events'),'refunds':read('refunds'),'swap_state':transaction['state']}
            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                report['ledger']={t:conn.execute('SELECT * FROM '+t).fetchall() for t in
                    ('service_operations','commands','recovery_station_fence')}
                assert conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0]==1
                assert conn.execute('SELECT count(*) FROM commands').fetchone()[0]==1
                assert conn.execute('SELECT count(*) FROM recovery_station_fence').fetchone()[0]==0
            assert final['old_pin_settled'] is True and final['new_pin_delivered']=='NO'
            assert final['active_operation']['consumed_at'] and transaction['state']=='REVIEW_REQUIRED'
            assert report['after']['commands']==report['before']['commands']
            assert report['after']['payments']==report['before']['payments']
            assert report['after']['holds']==report['before']['holds']
            assert sum(r['released_at'] is None for r in read('resource_reservations'))==3
            assert not report['after']['refunds']
            pins={r['id']:r for r in read('batteries')}
            assert pins[transaction['old_battery_id']]['holder_user_id']==transaction['customer_id']
            assert pins[transaction['new_battery_id']]['compartment_id']==transaction['supply_compartment_id']
            assert sum(r['action']=='MANUAL_RECOVERY_SETTLED' for r in read('audit_events'))==1
            report['status']='BROWSER_PASSED'
    finally:
        for child in reversed(children): stop(child)
        for log in logs: log.close()
        try: next(factory)
        except StopIteration: pass
        report['demo_fingerprint_unchanged']=fingerprints(demo)==before
        demo.engine.dispose()
        (ROOT/'docs/PHASE8B_LEGACY_BROWSER.json').write_text(json.dumps(report,default=str,indent=2),encoding='utf8')
    assert report['demo_fingerprint_unchanged']


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--device': device(Path(sys.argv[2]))
    else: run()
