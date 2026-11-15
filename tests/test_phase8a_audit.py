"""Audit payloads are business evidence; preserve actual values, not just NULL checks."""
import json
from uuid import UUID,uuid4
from unittest.mock import patch
import pytest
from sqlalchemy import select
from test_phase8a_inspection_transport import setup_inspection,facts
from test_phase8a_ia01_fix import request
from simulators.device.recovery_fence import transport_inspection,flush

def test_audit_after_write_failure_rolls_back_and_retry_is_single(client,environment,auth,tmp_path):
 from app.application import recovery as r
 swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
 try:
  transport_inspection(sim,task);flush(sim)
  url=f"/v1/swaps/{swap['id']}/recovery";before=client.get(url,headers=tech).json()
  protected=facts(client,swap);db=client.app.state.db;table=db.table('audit_events')
  with db.sessions() as s:old_ids=set(s.scalars(select(table.c.id)))
  original=r.audit
  def fail(*args,**kwargs):
   original(*args,**kwargs)
   raise RuntimeError('NFR06_AFTER_AUDIT_WRITE')
  key=str(uuid4());body=request(before,task)
  with patch.object(r,'audit',fail),pytest.raises(RuntimeError,match='NFR06_AFTER_AUDIT_WRITE'):
   client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
  assert client.get(url,headers=tech).json()==before and facts(client,swap)==protected
  with db.sessions() as s:assert set(s.scalars(select(table.c.id)))==old_ids
  accepted=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body)
  assert accepted.status_code==200,accepted.text
  assert client.post(url+'/evidence',headers={**tech,'Idempotency-Key':key},json=body).json()==accepted.json()
  with db.sessions() as s:
   rows=s.execute(select(table).where(table.c.id.not_in(old_ids))).mappings().all()
  assert len(rows)==1
  row=rows[0];b=row['before_data']['recovery_snapshot'];a=row['after_data']['recovery_snapshot']
  assert b['case']['version']==before['version'] and a['case']['version']==accepted.json()['version']
  assert not any(p['source_kind']=='TECHNICIAN' for p in b['attestations'].values())
  assert len([p for p in a['attestations'].values() if p['source_kind']=='TECHNICIAN'])==1
 finally:sim.close()

def test_creation_has_no_fabricated_before_child_and_audit_has_no_raw_notes(client,environment,auth,tmp_path):
 from app.application import recovery as r
 from app.application.recovery_audit import safe
 swap,sim,task,tech=setup_inspection(client,environment,auth,tmp_path)
 try:
  db=client.app.state.db;t=db.table('audit_events')
  with db.sessions() as s:
   row=s.execute(select(t).where(t.c.action=='RECOVERY_OPERATION_CREATED')).mappings().one()
  b=row['before_data']['recovery_snapshot'];a=row['after_data']['recovery_snapshot'];identity=task['operation_id']
  assert identity not in b['operations'] and a['operations'][identity]['consumed_at'] is None
  assert a['case']['operation_id']==identity and b['case']['operation_id'] is None
  secret='SYNTHETIC_NFR06_PRIVATE_NOTE'
  payload={'operation_id':identity,'nested':{'password':secret,'access_token':secret,'payload':secret},'note':secret}
  assert secret not in json.dumps(safe(payload)) and safe(payload)['operation_id']==identity
  for snapshot in (b,a):
   assert 'resolution_note' not in snapshot['case']
   assert all('payload' not in p for p in snapshot['attestations'].values())
 finally:sim.close()

def test_all_recovery_actions_use_explicit_before_snapshot():
 import ast
 from pathlib import Path
 for p in Path('services/backend/app/application').glob('recovery*.py'):
  tree=ast.parse(p.read_text(encoding='utf8'))
  for node in ast.walk(tree):
   if not isinstance(node,ast.Call):continue
   name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
   if name=='audit':assert 'before' in [k.arg for k in node.keywords],(p,node.lineno)

def test_legacy_receipt_attach_supersede_and_case_creation_audits(client,environment,auth):
 from test_phase8a_api import start_case,begin
 from app.application import recovery as r
 swap,tech,case=start_case(client,environment,auth)
 db=client.app.state.db;url=f"/v1/swaps/{swap['id']}/recovery"
 t=db.table('device_events')
 with db.sessions() as s:
  dev=r.assets.available_device(s,db,UUID(swap['station_id']))
  event=s.execute(select(t).where(t.c.device_id==dev['id'],t.c.kind=='SNAPSHOT',
      t.c.accepted.is_(True),t.c.processed_at.is_not(None)).order_by(t.c.observed_at.desc())).mappings().first()
 assert event
 secret='SYNTHETIC_NFR06_PRIVATE_NOTE'
 result=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json={
     'expected_version':case['version'],'evidence_event_id':str(event['id']),'note':secret})
 assert result.status_code==200,result.text
 case=result.json()
 initial=begin(client,swap,tech,case);assert initial.status_code==200,initial.text
 op=initial.json()['active_operation']
 body={'expected_version':initial.json()['version'],'note':'attach existing operation',
       'statement':{'kind':'ATTACH_OPERATION','operation_id':op['id']}}
 attached=client.post(url+'/evidence',headers={**tech,'Idempotency-Key':str(uuid4())},json=body)
 assert attached.status_code==200,attached.text
 reject=client.post(url+'/confirmations',headers={**auth('customer'),'Idempotency-Key':str(uuid4())},
     json={'operation_id':op['id'],'context_hash':op['context_hash'],'confirm':False})
 assert reject.status_code==201,reject.text
 before=client.get(url,headers=tech).json()
 replacement=begin(client,swap,tech,before);assert replacement.status_code==200,replacement.text
 audits=db.table('audit_events')
 with db.sessions() as s:rows=s.execute(select(audits).where(audits.c.aggregate_type=='recovery')).mappings().all()
 creation=[x for x in rows if x['action']=='RECOVERY_CASE_CREATED']
 assert len(creation)==1 and creation[0]['before_data']['recovery_snapshot'] is None
 assert secret not in json.dumps([dict(x['after_data']) for x in rows])
 superseded=next(x for x in rows if x['action']=='RECOVERY_OPERATION_SUPERSEDED')
 assert superseded['before_data']['recovery_snapshot']['operations'][op['id']]['cancelled_at'] is None
 assert superseded['after_data']['recovery_snapshot']['operations'][op['id']]['cancelled_at']
