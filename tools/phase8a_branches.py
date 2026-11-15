"""C/D/E/F extension of smoke_phase8a; all physical observations use real HTTP.

No direct custody writes, command age rewrites or generated observations.
"""
from smoke_phase8a import *
import time
from datetime import datetime, timezone


def crash_test_app():
    """E-only OS crash at the final audit, before PostgreSQL commit.

    Explicit test factory; never imported by app.main or production workers.
    The signal and one-shot marker are retained as evidence, not deleted.
    """
    from app.application import recovery
    signal = Path(os.environ['P8_TEST_SETTLE_CRASH_SIGNAL']).resolve()
    if not signal.is_relative_to(ROOT/'.cache') or not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise RuntimeError('Crash probe requires isolated schema/runtime')
    original = recovery.audit
    def audit(session, db, actor, case, action, after):
        result = original(session, db, actor, case, action, after)
        if action=='RECOVERY_NO_EFFECT_CLOSED' and os.environ.get('P8_FINAL_CLOSE_DIR'):
            from phase8a_final_races import marker
            marker(Path(os.environ['P8_FINAL_CLOSE_DIR']),session)
        if action in ('FOREIGN_OBJECT_RETURN_SETTLED','RECOVERY_NO_EFFECT_CLOSED') and signal.exists() and os.environ.get('P8_TEST_POST_COMMIT')!='1':
            signal.with_suffix('.crashed').write_text('exit91 after audit before commit', encoding='utf-8')
            os._exit(91)
        return result
    recovery.audit = audit
    application=create_app()
    if os.environ.get('P8_TEST_POST_COMMIT')!='1':
        return application
    async def post_commit_crash(scope, receive, send):
        async def intercept(message):
            path,status = ('/v1/device/recovery-observations',202) if os.environ.get('P8_TEST_CLOSURE_CRASH') else ('/recovery/settle',200)
            if (scope.get('path','').endswith(path) and signal.exists()
                    and message['type']=='http.response.start' and message['status']==status):
                # Function-scoped DB dependency has committed before response
                # start; the other OS Backend independently verifies durability.
                signal.with_suffix('.crashed').write_text('exit92 before response start; verify committed DB',encoding='utf-8')
                os._exit(92)
            await send(message)
        await application(scope,receive,intercept)
    return post_commit_crash


def run(branch):
    primary_port=int(os.getenv('P8_TEST_API_PORT','8030'))
    secondary_port=primary_port+1
    primary_url=f'http://127.0.0.1:{primary_port}'
    secondary_url=f'http://127.0.0.1:{secondary_port}'
    expired = '--expired-recovery' in sys.argv
    if expired and branch not in ('J','K'):
        raise ValueError('Use J for no-effect or K for historical effect')
    assert branch in ('CD', 'E', 'F', 'I', 'J', 'K', 'L')
    for port in (primary_port, secondary_port):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('Test port occupied')
    demo = Database(Settings.from_env()); fingerprint = fingerprints(demo)
    factory = environment.__wrapped__(); fixture = next(factory); db = fixture['seed_db']
    directory = ROOT/'.cache'/('p8-'+branch+'-'+uuid4().hex[:10]); directory.mkdir()
    ledger = directory/'ledgers'; ledger.mkdir()
    env = dict(os.environ, DATABASE_SCHEMA=fixture['settings'].schema,
        PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8',
        **{'DEMO_DEVICE_KEY_'+code: key for code, key in fixture['keys'].items()})
    cross = '--cross-expiry' in sys.argv
    staged_wait = '--staged-freshness' in sys.argv
    if (cross and not expired) or (staged_wait and branch!='E'):
        raise ValueError('Cross expiry requires an expiry branch; staged freshness requires E')
    if branch in ('E','K','L'):
        env['P8_TEST_ACTION_SIGNAL']=str(directory/'operator-action.txt')
        env['P8_TEST_HOLD_POST_RECEIPT']='1'
    if branch == 'E' or expired:
        if expired and branch=='J':
            env.update(P8_TEST_POST_COMMIT='1',P8_TEST_CLOSURE_CRASH='1')
        if '--post-commit-crash' in sys.argv:
            env['P8_TEST_POST_COMMIT']='1'
        env['P8_TEST_SETTLE_CRASH_SIGNAL']=str(directory/'settlement-crash.signal')
        env['PYTHONPATH']=os.pathsep.join((str(ROOT/'services/backend'),str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT)))
    processes, logs, checks = [], [], {k: [] for k in ('C', 'D') if branch == 'CD'}
    if branch != 'CD': checks[branch] = []
    def check(group, label, condition=True):
        if not condition:
            report.setdefault('failed_checks', []).append({'branch':group,'check':label})
            raise AssertionError(label)
        checks[group].append(label)
    def launch(args, name):
        log = (directory/(name+'.log')).open('w', encoding='utf-8'); logs.append(log)
        child = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(child); return child
    def stop(child):
        if child.poll() is None: child.terminate(); child.wait(timeout=15)
    def physical(name, operation=None):
        args = ['tools/phase8a_process.py', '--station', 'S01', '--url', primary_url,
            '--ledger-dir', str(ledger), '--scenario', 'wrong-return' if branch in ('E','I','J','K','L') else 'physical']
        if operation: args += ['--service-operation', operation['id']]
        return launch(args, name)
    def read(table, predicate=None):
        t = db.table(table)
        with db.sessions() as session:
            query = select(t)
            if predicate is not None: query = query.where(predicate(t))
            return [dict(r) for r in session.execute(query).mappings()]
    report = {'branch': branch, 'checks': checks, 'schema': fixture['settings'].schema,
        'runtime': str(directory.relative_to(ROOT)), 'status': 'FAILED'}
    try:
        # Existing fixture preparation uses domain services and a mock charge
        # outcome. Payment provider E2E is outside this recovery-only runner.
        for port in (primary_port, secondary_port):
            api_factory='app.main:create_app'
            if cross or staged_wait or '--final-closure' in sys.argv:
                env.update(P8_RACE_DIR=str(directory),PGAPPNAME=f'{directory.name}-{port}')
                api_factory='tools.phase8a_final_races:app'
            launch(['-m', 'uvicorn', api_factory, '--factory', '--host', '127.0.0.1',
                '--port', str(port), '--no-access-log'], 'api-'+str(port))
            wait(lambda:httpx.get(f'http://127.0.0.1:{port}/health', timeout=1).status_code == 200, 'API ready')
        with TestClient(create_app(fixture['settings'])) as client:
            customer = login(client, fixture); swap = book(client, fixture, customer, db)
            assert consent(client, customer, swap).status_code == 202
            payment.tick(client.app.state.db, transport=outcome)
        identity = UUID(swap['id'])
        def state(): return read('swap_transactions', lambda t:t.c.id == identity)[0]
        def commands(): return read('device_commands', lambda t:t.c.swap_id == identity)
        def holds(): return len(read('resource_reservations', lambda t:(t.c.swap_id == identity)&t.c.released_at.is_(None)))
        def audits(): return read('audit_events', lambda t:t.c.correlation_id == identity)
        def pin(key): return read('batteries', lambda t:t.c.id == UUID(swap[key]))[0]
        charge = read('payments', lambda t:t.c.swap_id == identity)[0]
        def custody(pin):
            return {key:pin[key] for key in ('id','location_kind','compartment_id','holder_user_id')}
        initial_new = custody(pin('new_battery_id'))
        launch(['-m', 'app.workers.device'], 'worker')
        sim = physical('S01-start')
        with httpx.Client(base_url=primary_url, timeout=20) as first, httpx.Client(base_url=secondary_url, timeout=20) as second:
            tech = login(first, fixture, 'technician'); customer = login(first, fixture)
            env['SERVICE_TECHNICIAN_TOKEN'] = tech['Authorization'].removeprefix('Bearer ')
            base = f"/v1/swaps/{swap['id']}/recovery"
            def case(): return first.get(base, headers=tech).json()
            def begin(purpose):
                r = first.post(base+'/evidence', headers={**tech, 'Idempotency-Key':str(uuid4())}, json={
                    'expected_version':case()['version'], 'note':'Actual simulator inspection',
                    'statement':{'kind':'BEGIN_OPERATION','purpose':purpose}})
                assert r.status_code == 200, r.text
                return r.json()['active_operation']
            def settle(op):
                return first.post(base+'/settle', headers={**tech,'Idempotency-Key':str(uuid4())},json={
                    'expected_version':case()['version'],'operation_id':op['id'],'resolution_note':'Verified model and independent parties'})
            def proof(op):
                wait(lambda:any(a['source_kind']=='SIMULATOR' for a in case()['active_operation']['attestations']), 'Service observation', 30)
                item = next(a for a in case()['active_operation']['attestations'] if a['source_kind']=='SIMULATOR')
                assert item['payload']['result']=='OBSERVED', item['payload']['result']
                r = first.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
                    'expected_version':case()['version'],'note':'Serial inspected','statement':{
                    'kind':'TECHNICIAN_ATTEST','operation_id':op['id'],'context_hash':op['context_hash'],
                    'actual_serial':item['payload']['actual_serial'],'observation':'CONFIRM'}})
                assert r.status_code == 200,r.text
                r = first.post(base+'/confirmations',headers={**customer,'Idempotency-Key':str(uuid4())},json={
                    'operation_id':op['id'],'context_hash':op['context_hash'],'confirm':True})
                assert r.status_code == 201,r.text
            wait(lambda:state()['state']=='REVIEW_REQUIRED', 'Physical timeout/wrong-return review', 100)
            group = 'C' if branch=='CD' else branch
            check(group,'Review retains charge, three holds and supply custody',
                holds()==3 and custody(pin('new_battery_id'))==initial_new and read('payments',lambda t:t.c.swap_id==identity)[0]==charge)
            device_id = commands()[0]['device_id']
            old_boot = read('devices',lambda t:t.c.id==device_id)[0]['boot_id']
            stop(sim)
            if branch=='F':
                time.sleep(16)
                check('F','Offline beyond freshness retains review, custody and holds',
                    state()['state']=='REVIEW_REQUIRED' and holds()==3 and custody(pin('new_battery_id'))==initial_new)
            before_commands = commands()
            sim = physical('S01-reboot')
            wait(lambda:read('devices',lambda t:t.c.id==device_id)[0]['boot_id'] != old_boot, 'Reconnect with new accepted boot',30)
            time.sleep(2)
            check(group,'Restart retains command count, no custody completion',len(commands())==len(before_commands) and state()['state']=='REVIEW_REQUIRED' and holds()==3)
            # Presence mismatch can enter review before physical expiry. Wait
            # on the original clock, with fresh snapshots continuing normally.
            deadline=max(c['created_at'].timestamp() for c in commands())+60
            wait(lambda:time.time()>deadline+2, 'Original physical deadline elapsed',65)
            time.sleep(5)
            before_commands=commands()
            if branch in ('CD','F'):
                with sqlite3.connect(ledger/'S01.sqlite3') as conn:
                    late=[json.loads(r[0]) for r in conn.execute('SELECT body FROM events WHERE sent=0')]
                late=[e for e in late if e['kind'] in ('DOOR','PRESENCE')]
                assert late
                for event in late:
                    r=first.post('/v1/device/events',headers={'X-Device-Key':fixture['keys']['S01']},json=event)
                    assert r.status_code==202,r.text
                wait(lambda:all(read('device_events',lambda t:t.c.id==UUID(e['event_id']))[0]['processed_at'] for e in late),'Late events processed',20)
                check(group,'Original late events rejected without automatic pickup custody',
                    all(not read('device_events',lambda t:t.c.id==UUID(e['event_id']))[0]['accepted'] for e in late)
                    and state()['state']=='REVIEW_REQUIRED' and holds()==3 and custody(pin('new_battery_id'))==initial_new)
                op = begin('VERIFY_NEW_DELIVERY')
                r = settle(op)
                check(group,'Empty slot/EXECUTED without three proof sources cannot settle',r.status_code in (409,422) and holds()==3 and custody(pin('new_battery_id'))==initial_new)
                if branch=='F':
                    stop(sim)
                    env['P8_TEST_CRASH_SERVICE']='1'
                    sim=physical('S01-service-prepared-crash',op)
                    env.pop('P8_TEST_CRASH_SERVICE')
                    wait(lambda:sim.poll() is not None,'Crash after durable PREPARED',30)
                    sim=physical('S01-service-unknown-retry',op)
                    time.sleep(5)
                    with sqlite3.connect(ledger/'S01.sqlite3') as conn:
                        entry=conn.execute('SELECT state,effects,observation FROM service_operations WHERE id=?',(op['id'],)).fetchone()
                    check('F','Prepared crash survives restart without repeated effect',entry==('UNKNOWN',0,None) and holds()==3)
                    wait(lambda:time.time()>datetime.fromisoformat(op['expires_at'].replace('Z','+00:00')).timestamp(), 'Real operation TTL elapsed',125)
                    op=begin('VERIFY_NEW_DELIVERY')
                    # Reboot after a real observation; do not edit that receipt.
                    stop(sim); sim=physical('S01-inspect',op); proof(op)
                    stop(sim); sim=physical('S01-proof-boot-change'); time.sleep(3)
                    r=settle(op)
                    check('F','Old boot proof rejected after reboot',r.status_code==422 and holds()==3)
                else:
                    stop(sim); sim=physical('S01-inspect',op); proof(op)
                    body={'expected_version':case()['version'],'operation_id':op['id'],'resolution_note':'Verified delivery after deadline'}
                    key=str(uuid4())
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        results=list(pool.map(lambda http:http.post(base+'/settle',headers={**tech,'Idempotency-Key':key},json=body),(first,second)))
                    report['settlement_responses']=[{'status':r.status_code,'code':r.json().get('code')} for r in results]
                    check('D','Two OS Backends replay one settlement',all(r.status_code==200 for r in results) and results[0].json()==results[1].json())
                    check('D','Manual completion commits exact holder and releases terminal holds',state()['state']=='COMPLETED' and holds()==0 and pin('new_battery_id')['holder_user_id']==state()['customer_id'])
                    check('D','One manual audit; command and Payment history unchanged',len([a for a in audits() if a['action']=='MANUAL_RECOVERY_SETTLED'])==1 and commands()==before_commands and read('payments',lambda t:t.c.swap_id==identity)[0]==charge)
            else:
                check(group,'Wrong return never issues OPEN_SUPPLY or imports foreign battery',all(c['kind']!='OPEN_SUPPLY' for c in commands()) and not read('batteries',lambda t:t.c.serial=='SIMULATED-WRONG-BATTERY'))
                check(group,'Old obligation not settled by foreign object',pin('old_battery_id')['holder_user_id']==state()['customer_id'] and not case()['old_pin_settled'])
                if '--operator-check' in sys.argv:
                    from phase8a_operator_verify import verify
                    stop(sim)
                    env['P8_OPERATOR_URL']=primary_url
                    verify(directory,fixture,swap,env,launch,first,second,tech,customer,case,read,report)
                    report['status']='PASSED'
                    return
                if '--manual-browser' in sys.argv:
                    if branch!='E':
                        raise ValueError('Manual staged fixture requires E')
                    from phase8a_manual_operator import handoff
                    stop(sim)
                    env['P8_OPERATOR_URL']=primary_url
                    handoff(directory,ledger,fixture,swap,env,launch,read,case,report)
                    report['status']='BROWSER_PASSED' if env.get('P8_PLAYWRIGHT_SPEC') else 'MANUAL_STOPPED'
                    return
                r=first.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
                    'expected_version':case()['version'],'note':'Inspect foreign presenter',
                    'statement':{'kind':'BEGIN_OPERATION','purpose':'RETURN_FOREIGN_OBJECT'}})
                report['foreign_operation_http']=r.status_code
                if r.status_code==200 and branch in ('E','I','J','K','L'):
                    op=r.json()['active_operation']
                    original_old=custody(pin('old_battery_id'))
                    stop(sim);sim=physical('S01-readonly-inspection',op)
                    wait(lambda:len(case()['active_operation']['attestations'])==1,'Inspection persisted via real API',40)
                    receipt=case()['active_operation']['attestations'][0]
                    check(group,'Real simulator receipt accepted in PRE_ACTION_INSPECTION',receipt['stage']=='PRE_ACTION_INSPECTION' and receipt['payload']['actual_serial']=='SIMULATED-WRONG-BATTERY' and receipt['payload']['effect_count_delta']==0)
                    with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                        packet=json.loads(conn.execute('SELECT packet FROM recovery_inspection_outbox').fetchone()[0])
                        check(group,'Durable inspection fence remains ACTIVE',conn.execute('SELECT state FROM recovery_station_fence').fetchone()[0]=='ACTIVE')
                    replay=first.post('/v1/device/recovery-observations',headers={'X-Device-Key':fixture['keys']['S01']},json=packet)
                    check(group,'Receipt replay is idempotent',replay.status_code==202 and replay.json()['duplicate'] is True and len(case()['active_operation']['attestations'])==1)
                    check(group,'Inspection preserves network custody charge and three holds',custody(pin('old_battery_id'))==original_old and custody(pin('new_battery_id'))==initial_new and holds()==3 and read('payments',lambda t:t.c.swap_id==identity)[0]==charge and state()['state']=='REVIEW_REQUIRED')
                    if branch in ('E','J','K','L'):
                        binding={'operation_id':op['id'],'context_hash':op['context_hash'],'stage':'PRE_ACTION_INSPECTION',
                                 'receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
                        attested=first.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
                            'expected_version':case()['version'],'note':'Independent pre-action serial and presenter',
                            'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}})
                        assert attested.status_code==200,attested.text
                        confirmed=first.post(base+'/confirmations',headers={**customer,'Idempotency-Key':str(uuid4())},json={**binding,'confirm':True})
                        assert confirmed.status_code==201,confirmed.text
                        body={'expected_version':case()['version'],'note':'Transport authorization only',
                              'statement':{'kind':'AUTHORIZE_ACTION','operation_id':op['id'],'context_hash':op['context_hash']}}
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            results=list(pool.map(lambda http:http.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json=body),(first,second)))
                        report['authorization_responses']=[{'status':x.status_code,'code':x.json().get('code')} for x in results]
                        check(group,'Two OS Backends create one authorization',sorted(x.status_code for x in results)==[200,409]
                              and len(read('recovery_action_authorizations'))==1)
                        wait(lambda:bool(case()['active_operation']['authorization']['transport_acknowledged']), 'Durable authorization acknowledgment',12)
                        check(group,'Authenticated simulator persists one transport ACK with no action permit',
                              len(read('recovery_authorization_acks'))==1 and case()['active_operation']['authorization']['effect_allowed'] is False)
                        with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                            ack_packet=json.loads(conn.execute('SELECT packet FROM recovery_authorization_outbox').fetchone()[0])
                            check(group,'No prepared service/effect and fence remains active',
                                  conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]==0
                                  and conn.execute('SELECT state FROM recovery_station_fence').fetchone()[0]=='ACTIVE')
                        replay=second.post('/v1/device/recovery-observations',headers={'X-Device-Key':fixture['keys']['S01']},json=ack_packet)
                        check(group,'Second Backend replays same ACK without new audit',replay.status_code==202 and replay.json()['duplicate']
                              and len([a for a in audits() if a['action']=='RECOVERY_AUTHORIZATION_ACKNOWLEDGED'])==1)
                        check(group,'Authorization preserves custody payment three holds and review',
                              custody(pin('old_battery_id'))==original_old and custody(pin('new_battery_id'))==initial_new
                              and holds()==3 and read('payments',lambda t:t.c.swap_id==identity)[0]==charge and state()['state']=='REVIEW_REQUIRED')
                        if branch in ('E','K','L'):
                            permit=case()['active_operation']['authorization']
                            body={'expected_version':case()['version'],'note':'Explicit test operator activation',
                                'statement':{'kind':'AUTHORIZE_ACTION','phase':'ACTIVATE','operation_id':op['id'],
                                    'context_hash':op['context_hash'],'authorization_id':permit['id'],
                                    'acknowledgment_id':permit['acknowledgment_id']}}
                            key=str(uuid4())
                            with ThreadPoolExecutor(max_workers=2) as pool:
                                results=list(pool.map(lambda http:http.post(base+'/evidence',headers={**tech,'Idempotency-Key':key},json=body),(first,second)))
                            check(group,'Two OS Backends activate one acknowledged intent',
                                all(x.status_code==200 for x in results) and results[0].json()==results[1].json()
                                and len(read('recovery_action_activations'))==1)
                            (directory/'operator-action.txt').write_text(op['id'],encoding='utf-8')
                            def durable_effect():
                                with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                                    return conn.execute('SELECT observation FROM service_operations WHERE id=?',(op['id'],)).fetchone()
                            wait(durable_effect, 'Real activated handover committed locally',20)
                            if branch=='K':
                                stop(sim)  # Actual process loss after effect, before Backend receipt.
                            check(group,'Durable effect exists before Backend POST receipt',
                                not any(a['stage']=='POST_ACTION_RECEIPT' for a in case()['active_operation']['attestations']))
                            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                                service_row=conn.execute('SELECT state,effects,observation FROM service_operations WHERE id=?',(op['id'],)).fetchone()
                                post_packet=json.loads(service_row[2])
                                check(group,'One physical foreign-object effect and durable POST receipt',
                                    service_row[:2]==('OBSERVED',1) and conn.execute('SELECT state FROM recovery_action_ledger').fetchone()[0]=='OBSERVED'
                                    and conn.execute('SELECT customer_id FROM service_positions WHERE serial=?',('SIMULATED-WRONG-BATTERY',)).fetchone()[0]==str(state()['customer_id']))
                            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                                original_snapshot=json.loads(conn.execute('SELECT body FROM events WHERE id=?',
                                    (post_packet['snapshot_event_id'],)).fetchone()[0])
                            source_response=first.post('/v1/device/events',headers={'X-Device-Key':fixture['keys']['S01']},json=original_snapshot)
                            assert source_response.status_code==202,source_response.text
                            wait(lambda:bool(read('device_events',lambda t:t.c.id==UUID(post_packet['snapshot_event_id']))[0]['processed_at']),
                                 'Original source snapshot processed',10)
                            with ThreadPoolExecutor(max_workers=2) as pool:
                                responses=list(pool.map(lambda http:http.post('/v1/device/recovery-observations',
                                    headers={'X-Device-Key':fixture['keys']['S01']},json=post_packet),(first,second)))
                            check(group,'Two OS Backends race initial receipt with one insertion and one replay',
                                all(x.status_code==202 for x in responses) and sorted(x.json()['duplicate'] for x in responses)==[False,True]
                                and len([a for a in audits() if a['action']=='RECOVERY_POST_ACTION_RECEIPT_STORED'])==1)
                            if branch in ('E','L'):
                                receipt=next(a for a in case()['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT')
                                # Backend process restart after durable receipt, before human testimony.
                                # The second API child is launched before the worker/simulator.
                                stop(processes[1])
                                restarted=launch(['-m','uvicorn','phase8a_branches:crash_test_app' if branch=='E' else 'app.main:create_app',
                                    '--factory','--host','127.0.0.1','--port',str(secondary_port),'--no-access-log'],'api-8031-restart')
                                wait(lambda:second.get('/health').status_code==200,'Second Backend restarted',15)
                                wait(lambda:any(e['kind']=='SNAPSHOT' and e['accepted'] and e['processed_at']
                                    and e['observed_at']>=datetime.fromisoformat(post_packet['observed_at'])
                                    for e in read('device_events',lambda t:t.c.device_id==device_id)),
                                    'Fresh actual post-action snapshot',10)
                                binding={'operation_id':op['id'],'context_hash':op['context_hash'],'stage':'POST_ACTION_RECEIPT',
                                    'receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
                                body={'expected_version':case()['version'],'note':'Post-action witnessed receipt',
                                    'statement':{**binding,'kind':'TECHNICIAN_ATTEST','actual_serial':post_packet['actual_serial'],'observation':'CONFIRM'}}
                                key=str(uuid4())
                                with ThreadPoolExecutor(max_workers=2) as pool:
                                    results=list(pool.map(lambda http:http.post(base+'/evidence',headers={**tech,'Idempotency-Key':key},json=body),(first,second)))
                                check(group,'Two restarted OS Backends persist one Technician POST statement',
                                    all(r.status_code==200 for r in results))
                                customer_keys=[str(uuid4()),str(uuid4())]
                                with ThreadPoolExecutor(max_workers=2) as pool:
                                    results=list(pool.map(lambda pair:pair[0].post(base+'/confirmations',headers={**customer,'Idempotency-Key':pair[1]},json={**binding,'confirm':True}),zip((first,second),customer_keys)))
                                check(group,'Two OS Backends race Customer POST statement without overwrite',sorted(r.status_code for r in results)==[201,409])
                                winner=next(i for i,r in enumerate(results) if r.status_code==201)
                                replay_human=first.post(base+'/confirmations',headers={**customer,'Idempotency-Key':customer_keys[winner]},json={**binding,'confirm':True})
                                check(group,'Human replay retains identity and exactly two human audits',
                                    replay_human.status_code==201 and replay_human.json()==results[winner].json()
                                    and len([a for a in audits() if a['action']=='RECOVERY_POST_ACTION_CONFIRMED'])==2)
                                post_rows=[a for a in case()['active_operation']['attestations'] if a['stage']=='POST_ACTION_RECEIPT']
                                check(group,'Two independent human sources reference exact durable POST receipt',
                                    len(post_rows)==3 and {a['source_kind'] for a in post_rows}=={'SIMULATOR','TECHNICIAN','CUSTOMER'}
                                    and all(a['reference_receipt_id']==receipt['id'] and a['payload']['confirm'] for a in post_rows if a['source_kind']!='SIMULATOR'))
                                if staged_wait:
                                    from phase8a_final_races import staged_freshness
                                    staged_freshness(first,case,post_rows,db,tech,base,op,report,directory,
                                                     [processes[0].pid,restarted.pid])
                                    check(group,'Freshness crossed during a proven PG row wait',
                                          not case()['active_operation']['consumed_at'] and holds()==3 and
                                          not any(a['action']=='FOREIGN_OBJECT_RETURN_SETTLED' for a in audits()))
                                elif branch=='E':
                                    body={'expected_version':case()['version'],'operation_id':op['id'],
                                          'resolution_note':'Staged foreign-object settlement only'}
                                    keys=[str(uuid4()),str(uuid4())]
                                    Path(env['P8_TEST_SETTLE_CRASH_SIGNAL']).write_text('crash before commit',encoding='utf-8')
                                    disconnected=False
                                    try:
                                        second.post(base+'/settle',headers={**tech,'Idempotency-Key':keys[0]},json=body)
                                    except httpx.TransportError:
                                        disconnected=True
                                    restarted.wait(timeout=10)
                                    post_commit=env.get('P8_TEST_POST_COMMIT')=='1'
                                    committed=bool(case()['active_operation']['consumed_at'])
                                    success_audits=len([a for a in audits() if a['action']=='FOREIGN_OBJECT_RETURN_SETTLED'])
                                    report['crash']={'post_commit':post_commit,'exit_code':restarted.returncode,
                                        'http_disconnected':disconnected,'consumed_after_crash':committed,'success_audits_after_crash':success_audits}
                                    check(group,'Backend OS crash after commit before HTTP preserves durable result' if post_commit else 'Backend OS crash before commit rolls back consumption audit and request',
                                        disconnected and restarted.returncode==(92 if post_commit else 91)
                                        and committed==post_commit and success_audits==int(post_commit) and holds()==3)
                                    launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(secondary_port),'--no-access-log'],'api-8031-after-crash')
                                    wait(lambda:second.get('/health').status_code==200,'Backend recovered from actual OS crash',15)
                                    with ThreadPoolExecutor(max_workers=2) as pool:
                                        results=list(pool.map(lambda pair:pair[0].post(base+'/settle',headers={**tech,'Idempotency-Key':pair[1]},json=body),zip((first,second),keys)))
                                    report['settlement_responses']=[{'status':r.status_code,'code':r.json().get('code')} for r in results]
                                    check(group,'Two OS Backends settle once with different keys',sorted(r.status_code for r in results)==[200,409])
                                    winner=next(i for i,r in enumerate(results) if r.status_code==200)
                                    with ThreadPoolExecutor(max_workers=2) as pool:
                                        replays=list(pool.map(lambda http:http.post(base+'/settle',headers={**tech,'Idempotency-Key':keys[winner]},json=body),(first,second)))
                                    check(group,'Lost response replay on both Backends returns same committed settlement',
                                        all(r.status_code==200 and r.json()==results[winner].json() for r in replays))
                                    check(group,'One foreign audit and consumed operation; case remains open',
                                        len([a for a in audits() if a['action']=='FOREIGN_OBJECT_RETURN_SETTLED'])==1
                                        and bool(case()['active_operation']['consumed_at']) and case()['state']=='EVIDENCE_RECORDED'
                                        and not case()['old_pin_settled'] and case()['new_pin_delivered']!='YES')
                                    check(group,'Settlement does not issue supply or mutate custody charge holds',
                                        all(c['kind']!='OPEN_SUPPLY' for c in commands()) and holds()==3
                                        and custody(pin('old_battery_id'))==original_old and custody(pin('new_battery_id'))==initial_new
                                        and read('payments',lambda t:t.c.swap_id==identity)[0]==charge)
                                stop(sim)
                            env.pop('P8_TEST_HOLD_POST_RECEIPT')
                            sim=physical('S01-post-effect-restart')
                            time.sleep(3)
                            replay=second.post('/v1/device/recovery-observations',headers={'X-Device-Key':fixture['keys']['S01']},json=post_packet)
                            check(group,'Post-effect restart retains receipt without custody or release',
                                replay.status_code==202 and replay.json()['duplicate'] and not case()['old_pin_settled']
                                and custody(pin('old_battery_id'))==original_old and custody(pin('new_battery_id'))==initial_new
                                and holds()==3 and read('payments',lambda t:t.c.swap_id==identity)[0]==charge and state()['state']=='REVIEW_REQUIRED')
                elif r.status_code==200:
                    op=r.json()['active_operation']
                    incomplete=settle(op)
                    check('E','Missing foreign proof cannot settle old obligation',incomplete.status_code==422 and not case()['old_pin_settled'] and holds()==3)
                    stop(sim);sim=physical('S01-foreign',op);proof(op)
                    r=settle(op)
                    check('E','Foreign handover settles object only',r.status_code==200 and not r.json()['old_pin_settled'] and holds()==3)
                else:
                    report['blocked']=['Foreign handover blocked by command reconciliation: '+r.json().get('code','ERROR')]
            if expired:
                from phase8a_expiry_smoke import verify
                final_close=None
                if '--final-closure' in sys.argv:
                    assert branch=='J'
                    final_close=directory/'committed-closure'
                    final_close.mkdir()
                    env['P8_FINAL_CLOSE_DIR']=str(final_close)
                stop(processes[1])
                killed=launch(['-m','uvicorn','phase8a_branches:crash_test_app','--factory','--host','127.0.0.1',
                               '--port',str(secondary_port),'--no-access-log'],'expiry-fault-api')
                wait(lambda:second.get('/health').status_code==200,'Fault API ready')
                def restart_station(current=None):
                    nonlocal sim
                    stop(sim)
                    sim=physical('expiry-'+uuid4().hex[:6],current)
                active=None
                if cross:
                    from phase8a_final_races import cross_expiry
                    active=cross_expiry(branch,first,second,case,op,base,tech,db,directory,report,
                                 [processes[0].pid,killed.pid])
                verify(branch, op, base, tech, customer, fixture['keys']['S01'], first, second, case, read, audits,
                       ledger, env, killed, launch, restart_station, lambda label,ok:check(group,label,ok),active,
                       (db,report,final_close,processes[0].pid) if final_close else None)
                check(group,'Expiry decision preserves custody, charge, holds and review',
                      custody(pin('old_battery_id'))==original_old and custody(pin('new_battery_id'))==initial_new
                      and read('payments',lambda t:t.c.swap_id==identity)[0]==charge and holds()==3
                      and not case()['old_pin_settled'] and state()['state']=='REVIEW_REQUIRED')
            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                report['ledger_commands']=[dict(zip(('id','status','effects'),r)) for r in conn.execute('SELECT id,status,effects FROM commands')]
                report['service_operations']=[dict(zip(('state','effects'),r)) for r in conn.execute('SELECT state,effects FROM service_operations')]
                check(group,'No duplicate command or service physical effect',all(r['effects']<=1 for r in report['ledger_commands']+report['service_operations']))
            report['database']={'state':state()['state'],'holds':holds(),'payment':charge['state'],
                'old_location':pin('old_battery_id')['location_kind'],'new_location':pin('new_battery_id')['location_kind'],
                'refund_count':len(read('refunds')),'audit_actions':[a['action'] for a in audits()]}
        report['status']='PARTIAL' if report.get('blocked') else 'PASSED'
    finally:
        for child in reversed(processes): stop(child)
        for log in logs: log.close()
        if 'state' in locals():
            report.setdefault('database', {'state':state()['state'],'holds':holds(),
                'old_location':pin('old_battery_id')['location_kind'],
                'new_location':pin('new_battery_id')['location_kind']})
        report['demo_fingerprint_unchanged']=fingerprints(demo)==fingerprint
        assert report['demo_fingerprint_unchanged']
        demo.engine.dispose()
        try: next(factory)
        except StopIteration: pass
        (ROOT/'docs'/('PHASE8A_E2E_'+branch+'.json')).write_text(json.dumps(report,default=str,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,default=str,indent=2))
