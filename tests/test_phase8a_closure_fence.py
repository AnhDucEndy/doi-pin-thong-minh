"""Closure interlock uses a real SQLite ledger. HTTP task identity is a fixture."""
import json
from uuid import uuid4

import httpx
import pytest
from app.domain.recovery import canonical_hash
from simulators.device import recovery_fence as fence, recovery_reconciliation as er
from test_phase8a_staged_fence import command, inspection
from test_phase8a_service import simulator


def fixture(tmp_path):
    op=inspection()
    sim=simulator(tmp_path/'closure.sqlite3',op)
    original=command()
    sim.scenario='wrong-return'
    assert sim.handle(original)=='EXECUTED'
    op.update(return_compartment_id=original['compartment_id'],swap_id=original['swap_id'])
    proof=fence.inspect(sim,op)
    sim.snapshot()
    payload={'context_hash':op['context_hash'],'operation_id':op['operation_id'],'ledger_id':proof['ledger_id'],
             'fence_generation':proof['fence_generation'],'command_ids':[original['id']]}
    task={'task_kind':'CLOSE_NO_EFFECT','protocol_version':'0.2','effect_allowed':False,
          'station_id':op['station_id'],'context_hash':op['context_hash'],'operation_id':op['operation_id'],
          'closure_id':str(uuid4()),'payload':payload,'payload_hash':canonical_hash(payload)}
    sim.http.close()
    sim.http=httpx.Client(base_url='http://localhost',transport=httpx.MockTransport(
        lambda req:httpx.Response(200,json={'items':[task]})))
    return sim,task,original


def test_deny_and_positive_witness_survive_restart_before_commit_ack(tmp_path):
    sim,task,original=fixture(tmp_path)
    try:
        receipt=er.close_no_effect(sim,task)
        assert receipt['prior_effect_state']=='NEVER_PREPARED' and fence.active(sim.conn)
        assert er.close_no_effect(sim,task)==receipt
        assert not sim.conn.execute('SELECT 1 FROM service_operations').fetchone()
        transport=sim.http._transport
        sim.close()
        sim=simulator(tmp_path/'closure.sqlite3',task)
        sim.http.close();sim.http=httpx.Client(base_url='http://localhost',transport=transport)
        assert er.close_no_effect(sim,task)==receipt
        task.update(task_kind='CLOSURE_COMMITTED',receipt_hash='a'*64)
        with pytest.raises(ValueError,match='INVALID'):
            er.acknowledge_closure(sim,task)
        assert fence.active(sim.conn)
        from app.api.recovery_schemas import NoEffectClosure
        task['receipt_hash']=canonical_hash(NoEffectClosure.model_validate(receipt).model_dump(mode='json'))
        er.acknowledge_closure(sim,task)
        assert not fence.active(sim.conn)
        for kind,identity in [('OPERATION',task['operation_id']),('COMMAND',original['id'])]:
            with pytest.raises(RuntimeError,match='PERMANENTLY_DISABLED'):
                er.deny_guard(sim.conn,kind,identity)
        sim.handle(original)
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==1
    finally:
        sim.close()


@pytest.mark.parametrize('fault',['pending','uncertain','after-close','lost-witness','prepared'])
def test_uncertainty_preserves_fence(tmp_path,fault):
    sim,task,_=fixture(tmp_path)
    try:
        if fault=='pending':
            task['payload']['command_ids'].append(str(uuid4()))
            task['payload_hash']=canonical_hash(task['payload'])
        elif fault in ('uncertain','after-close'):
            if fault=='after-close':
                packet=er.close_no_effect(sim,task)
            sim.scenario='crash-after-ledger'
            with pytest.raises(RuntimeError,match='DURABLE_LEDGER'):
                sim.handle(command())
        else:
            # Negative fault only. Missing or interrupted history cannot be
            # reconstructed from absence of a terminal effect receipt.
            if fault=='lost-witness':
                sim.conn.execute('DELETE FROM recovery_effect_witness')
            else:
                sim.conn.execute("UPDATE recovery_effect_witness SET state='PREPARED'")
            sim.conn.commit()
        if fault=='after-close':
            from app.api.recovery_schemas import NoEffectClosure
            task.update(task_kind='CLOSURE_COMMITTED',receipt_hash=canonical_hash(
                NoEffectClosure.model_validate(packet).model_dump(mode='json')))
            with pytest.raises(RuntimeError,match='FENCE_CONFLICT'):
                er.acknowledge_closure(sim,task)
        else:
            with pytest.raises(RuntimeError,match='RECONCILIATION_REQUIRED|NO_EFFECT_UNPROVEN'):
                er.close_no_effect(sim,task)
            assert not sim.conn.execute('SELECT 1 FROM recovery_denied_effects').fetchone()
        assert fence.active(sim.conn)
        assert sim.conn.execute('SELECT sum(effects) FROM commands').fetchone()[0]==1
    finally:
        sim.close()
