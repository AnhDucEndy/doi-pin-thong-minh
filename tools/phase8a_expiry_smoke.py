"""Expiry extension of the real J/K process fixture; all decisions travel over HTTP."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import httpx
from smoke_phase8a import wait


def verify(branch, op, base, tech, customer, device_key, first, second, case, read, audits,
           ledger, env, killed, launch, restart_station, check, active=None, final_close=None):
    successor = branch=='K'
    def local(sql):
        with sqlite3.connect((ledger/'S01.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
            return conn.execute(sql).fetchall()
    def headers(actor,key=None):
        return {**actor,'Idempotency-Key':key or str(uuid4())}
    if active is None:
        wait(lambda:datetime.now(timezone.utc)>=datetime.fromisoformat(op['expires_at']), 'Original expiry',130)
        body={'expected_version':case()['version'],'note':'Expired foreign operation',
              'statement':{'kind':'REINSPECT_OPERATION' if successor else 'CLOSE_NO_EFFECT',
                           'operation_id':op['id'],'context_hash':op['context_hash']}}
        keys=[str(uuid4()),str(uuid4())]
        def issue(pair):
            http,key=pair
            return http.post(base+'/evidence',headers=headers(tech,key),json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(issue,zip((first,second),keys)))
        check('Concurrent expired-operation requests commit once', sorted(r.status_code for r in responses)==[200,409])
        index=next(i for i,r in enumerate(responses) if r.status_code==200)
        assert issue((second,keys[index])).json()==responses[index].json()
        active=responses[index].json()['active_operation']
    if not successor:
        env['P8_TEST_HOLD_CLOSURE']='1'
    restart_station(active)
    if successor:
        wait(lambda:case()['active_operation']['attestations'],'Successor current proof',30)
        observation=case()['active_operation']['attestations'][0]
        payload=observation['payload']
        check('Current external model observed after reboot', payload['boot_id']!=payload['historical_receipt']['boot_id']
              and payload['recipient_id']==op['customer_id'] and payload['effect_count_delta']==0)
        ref={'operation_id':active['id'],'context_hash':active['context_hash'],'stage':'RECONCILIATION_INSPECTION',
             'receipt_id':observation['id'],'receipt_hash':observation['payload_hash']}
        res=first.post(base+'/evidence',headers=headers(tech),json={'expected_version':case()['version'],
            'note':'Observed current possession','statement':{**ref,'kind':'TECHNICIAN_ATTEST',
            'actual_serial':payload['actual_serial'],'observation':'CONFIRM'}})
        assert res.status_code==200,res.text
        res=first.post(base+'/confirmations',headers=headers(customer),json={**ref,'confirm':True})
        assert res.status_code==201,res.text
        path=base+'/settle'
        auth=headers(tech)
        decision={'expected_version':case()['version'],'operation_id':active['id'],'resolution_note':'Foreign possession verified'}
    else:
        wait(lambda:local('SELECT packet FROM recovery_closure_outbox'),'Local closure outbox',30)
        check('Station fence retained before Backend commit',local('SELECT state FROM recovery_station_fence')==[('ACTIVE',)])
        decision=json.loads(local('SELECT packet FROM recovery_closure_outbox')[0][0])
        path='/v1/device/recovery-observations'
        auth={'X-Device-Key':device_key}
    Path(env['P8_TEST_SETTLE_CRASH_SIGNAL']).write_text('armed',encoding='utf-8')
    def submit_receipt():
        try:
            response=second.post(path,headers=auth,json=decision)
            raise AssertionError(f'Crash boundary not reached: HTTP {response.status_code}')
        except httpx.TransportError:
            pass
    if final_close:
        from sqlalchemy import text
        db,report,directory,first_pid=final_close
        initial=case()
        original_operations=read('recovery_operations')
        for state in (None,'PREPARED','UNKNOWN'):
            invalid=dict(decision)
            if state is None:
                invalid.pop('prior_effect_state')
            else:
                invalid['prior_effect_state']=state
            refused=first.post(path,headers=auth,json=invalid)
            check('No-effect receipt refused for witness '+str(state),
                  refused.status_code==422 and read('recovery_operations')==original_operations
                  and case()['version']==initial['version'] and not read('recovery_closure_receipts')
                  and not any(row['action']=='RECOVERY_NO_EFFECT_CLOSED' for row in audits())
                  and local('SELECT state FROM recovery_station_fence')==[('ACTIVE',)])
        def reinspect(version):
            return first.post(base+'/evidence',headers=headers(tech),json={'expected_version':version,
                'note':'Request successor after closure','statement':{'kind':'REINSPECT_OPERATION',
                'operation_id':op['id'],'context_hash':op['context_hash']}})
        with ThreadPoolExecutor(2) as pool:
            writer=pool.submit(submit_receipt)
            try:
                wait(lambda:(directory/'paused').exists(),'Uncommitted final closure audit',7)
                holder=int((directory/'paused').read_text())
                rival=pool.submit(reinspect,initial['version'])
                with db.sessions() as s:
                    def blocked():
                        s.execute(text('select pg_stat_clear_snapshot()'))
                        return s.scalar(text('select pid from pg_stat_activity where :holder=any(pg_blocking_pids(pid)) '
                            'and application_name=:app'),dict(holder=holder,app=directory.parent.name+'-8030'))
                    wait(blocked,'Successor waiting on final closure',3)
                    waiter=blocked()
                assert not read('recovery_operations')[0]['cancelled_at']
            finally:
                (directory/'release').touch()
            writer.result()
            rejected=rival.result()
        closed=case()
        retry=reinspect(closed['version'])
        check('Final closure precedes successor; old and current versions cannot reopen',
              rejected.status_code==409 and rejected.json()['code']=='VERSION_CONFLICT' and retry.status_code==409
              and len(read('recovery_operations'))==1 and closed['active_operation']['cancelled_at']
              and case()['version']==initial['version']+1 and not closed['old_pin_settled'])
        report['closure_before_successor']=dict(os_pids=[killed.pid,first_pid],pg_holder=holder,pg_waiter=waiter,
            before_version=initial['version'],after_version=closed['version'],old_request=[409,rejected.json()['code']],
            current_request=[409,retry.json()['code']])
    else:
        submit_receipt()
    wait(lambda:killed.poll() is not None,'Fault process exit')
    action='FOREIGN_OBJECT_RETURN_SETTLED' if successor else 'RECOVERY_NO_EFFECT_CLOSED'
    check('Actual process crash and DB audit boundary', killed.returncode==(91 if successor else 92)
          and sum(a['action']==action for a in audits())==(0 if successor else 1))
    if successor:
        assert all(not row['consumed_at'] for row in read('recovery_operations'))
    launch(['-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1',
            '--port','8031','--no-access-log'],'expiry-retry-api')
    wait(lambda:second.get('/health').status_code==200,'Restarted API ready')
    if successor:
        competitors = [(first,auth), (second,headers(tech))]
        with ThreadPoolExecutor(max_workers=2) as pool:
            raced = list(pool.map(lambda pair:pair[0].post(path,headers=pair[1],json=decision), competitors))
        check('Two processes compete on unconsumed chain after rollback',
              sorted(r.status_code for r in raced)==[200,409])
        winner = next(i for i,r in enumerate(raced) if r.status_code==200)
        result, auth = raced[winner], competitors[winner][1]
    else:
        result=first.post(path,headers=auth,json=decision)
        assert result.status_code==202,result.text
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda http:http.post(path,headers=auth,json=decision),(first,second)))
    check('Both processes replay one decision and one audit', all(r.json()==result.json() for r in replies)
          and sum(a['action']==action for a in audits())==1)
    if successor:
        rows=read('recovery_operations')
        assert len(rows)==2 and all(r['consumed_at'] for r in rows)
    else:
        assert result.json()['duplicate'] and case()['active_operation']['cancelled_at']
        env.pop('P8_TEST_HOLD_CLOSURE')
        restart_station()
        wait(lambda:local('SELECT state FROM recovery_station_fence')==[('CLOSED',)],'Durable closure acknowledgment',25)
        assert local("SELECT count(*) FROM recovery_denied_effects WHERE kind='OPERATION'")==[(1,)]
    check('Exact service effect count',local('SELECT COALESCE(sum(effects),0) FROM service_operations')==[(int(successor),)])
