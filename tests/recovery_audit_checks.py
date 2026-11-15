"""Independent SQL-backed audit assertions on Phase8A workflows, not a mock audit.

Existing tests still drive the real service/transactions. Snapshot values are
checked against live rows when captured; action deltas detect late BEFORE reads.
No mutation, clock change or synchronization is introduced by this observer.
"""
import hashlib
import json
from pathlib import Path
from uuid import UUID
import pytest
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

INCREMENT = {'RECOVERY_ATTESTATION_RECORDED','RECOVERY_EVIDENCE_RECORDED',
 'RECOVERY_OPERATION_CREATED','RECOVERY_OPERATION_ATTACHED','RECOVERY_PRE_ACTION_CONFIRMED',
 'RECOVERY_POST_ACTION_CONFIRMED','RECOVERY_REINSPECTION_ATTESTED',
 'RECOVERY_AUTHORIZATION_INTENT_CREATED','RECOVERY_ACTION_ACTIVATED',
 'RECOVERY_REINSPECTION_REQUESTED','RECOVERY_NO_EFFECT_CLOSURE_REQUESTED',
 'RECOVERY_NO_EFFECT_CLOSED','FOREIGN_OBJECT_RETURN_SETTLED','MANUAL_RECOVERY_SETTLED',
 'RECOVERY_RESUMED_COMPLETED'}
UNCHANGED = {'RECOVERY_OPERATION_SUPERSEDED','RECOVERY_AUTHORIZATION_ACKNOWLEDGED',
 'RECOVERY_INSPECTION_RECORDED','RECOVERY_POST_ACTION_RECEIPT_STORED','RECOVERY_REINSPECTION_RECORDED'}
CREATION = {'RECOVERY_CASE_CREATED'}
ADDED = {'RECOVERY_OPERATION_CREATED':'operations','RECOVERY_REINSPECTION_REQUESTED':'operations',
 'RECOVERY_ATTESTATION_RECORDED':'attestations','RECOVERY_PRE_ACTION_CONFIRMED':'attestations',
 'RECOVERY_POST_ACTION_CONFIRMED':'attestations','RECOVERY_REINSPECTION_ATTESTED':'attestations',
 'RECOVERY_INSPECTION_RECORDED':'attestations','RECOVERY_POST_ACTION_RECEIPT_STORED':'attestations',
 'RECOVERY_REINSPECTION_RECORDED':'attestations','RECOVERY_AUTHORIZATION_INTENT_CREATED':'authorizations',
 'RECOVERY_AUTHORIZATION_ACKNOWLEDGED':'authorization_acks','RECOVERY_ACTION_ACTIVATED':'activations',
 'RECOVERY_NO_EFFECT_CLOSURE_REQUESTED':'closure_intents','RECOVERY_NO_EFFECT_CLOSED':'closure_receipts'}
GROUPS = {'case':'recovery_cases','operations':'recovery_operations','attestations':'recovery_attestations',
 'authorizations':'recovery_action_authorizations','authorization_acks':'recovery_authorization_acks',
 'activations':'recovery_action_activations','closure_intents':'recovery_closure_intents',
 'closure_receipts':'recovery_closure_receipts','swap':'swap_transactions','batteries':'batteries',
 'holds':'resource_reservations','commands':'device_commands','payments':'payments'}

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

@pytest.fixture(autouse=True)
def verify_recovery_audit(request,monkeypatch):
 if not request.module.__name__.split('.')[-1].startswith('test_phase8a'):
  return
 from app.application import recovery as r
 capture,emit=r.audit_snapshot,r.audit
 captured={}
 def snapshot(session,db,case):
  data=capture(session,db,case)
  for group,name in GROUPS.items():
   supplied=data[group]
   values=[supplied] if group in ('case','swap') else list(supplied.values())
   if not values:continue
   table=db.table(name)
   raw={str(x['id']):jsonable_encoder(dict(x)) for x in session.execute(select(table)
       .where(table.c.id.in_([UUID(v['id']) for v in values]))).mappings()}
   assert len(raw)==len(values),(group,'missing actual rows')
   for row in values:
    assert row=={k:raw[row['id']][k] for k in row},(group,'snapshot differs from live row')
  assert {'version','state','old_pin_settled','new_pin_delivered','operation_id'}<=set(data['case'])
  captured[id(data)]=digest(data)
  return data
 def audit(session,db,actor,case,action,details,**kwargs):
  before=kwargs['before']
  if before is not None:assert captured[id(before)]==digest(before),'BEFORE mutated after capture'
  table=db.table('audit_events')
  previous=set(session.scalars(select(table.c.id)))
  result=emit(session,db,actor,case,action,details,**kwargs)
  events=session.execute(select(table).where(table.c.id.not_in(previous))).mappings().all()
  assert len(events)==1
  row=events[0];b=row['before_data']['recovery_snapshot'];a=row['after_data']['recovery_snapshot']
  assert b==before
  assert action in INCREMENT|UNCHANGED|CREATION,('Uncovered Recovery audit action',action)
  if action in CREATION:
   assert b is None and a['case']['state']=='OPEN' and not a['case']['old_pin_settled']
  else:
   assert a['case']['version']==b['case']['version']+(action in INCREMENT),(action,'wrong before/after version')
  assert row['correlation_id']==UUID(a['case']['swap_id']) and row['actor_id']==str(actor['id'])
  assert row['action']==action and row['aggregate_id']==case['id']
  if action in {'RECOVERY_OPERATION_CREATED','RECOVERY_REINSPECTION_REQUESTED'}:
   added=set(a['operations'])-set(b['operations']);assert len(added)==1
   assert next(iter(added))==a['case']['operation_id']
  if action in ADDED:assert len(set(a[ADDED[action]])-set(b[ADDED[action]]))==1,(action,'new child must not exist in BEFORE')
  if action=='RECOVERY_OPERATION_SUPERSEDED':
   identity=str(details['operation_id'])
   assert b['operations'][identity]['cancelled_at'] is None and a['operations'][identity]['cancelled_at']
  if action in {'MANUAL_RECOVERY_SETTLED','FOREIGN_OBJECT_RETURN_SETTLED'}:
   identity=str(details['operation_id'])
   assert b['operations'][identity]['consumed_at'] is None and a['operations'][identity]['consumed_at']
  if action=='RECOVERY_NO_EFFECT_CLOSED':
   identity=str(details['operation_id'])
   assert b['operations'][identity]['cancelled_at'] is None and a['operations'][identity]['cancelled_at']
  if action not in {'MANUAL_RECOVERY_SETTLED','RECOVERY_RESUMED_COMPLETED'}|CREATION:
   for key in ('swap','batteries','payments','holds','commands'):assert b[key]==a[key],(action,key)
  if action=='RECOVERY_RESUMED_COMPLETED':
   assert b['case']['state']!='RESOLVED' and a['case']['state']=='RESOLVED'
   assert a['case']['old_pin_settled'] is True and a['case']['new_pin_delivered']=='YES'
  config=request.config
  counts=getattr(config,'recovery_audit_counts',{})
  counts[action]=counts.get(action,0)+1;config.recovery_audit_counts=counts
  return result
 monkeypatch.setattr(r,'audit_snapshot',snapshot)
 monkeypatch.setattr(r,'audit',audit)

def pytest_sessionfinish(session,exitstatus):
 counts=getattr(session.config,'recovery_audit_counts',{})
 Path('docs/PHASE8A_NFR06_AUDIT_COVERAGE.json').write_text(json.dumps({
  'exit':int(exitstatus),'actions':counts,'not_exercised':sorted((INCREMENT|UNCHANGED|CREATION)-set(counts)),
  'checks':'Live SQL equality at capture; detached before; exact version/state/creation/consumption; protected facts; original audit persisted'},indent=2),encoding='utf8')
