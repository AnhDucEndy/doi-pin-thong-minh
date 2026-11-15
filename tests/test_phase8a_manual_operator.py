"""Operator tooling checks use real SQLite model and fixture HTTP, not Browser."""
import pytest
from tools.phase8a_manual_operator import dispatch
from test_phase8a_staged_fence import inspection
from test_phase8a_service import simulator


@pytest.mark.parametrize('action',['ACK','HANDOVER','REINSPECT','CLOSE','ACK_CLOSURE'])
def test_operator_rejects_unavailable_task_without_effect(tmp_path,action):
    task=inspection()
    sim=simulator(tmp_path/'operator.sqlite3',task)
    try:
        before=sim.slots()
        with pytest.raises(ValueError,match='No matching authorized task'):
            dispatch(sim,action,task['operation_id'])
        assert sim.slots()==before
        assert not sim.conn.execute('SELECT 1 FROM service_operations').fetchone()
    finally:
        sim.close()


def test_operator_inspection_replay_keeps_original_receipt_and_no_effect(tmp_path):
    task=inspection()
    sim=simulator(tmp_path/'operator.sqlite3',task)
    try:
        sim.snapshot()
        before=sim.slots()
        dispatch(sim,'INSPECT',task['operation_id'])
        packet=sim.conn.execute('SELECT packet FROM recovery_inspection_outbox').fetchone()[0]
        dispatch(sim,'INSPECT',task['operation_id'])
        assert sim.conn.execute('SELECT packet FROM recovery_inspection_outbox').fetchone()[0]==packet
        assert sim.slots()==before
        assert not sim.conn.execute('SELECT 1 FROM service_operations').fetchone()
    finally:
        sim.close()
