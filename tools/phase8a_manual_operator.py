"""Test-only local operator. Human evidence and all decisions stay in Browser."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'services/backend'),str(ROOT)]

ACTIONS={'INSPECT':'INSPECT','ACK':'AUTHORIZATION_INTENT','HANDOVER':'ACTION',
         'REINSPECT':'RECONCILE_INSPECT','CLOSE':'CLOSE_NO_EFFECT','ACK_CLOSURE':'CLOSURE_COMMITTED',
         'REBOOT':'TEST_ONLY_REBOOT'}

def dispatch(sim, action, operation):
    from simulators.device import recovery_fence as fence, recovery_reconciliation as er
    from simulators.device.service import flush
    tasks=sim.http.get('/v1/device/recovery-tasks')
    tasks.raise_for_status()
    task=next((t for t in tasks.json()['items']
               if t['operation_id']==operation and t['task_kind']==ACTIONS[action]),None)
    if task is None:
        raise ValueError('No matching authorized task; refresh Backend state')
    if action=='INSPECT':
        result=fence.transport_inspection(sim,task)
    elif action=='ACK':
        result=fence.acknowledge_authorization(sim,task)
    elif action=='HANDOVER':
        from simulators.device.recovery_handover import perform
        result=perform(sim,task,technician_token=os.environ['SERVICE_TECHNICIAN_TOKEN'])
    elif action=='REINSPECT':
        result=er.reinspect(sim,task)
        response=sim.http.post('/v1/device/recovery-observations',json=result)
        response.raise_for_status()
    elif action=='CLOSE':
        result=er.close_no_effect(sim,task)
        response=sim.http.post('/v1/device/recovery-observations',json=result)
        response.raise_for_status()
    else:
        result=er.acknowledge_closure(sim,task)
    fence.flush(sim)
    flush(sim)
    return {'action':action,'operation_id':operation,'completed':True}

def handoff(directory, ledger, fixture, swap, env, launch, read, case, report):
    from smoke_phase8a import wait
    import httpx
    api_url=env.get('P8_OPERATOR_URL','http://127.0.0.1:8030')
    web_port=int(env.get('P8_MANUAL_WEB_PORT','5180'))
    web_url=f'http://127.0.0.1:{web_port}/'
    env['DEV_API_TARGET']=api_url
    with __import__('socket').socket() as probe:
        if probe.connect_ex(('127.0.0.1',web_port))==0:
            raise RuntimeError('Manual frontend port occupied')
    launch(['-m','tools.phase8a_manual_operator','--device',str(directory)],'manual-operator')
    # launch() uses repository cwd, so the Vite root is explicit.
    import subprocess
    log=(directory/'manual-web.log').open('w',encoding='utf8')
    web=subprocess.Popen(['node',str(ROOT/'apps/web/node_modules/vite/bin/vite.js'),
        '--host','127.0.0.1','--port',str(web_port),'--strictPort'],cwd=ROOT/'apps/web',env=env,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        wait(lambda:httpx.get(web_url+'health').status_code==200,'Manual web ready',25)
        public={'schema':fixture['settings'].schema,'swap_id':swap['id'],
                'frontend':web_url,'backend':api_url,
                'ledger':str(ledger),'ready':True,'web_pid':web.pid}
        (directory/'private.json').write_text(json.dumps({'passwords':fixture['passwords']}),encoding='utf8')
        (directory/'manual.json').write_text(json.dumps(public,indent=2),encoding='utf8')
        if env.get('P8_PLAYWRIGHT_SPEC'):
            env['PW_RUNTIME']=str(directory)
            test_process=subprocess.Popen(['node',str(ROOT/'apps/web/node_modules/@playwright/test/cli.js'),
                'test',env['P8_PLAYWRIGHT_SPEC']],cwd=ROOT/'apps/web',env=env)
            while test_process.poll() is None:
                (directory/'state.json').write_text(json.dumps(case(),default=str,indent=2),encoding='utf8')
                time.sleep(.2)
            report['browser_exit']=test_process.returncode
            current_case=case()
            transaction=next(r for r in read('swap_transactions') if str(r['id'])==swap['id'])
            report['browser_db']={
                'case':{k:current_case[k] for k in ('state','version','old_pin_settled','new_pin_delivered')},
                'operations':[{k:r[k] for k in ('id','protocol_version','consumed_at','cancelled_at','supersedes_id')}
                              for r in read('recovery_operations')],
                'payment':[r['state'] for r in read('payments')],
                'holds':sum(r['released_at'] is None for r in read('resource_reservations')),
                'custody':[{k:r[k] for k in ('id','location_kind','holder_user_id','compartment_id')}
                           for r in read('batteries') if r['id'] in (transaction['old_battery_id'],transaction['new_battery_id'])],
                'audit_actions':[r['action'] for r in read('audit_events') if r['aggregate_type']=='recovery']}
            operation=current_case.get('active_operation') or {}
            report['browser_db']['accepted_proof']=[
                {**{k:p.get(k) for k in ('id','stage','source_kind','payload_hash','observed_at')},
                 **{k:p['payload'].get(k) for k in ('result','confirm','actual_serial','recipient_id')}}
                for p in operation.get('attestations',[])]
            import sqlite3
            with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as connection:
                report['browser_db']['service_effects']=connection.execute('SELECT state,effects FROM service_operations').fetchall()
                report['browser_db']['fence']=connection.execute('SELECT state FROM recovery_station_fence').fetchall()
            (directory/'browser_exit.json').write_text(json.dumps({'exit_code':test_process.returncode}))
            if test_process.returncode:
                raise RuntimeError('Browser test failed; preserve Playwright evidence')
            observed=report['browser_db']
            assert observed['payment']==['SUCCEEDED'] and observed['holds']==3
            assert not observed['case']['old_pin_settled']
            assert observed['case']['new_pin_delivered']=='UNKNOWN'
            assert transaction['state']=='REVIEW_REQUIRED'
            custody={p['id']:p for p in observed['custody']}
            assert custody[transaction['old_battery_id']]['location_kind']=='CUSTOMER'
            assert custody[transaction['old_battery_id']]['holder_user_id']==transaction['customer_id']
            assert custody[transaction['new_battery_id']]['location_kind']=='COMPARTMENT'
            scenario=env.get('PW_SCENARIO','smoke') if env['P8_PLAYWRIGHT_SPEC']=='staged.spec.ts' else 'smoke'
            expected_effects=1 if scenario in ('post','post-reject','successor','terminal-label') else 0
            assert sum(row[1] for row in observed['service_effects'])==expected_effects
            assert observed['audit_actions'].count('FOREIGN_OBJECT_RETURN_SETTLED')==(1 if scenario in ('post','successor','terminal-label') else 0)
            return
        while not (directory/'stop').exists():
            if web.poll() is not None:
                raise RuntimeError('Manual web exited')
            (directory/'state.json').write_text(json.dumps(case(),default=str,indent=2),encoding='utf8')
            time.sleep(1)
        report['manual_browser']={'status':'User verification pending','schema':public['schema']}
    finally:
        if web.poll() is None:
            web.terminate();web.wait(15)
        log.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',type=Path)
    parser.add_argument('--request',type=Path)
    parser.add_argument('--action',choices=tuple(ACTIONS))
    parser.add_argument('--operation',type=UUID)
    args=parser.parse_args()
    directory=(args.device or args.request).resolve()
    if not directory.is_relative_to(ROOT/'.cache') or not directory.is_dir():
        raise ValueError('Use retained isolated fixture runtime under .cache')
    if args.request:
        if not args.action or not args.operation:
            parser.error('Request requires action and operation')
        path=directory/('request-'+uuid4().hex+'.json')
        path.write_text(json.dumps({'action':args.action,'operation_id':str(args.operation)}),encoding='utf8')
        print(str(path))
        return
    if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise ValueError('Test schema required')
    from simulators.device.main import Simulator
    from app.config import approved_policy
    sim=Simulator('S01',os.environ['DEMO_DEVICE_KEY_S01'],base_url=os.getenv('P8_OPERATOR_URL','http://127.0.0.1:8030'),
                  ledger=directory/'ledgers/S01.sqlite3',scenario='wrong-return')
    try:
        next_cycle=0
        while not (directory/'stop').exists():
            if time.monotonic()>=next_cycle:
                sim.cycle()
                # Drain durable observations after transport loss/worker delay.
                # flush never invokes a physical service effect.
                from simulators.device.service import flush
                flush(sim)
                next_cycle=time.monotonic()+approved_policy()['telemetry_interval_seconds']
            for request in sorted(directory.glob('request-*.json')):
                result=request.with_suffix('.result.json')
                if result.exists() or request.name.endswith('.result.json'):
                    continue
                packet=json.loads(request.read_text())
                try:
                    if packet['action']=='REBOOT':
                        # Explicit test IPC only: real new boot and unchanged
                        # durable model/ledger, no fabricated device observation.
                        old_boot=sim.boot
                        sim.close()
                        sim=Simulator('S01',os.environ['DEMO_DEVICE_KEY_S01'],
                            base_url=os.getenv('P8_OPERATOR_URL','http://127.0.0.1:8030'),
                            ledger=directory/'ledgers/S01.sqlite3',scenario='wrong-return')
                        sim.cycle()
                        outcome={'completed':True,'old_boot':old_boot,'new_boot':sim.boot}
                    else:
                        outcome=dispatch(sim,packet['action'],str(UUID(packet['operation_id'])))
                except Exception as error:
                    outcome={'completed':False,'error_type':type(error).__name__}
                result.write_text(json.dumps(outcome),encoding='utf8')
            time.sleep(.1)
    finally:
        sim.close()

if __name__=='__main__':
    main()
