"""Real operator IPC checks, called only from an isolated E fixture."""
from datetime import datetime, timezone, timedelta
import json
import os
import sqlite3
from uuid import uuid4

from smoke_phase8a import wait


def verify(directory,fixture,swap,env,launch,first,second,tech,customer,case,read,report):
    mode=os.getenv('P8_OPERATOR_MODE','E')
    base=f"/v1/swaps/{swap['id']}/recovery"
    http=[]
    def post(path,body,actor=tech,key=None):
        result=first.post(path,headers={**actor,'Idempotency-Key':key or str(uuid4())},json=body)
        http.append({'path':path,'status':result.status_code,'code':result.json().get('code')})
        return result
    def record(statement):
        return post(base+'/evidence',{'expected_version':case()['version'],'note':'Operator verification','statement':statement})
    def local(sql):
        with sqlite3.connect((directory/'ledgers/S01.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
            return c.execute(sql).fetchall()
    def facts():
        charge=read('payments')[0]
        transaction=read('swap_transactions')[0]
        pins=[p for p in read('batteries') if p['id'] in (transaction['old_battery_id'],transaction['new_battery_id'])]
        return {'payment':charge['state'],'holds':sum(h['released_at'] is None for h in read('resource_reservations')),
                'custody':[{k:p[k] for k in ('id','location_kind','holder_user_id','compartment_id')} for p in pins]}
    def start():
        module='tools.phase8a_operator_fault' if env.get('P8_OPERATOR_FAULT') else 'tools.phase8a_manual_operator'
        return launch(['-m',module,'--device',str(directory)],'operator-'+uuid4().hex[:6])
    def stop(child):
        child.terminate();child.wait(15)
    operations=[]
    report['operator']={'mode':mode,'requests':operations,'http':http}
    def action(kind,op,expected=True):
        path=directory/('request-'+uuid4().hex+'.json')
        path.write_text(json.dumps({'action':kind,'operation_id':op['id']}))
        result=path.with_suffix('.result.json')
        if mode=='U' and kind=='HANDOVER':
            wait(lambda:child.poll() is not None,'Actual operator crash after PREPARED',15)
            assert child.returncode==86
            operations.append({'action':kind,'crash_exit':86})
            return result
        wait(result.exists,'Operator '+kind,15)
        packet=json.loads(result.read_text())
        operations.append({'requested_action':kind,**packet})
        assert packet['completed']==expected,packet
        return packet
    if mode=='U':env['P8_OPERATOR_FAULT']='1'
    child=start()
    try:
        wait(lambda:first.get('/health').status_code==200,'API ready')
        # Give the worker the actual reboot snapshot before opening inspection.
        from sqlalchemy import select
        station=read('swap_transactions')[0]['station_id']
        def device():
            return next(d for d in read('devices') if d['station_id']==station)
        old_boot=device()['boot_id']
        wait(lambda:any(d['station_id']==read('swap_transactions')[0]['station_id'] and d['boot_id']!=old_boot for d in read('devices')),
             'Operator reboot projection',15)
        wait(lambda:any(e['kind']=='SNAPSHOT' and e['accepted'] and e['processed_at'] for e in read('device_events')),'Snapshot accepted')
        before=facts()
        response=record({'kind':'BEGIN_OPERATION','purpose':'RETURN_FOREIGN_OBJECT'})
        assert response.status_code==200,response.text
        op=response.json()['active_operation']
        action('INSPECT',op)
        wait(lambda:case()['active_operation']['attestations'],'PRE accepted')
        receipt=case()['active_operation']['attestations'][0]
        assert receipt['stage']=='PRE_ACTION_INSPECTION'
        ref={'operation_id':op['id'],'context_hash':op['context_hash'],'stage':receipt['stage'],
             'receipt_id':receipt['id'],'receipt_hash':receipt['payload_hash']}
        wrong=post(base+'/confirmations',{**ref,'stage':'POST_ACTION_RECEIPT','confirm':True},customer)
        assert wrong.status_code in (409,422)
        if mode=='T':
            prior=case(); boot=device()['boot_id']
            stop(child);child=start()
            wait(lambda:device()['boot_id']!=boot,'IA01 new boot committed',15)
            wait(lambda:first.get('/v1/swaps/'+swap['id'],headers=customer).json()['recovery_confirmation']['confirmation_status']=='UNAVAILABLE',
                 'IA01 owner projection unavailable',15)
            statement={**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}
            body={'expected_version':prior['version'],'note':'IA01 OS-process old boot','statement':statement}
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda http:http.post(base+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json=body),[first,second]))
            assert all(r.status_code==409 and r.json()['code']=='RECONCILIATION_REQUIRED' for r in results)
            assert post(base+'/confirmations',{**ref,'confirm':True},customer).status_code==409
            assert case()==prior and facts()==before
            assert local('SELECT count(*) FROM service_operations')[0][0]==0
            assert not any(a['action']=='RECOVERY_PRE_ACTION_CONFIRMED' for a in read('audit_events'))
            report['operator']={'mode':'T','old_boot':str(boot),'new_boot':str(device()['boot_id']),
                'statuses':[r.status_code for r in results],'case_unchanged':True,'facts':before,
                'effects':0,'confirmation_audits':0,'requests':operations,'http':http}
            return
        assert record({**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':receipt['payload']['actual_serial'],'observation':'CONFIRM'}).status_code==200
        assert post(base+'/confirmations',{**ref,'confirm':True},customer).status_code==201
        assert record({'kind':'AUTHORIZE_ACTION','operation_id':op['id'],'context_hash':op['context_hash']}).status_code==200
        action('ACK',op)
        action('ACK',op)
        permit=case()['active_operation']['authorization']
        assert permit['transport_acknowledged']
        if mode!='J':
            body={'expected_version':case()['version'],'note':'Activate verified task','statement':{
                'kind':'AUTHORIZE_ACTION','phase':'ACTIVATE','operation_id':op['id'],'context_hash':op['context_hash'],
                'authorization_id':permit['id'],'acknowledgment_id':permit['acknowledgment_id']}}
            assert post(base+'/evidence',body,customer).status_code==403
            assert post(base+'/evidence',body).status_code==200
            if mode=='U':
                pending=action('HANDOVER',op)
                assert local('SELECT state FROM recovery_action_ledger')==[('PREPARED',)]
                env.pop('P8_OPERATOR_FAULT')
                child=start()
                wait(pending.exists,'Same queued request after restart',15)
                assert local('SELECT sum(effects) FROM service_operations')==[(0,)]
                wait(lambda:datetime.now(timezone.utc)>=datetime.fromisoformat(op['expires_at']),'Real expiry after UNKNOWN',130)
                refused=record({'kind':'CLOSE_NO_EFFECT','operation_id':op['id'],'context_hash':op['context_hash']})
                assert refused.status_code in (200,409)
                if refused.status_code==200:
                    action('CLOSE',op,expected=False)
                assert local('SELECT state FROM recovery_station_fence')==[('ACTIVE',)]
                assert not read('recovery_closure_receipts')
                assert not case()['active_operation']['cancelled_at'] and not case()['active_operation']['consumed_at']
                assert facts()==before
                assert not any(a['action']=='RECOVERY_NO_EFFECT_CLOSED' for a in read('audit_events'))
                report['operator'].update(facts=before,effects=0,unknown_after_crash=True,case_version=case()['version'])
                return
            action('HANDOVER',op)
            wait(lambda:any(p['stage']=='POST_ACTION_RECEIPT' for p in case()['active_operation']['attestations']),'Accepted POST receipt',12)
            postproof=next(p for p in case()['active_operation']['attestations'] if p['stage']=='POST_ACTION_RECEIPT')
            ref.update(stage=postproof['stage'],receipt_id=postproof['id'],receipt_hash=postproof['payload_hash'])
            assert post(base+'/confirmations',{**ref,'receipt_hash':'0'*64,'confirm':True},customer).status_code in (409,422)
            if mode=='E':
                # Accepted POST removes ACTION from the current task-list.
                # Replaying the operator request must be denied without effect.
                action('HANDOVER',op,expected=False)
            elif mode=='S':
                policy=read('swap_transactions')[0]['policy_snapshot']
                deadline=datetime.fromisoformat(postproof['observed_at'])+timedelta(seconds=policy['telemetry_stale_seconds'])
                wait(lambda:datetime.now(timezone.utc)>deadline,'Actual POST freshness expiry',20)
                version=case()['version']
                refusal=record({**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':'SIMULATED-WRONG-BATTERY','observation':'CONFIRM'})
                assert refusal.status_code==422 and refusal.json()['code']=='EVENT_STALE'
                assert case()['version']==version and not case()['active_operation']['consumed_at']
                assert facts()==before
                assert local('SELECT sum(effects) FROM service_operations')==[(1,)]
                assert not any(a['action']=='FOREIGN_OBJECT_RETURN_SETTLED' for a in read('audit_events'))
                report['operator'].update(stale_rejected=True,case_version=version,facts=before,effects=1)
                return
            else:
                stop(child);child=start()
                # Current boot must differ from immutable original effect proof.
                wait(lambda:str(device()['boot_id'])!=postproof['source_boot'],'Fresh reboot',15)
                assert record({**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':'SIMULATED-WRONG-BATTERY','observation':'CONFIRM'}).status_code in (409,422)
        if mode in ('J','K'):
            wait(lambda:datetime.now(timezone.utc)>=datetime.fromisoformat(op['expires_at']),'Actual operation expiry',130)
            assert post(base+'/confirmations',{**ref,'confirm':True},customer).status_code in (409,422)
            if mode=='J':
                assert record({'kind':'CLOSE_NO_EFFECT','operation_id':op['id'],'context_hash':op['context_hash']}).status_code==200
                action('CLOSE',op)
                action('ACK_CLOSURE',op)
                action('ACK_CLOSURE',op)
                assert local('SELECT state FROM recovery_station_fence')==[('CLOSED',)]
            else:
                response=record({'kind':'REINSPECT_OPERATION','operation_id':op['id'],'context_hash':op['context_hash']})
                assert response.status_code==200,response.text
                op=response.json()['active_operation']
                action('REINSPECT',op)
                proof=case()['active_operation']['attestations'][0]
                assert proof['stage']=='RECONCILIATION_INSPECTION'
                ref={'operation_id':op['id'],'context_hash':op['context_hash'],'stage':proof['stage'],
                     'receipt_id':proof['id'],'receipt_hash':proof['payload_hash']}
        if mode!='J':
            assert record({**ref,'kind':'TECHNICIAN_ATTEST','actual_serial':'SIMULATED-WRONG-BATTERY','observation':'CONFIRM'}).status_code==200
            assert post(base+'/confirmations',{**ref,'confirm':True},customer).status_code==201
            body={'expected_version':case()['version'],'operation_id':op['id'],'resolution_note':'Operator proof'}
            key=str(uuid4())
            result=post(base+'/settle',body,key=key)
            assert result.status_code==200,result.text
            assert post(base+'/settle',body,key=key).json()==result.json()
        assert facts()==before
        assert before['holds']==3 and before['payment']=='SUCCEEDED'
        assert not case()['old_pin_settled']
        effects=local('SELECT coalesce(sum(effects),0) FROM service_operations')[0][0]
        assert effects==(0 if mode=='J' else 1)
        audit_action='RECOVERY_NO_EFFECT_CLOSED' if mode=='J' else 'FOREIGN_OBJECT_RETURN_SETTLED'
        assert sum(a['action']==audit_action for a in read('audit_events'))==1
        report['operator']={'mode':mode,'requests':operations,'http':http,'case_version':case()['version'],
                            'effects':effects,'success_audit':audit_action,'success_audits':1,'facts':before}
    finally:
        if child.poll() is None:stop(child)
