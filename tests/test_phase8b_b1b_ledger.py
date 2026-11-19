"""Native SQLite/model regressions, not authenticated PostgreSQL/API E2E."""
from datetime import timedelta
import json
import sqlite3
from uuid import uuid4

import httpx
import pytest

from app.application.identity import utcnow
from app.domain.recovery import canonical_hash
from app.seed import demo_id
from simulators.device.main import Simulator
from simulators.device import no_delivery as nd
from simulators.device.recovery_fence import active
from test_phase8a_staged_fence import command


def task():
    current = utcnow()
    ctx = dict(protocol_version='0.3', purpose='VERIFY_NO_DELIVERY',operation_id=str(uuid4()),
        case_id=str(uuid4()),swap_id=str(uuid4()),station_id=str(demo_id('S01')),
        device_id=str(demo_id('device:S01')),customer_id=str(demo_id('customer')),
        created_by=str(demo_id('technician')),new_battery_id=str(demo_id('S01:battery:2')),
        expected_serial='S01-B002',supply_compartment_id=str(demo_id('S01:slot:2')),
        return_compartment_id=str(demo_id('S01:slot:1')),base_case_version=1,base_swap_version=1,
        created_at=current.isoformat(),expires_at=(current+timedelta(seconds=120)).isoformat())
    ctx['context_hash']=canonical_hash(ctx)
    return dict(protocol_version='0.3',task_kind='VERIFY_NO_DELIVERY_INSPECT',context=ctx,effect_allowed=False)


def simulator(path, tasks):
    def transport(request):
        if request.method=='POST' and request.url.path=='/v1/device/events':
            body=json.loads(request.content)
            return httpx.Response(202,json={'event_id':body['event_id'],'processing_state':'PROCESSED'})
        assert request.method=='GET' and request.url.path=='/v1/device/recovery-tasks'
        return httpx.Response(200,json={'items':tasks})
    return Simulator('S01','local-test-device-key-not-a-credential',ledger=path,
                     transport=httpx.MockTransport(transport),scenario='physical')


def test_new_genesis_records_actual_model_and_boot_chain(tmp_path):
    path=tmp_path/'new.sqlite3'
    sim=simulator(path,[])
    before=sim.slots();boot=sim.boot
    genesis=dict(sim.conn.execute('SELECT * FROM nd_genesis').fetchone())
    assert genesis['complete']==1
    assert json.loads(genesis['body'])['slots']==before
    assert nd.verify_history(sim.conn)
    sim.snapshot()
    assert nd.verify_history(sim.conn)
    sim.close()
    sim=simulator(path,[])
    try:
        assert sim.boot!=boot and nd.verify_history(sim.conn)
        assert dict(sim.conn.execute('SELECT * FROM nd_genesis').fetchone())==genesis
        assert sim.slots()==before
        assert sim.conn.execute("SELECT count(*) FROM nd_journal WHERE table_name='BOOT'").fetchone()[0]==2
    finally:sim.close()


def test_existing_uninstrumented_ledger_never_gains_complete_genesis(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    # Existing pre-journal database, even empty, is not a new model witness.
    with sqlite3.connect(path) as c:c.execute('PRAGMA user_version=1')
    sim=simulator(path,[])
    try:
        with pytest.raises(RuntimeError,match='HISTORY_INCOMPLETE'):nd.verify_history(sim.conn)
        assert sim.conn.execute('SELECT complete FROM nd_genesis').fetchone()[0]==0
    finally:sim.close()


def test_journal_and_command_effect_commit_atomically(tmp_path):
    sim=simulator(tmp_path/'atomic.sqlite3',[])
    try:
        cached=command()
        assert sim.handle(cached)=='EXECUTED'
        assert nd.verify_history(sim.conn)
        assert sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==1
        changes=[json.loads(r[0]) for r in sim.conn.execute("SELECT body FROM nd_journal WHERE table_name='slots'")]
        assert any(json.loads(r['row']['body'])['door_state']=='OPEN' for r in changes)
        assert sim.handle(cached)=='ACCEPTED'
        assert sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==1
    finally:sim.close()


def test_readonly_fence_blocks_cached_command_and_survives_restart(tmp_path):
    op=task();path=tmp_path/'fenced.sqlite3';sim=simulator(path,[op]);cached=command()
    nd.register_tasks(sim.conn,'COMMAND',[cached])
    before=sim.slots()
    initial=nd.install_fence(sim,op)
    assert sim.slots()==before
    assert initial['state']=='ACTIVE' and json.loads(initial['inspection'])['effect_count_delta']==0
    assert sim.conn.execute("SELECT 1 FROM nd_denials WHERE kind='COMMAND' AND identity=?",(cached['id'],)).fetchone()
    with pytest.raises(RuntimeError,match='STATION_FENCED'):sim.handle(cached)
    assert sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==0
    assert nd.verify_history(sim.conn)
    sim.close()
    sim=simulator(path,[op])
    try:
        assert sim.slots()==before and dict(active(sim.conn))==initial
        assert sim.handle(cached)=='UNKNOWN'
        assert sim.conn.execute('SELECT effects FROM commands').fetchone()[0]==0
        assert nd.verify_history(sim.conn)
    finally:sim.close()


@pytest.mark.parametrize('table',['nd_genesis','nd_journal','nd_fetched','nd_denials'])
def test_history_and_denial_rows_are_append_only(tmp_path,table):
    op=task();sim=simulator(tmp_path/(table+'.sqlite3'),[op])
    try:
        nd.install_fence(sim,op)
        with pytest.raises(sqlite3.IntegrityError,match='ND_APPEND_ONLY'):
            sim.conn.execute('DELETE FROM '+table)
        sim.conn.rollback()
        assert nd.verify_history(sim.conn)
    finally:sim.close()


def test_actual_model_write_cannot_cross_no_delivery_fence(tmp_path):
    op=task();sim=simulator(tmp_path/'model.sqlite3',[op])
    try:
        before=sim.slots();nd.install_fence(sim,op)
        slot=dict(before[0]);slot['door_state']='OPEN'
        with pytest.raises(sqlite3.IntegrityError,match='ND_STATION_FENCED'):sim.save_slot(slot)
        sim.conn.rollback()
        assert sim.slots()==before and nd.verify_history(sim.conn)
    finally:sim.close()


def test_readonly_receipt_uses_actual_model_and_original_source_hash(tmp_path):
    from app.api.no_delivery_schemas import P8NDObservation
    from app.domain.device import validate_event
    op=task();sim=simulator(tmp_path/'receipt.sqlite3',[op])
    try:
        before=sim.slots()
        receipt=nd.inspect(sim,op)
        P8NDObservation.model_validate(receipt)
        assert receipt['actual_serial']=='S01-B002' and receipt['effect_count_delta']==0
        assert sim.slots()==before and not sim.conn.execute('SELECT 1 FROM commands').fetchone()
        source=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',(receipt['snapshot_event_id'],)).fetchone()[0])
        assert receipt['snapshot_hash']==validate_event(source)[1]
        assert receipt['delivery_history']['event_ids']==[source['event_id']]
        assert nd.inspect(sim,op)==receipt
        assert sim.conn.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError,match='APPEND_ONLY'):
            sim.conn.execute("UPDATE nd_receipts SET packet='{}'")
        sim.conn.rollback()
    finally:sim.close()


def test_wrong_expectation_cannot_create_a_positive_observation(tmp_path):
    op=task();op['context']['expected_serial']='EXPECTED-BUT-NOT-ACTUAL'
    op['context']['context_hash']=canonical_hash({k:v for k,v in op['context'].items() if k!='context_hash'})
    sim=simulator(tmp_path/'no-echo.sqlite3',[op])
    try:
        before=sim.slots()
        with pytest.raises(RuntimeError,match='ACTUAL_MODEL_UNPROVEN'):nd.inspect(sim,op)
        assert sim.slots()==before and not sim.conn.execute('SELECT 1 FROM nd_receipts').fetchone()
        assert active(sim.conn)['state']=='ACTIVE'  # A refusal never releases exclusivity.
    finally:sim.close()


def test_unknown_command_is_not_a_no_delivery_proof(tmp_path):
    op=task();sim=simulator(tmp_path/'unknown.sqlite3',[op]);cached=command()
    try:
        sim.scenario='crash-after-ledger'
        with pytest.raises(RuntimeError,match='SIMULATED_CRASH'):sim.handle(cached)
        before=sim.slots()
        with pytest.raises(RuntimeError,match='UNRESOLVED_COMMAND'):nd.inspect(sim,op)
        assert sim.slots()==before and not sim.conn.execute('SELECT 1 FROM nd_receipts').fetchone()
        assert tuple(sim.conn.execute('SELECT status,effects FROM commands').fetchone())==('UNKNOWN',0)
        assert active(sim.conn)['state']=='ACTIVE'
    finally:sim.close()


def test_receipt_replay_after_boot_never_renews_current_proof(tmp_path):
    op=task();path=tmp_path/'receipt-reboot.sqlite3';sim=simulator(path,[op])
    first=nd.inspect(sim,op);sim.close()
    sim=simulator(path,[op])
    try:
        assert sim.boot!=first['boot_id']
        assert nd.inspect(sim,op)==first
        assert sim.conn.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==1
        assert nd.verify_history(sim.conn)
    finally:sim.close()


def test_inspection_sequence_is_after_current_device_source_high_watermark(tmp_path):
    op=task();sim=simulator(tmp_path/'sequence.sqlite3',[op])
    try:
        for _ in range(5):sim.emit('HEARTBEAT',{'health':'OK'})
        packet=nd.inspect(sim,op)
        source=json.loads(sim.conn.execute('SELECT body FROM events WHERE id=?',
                                          (packet['snapshot_event_id'],)).fetchone()[0])
        assert packet['seq']>source['seq']
        next_source=sim.snapshot()
        assert next_source['seq']>packet['seq']
    finally:sim.close()


@pytest.mark.parametrize('status',[202,409])
def test_receipt_waits_for_trailing_source_and_never_rehabilitates_refusal(tmp_path,status):
    op=task();sim=simulator(tmp_path/('transport'+str(status)+'.sqlite3'),[op])
    try:
        original=nd.inspect(sim,op)
        state={'processed':False,'submissions':[]}
        def transport(request):
            body=json.loads(request.content)
            if request.url.path=='/v1/device/events':
                return httpx.Response(202,json={'event_id':body['event_id'],
                    'processing_state':'PROCESSED' if state['processed'] else 'QUEUED'})
            assert request.url.path=='/v1/device/recovery-observations'
            state['submissions'].append(body)
            return httpx.Response(status,json={'accepted':True,'duplicate':False,'id':str(uuid4())} if status==202
                                  else {'code':'QUIESCENCE_REQUIRED'})
        sim.http.close();sim.http=httpx.Client(base_url='http://localhost',transport=httpx.MockTransport(transport))
        sim.snapshot();sim.flush()
        nd.flush(sim)
        assert state['submissions']==[]
        assert sim.conn.execute('SELECT sent FROM nd_receipts').fetchone()[0]==0
        state['processed']=True;nd.flush(sim);nd.flush(sim)
        assert state['submissions']==[original]
        assert sim.conn.execute('SELECT sent FROM nd_receipts').fetchone()[0]==(1 if status==202 else 2)
        assert sim.conn.execute('SELECT status FROM nd_receipt_dispositions').fetchone()[0]==status
        assert json.loads(sim.conn.execute('SELECT packet FROM nd_receipts').fetchone()[0])==original
    finally:sim.close()


@pytest.mark.parametrize('restart',[False,True])
def test_inspection_refreshes_durable_queued_source_disposition_without_recapture(tmp_path,restart):
    """An old 202 receipt can stay QUEUED locally after worker commit/crash."""
    op=task();path=tmp_path/'queued-history.sqlite3';sim=simulator(path,[op])
    try:
        source=sim.snapshot();old_http=sim.http
        def queued(request):
            packet=json.loads(request.content)
            return httpx.Response(202,json={'event_id':packet['event_id'],'processing_state':'QUEUED'})
        sim.http=httpx.Client(base_url='http://localhost',transport=httpx.MockTransport(queued))
        sim.flush();sim.http.close();sim.http=old_http
        original=sim.conn.execute('SELECT body FROM events WHERE id=?',(source['event_id'],)).fetchone()[0]
        if restart:
            sim.close();sim=simulator(path,[op])
        before=sim.slots()
        packet=nd.inspect(sim,op)
        assert packet['boot_id']==sim.boot and packet['effect_count_delta']==0
        assert sim.slots()==before
        retained=sim.conn.execute('SELECT body,receipt FROM events WHERE id=?',(source['event_id'],)).fetchone()
        assert retained['body']==original and json.loads(retained['receipt'])['processing_state']=='PROCESSED'
        assert packet['delivery_history']['event_ids'][0]==source['event_id']
        assert nd.inspect(sim,op)==packet and sim.conn.execute('SELECT count(*) FROM nd_receipts').fetchone()[0]==1
    finally:sim.close()


def test_actual_service_crash_is_not_no_effect_after_reboot(tmp_path):
    from test_phase8a_service import simulator as legacy_simulator,task as service_task
    from simulators.device.service import perform
    operation=service_task();path=tmp_path/'actual-service-crash.sqlite3'
    sim=legacy_simulator(path,operation)
    try:
        with pytest.raises(RuntimeError,match='CRASH_AFTER_PREPARED'):
            perform(sim,operation,technician_token='synthetic-service-test',crash_after_prepared=True)
    finally:sim.close()
    op=task();sim=simulator(path,[op])
    try:
        before=sim.slots()
        with pytest.raises(RuntimeError,match='ND_UNRESOLVED_SERVICE'):nd.inspect(sim,op)
        assert sim.slots()==before and active(sim.conn)['state']=='ACTIVE'
        stored=sim.conn.execute('SELECT state,effects,observation FROM service_operations').fetchone()
        assert tuple(stored)==('UNKNOWN',0,None)
        assert not sim.conn.execute('SELECT 1 FROM nd_receipts').fetchone()
    finally:sim.close()


def test_delivered_then_returned_serial_is_not_certified_from_present_slot(tmp_path):
    from test_phase8a_service import simulator as legacy_simulator,task as service_task
    from simulators.device.service import perform
    operation=service_task();path=tmp_path/'delivered-and-returned.sqlite3'
    sim=legacy_simulator(path,operation)
    try:
        assert perform(sim,operation,technician_token='synthetic-service-test')=='OBSERVED'
        assert sim.conn.execute('SELECT effects FROM service_operations').fetchone()[0]==1
        # Real model command returns that same delivered object into its slot.
        # No SQL edits the slot, custody, timestamp or prior service receipt.
        returned=command();returned['compartment_id']=str(demo_id('S01:slot:2'))
        returned['payload']['expected_serial']='S01-B002'
        returned['payload']['expected_battery_id']=str(demo_id('S01:battery:2'))
        sim.scenario='physical'
        assert sim.handle(returned)=='EXECUTED'
    finally:sim.close()
    op=task();sim=simulator(path,[op])
    try:
        before=sim.slots()
        assert next(s for s in before if s['compartment_id']==op['context']['supply_compartment_id'])['present']
        with pytest.raises(RuntimeError,match='ND_DELIVERY_HISTORY_CONFLICT'):nd.inspect(sim,op)
        assert sim.slots()==before and active(sim.conn)['state']=='ACTIVE'
        assert not sim.conn.execute('SELECT 1 FROM nd_receipts').fetchone()
    finally:sim.close()
