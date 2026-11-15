"""Read-only NFR06 verification for fresh real-process fixture reports.

Never prints credentials or raw payloads. Refuses demo/non-test schemas and
existing output files. This is evidence tooling, not a production endpoint.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/backend'))
from app.config import Settings
from fastapi.encoders import jsonable_encoder
from sqlalchemy import MetaData,create_engine,select,text

INCREMENT={'RECOVERY_ATTESTATION_RECORDED','RECOVERY_EVIDENCE_RECORDED','RECOVERY_OPERATION_CREATED',
 'RECOVERY_OPERATION_ATTACHED','RECOVERY_PRE_ACTION_CONFIRMED','RECOVERY_POST_ACTION_CONFIRMED',
 'RECOVERY_REINSPECTION_ATTESTED','RECOVERY_AUTHORIZATION_INTENT_CREATED','RECOVERY_ACTION_ACTIVATED',
 'RECOVERY_REINSPECTION_REQUESTED','RECOVERY_NO_EFFECT_CLOSURE_REQUESTED','RECOVERY_NO_EFFECT_CLOSED',
 'FOREIGN_OBJECT_RETURN_SETTLED','MANUAL_RECOVERY_SETTLED','RECOVERY_RESUMED_COMPLETED'}
UNCHANGED={'RECOVERY_OPERATION_SUPERSEDED','RECOVERY_AUTHORIZATION_ACKNOWLEDGED','RECOVERY_INSPECTION_RECORDED',
 'RECOVERY_POST_ACTION_RECEIPT_STORED','RECOVERY_REINSPECTION_RECORDED'}
FORBIDDEN={'password','password_hash','token','token_hash','access_token','refresh_token','qr_token',
 'secret','device_key','x_device_key','authorization','headers','payload','raw_payload','resolution_note'}

def safe_keys(value):
 if isinstance(value,dict):
  assert not (set(k.lower().replace('-','_') for k in value)&FORBIDDEN),'Sensitive audit field'
  for v in value.values():safe_keys(v)
 elif isinstance(value,list):
  for v in value:safe_keys(v)

def verify(connection,schema):
 connection.execute(text('SET TRANSACTION READ ONLY'))
 connection.execute(text('SET LOCAL statement_timeout=10000'))
 meta=MetaData()
 meta.reflect(bind=connection,schema=schema,only=['audit_events','recovery_cases','recovery_operations',
     'payments','resource_reservations','batteries','swap_transactions'])
 def table(name):return meta.tables[f'{schema}.{name}']
 events=connection.execute(select(table('audit_events')).where(table('audit_events').c.aggregate_type=='recovery')).mappings().all()
 assert events,'No Recovery audit evidence'
 counts={};latest={};transitions=[]
 for row in events:
  action=row['action'];counts[action]=counts.get(action,0)+1
  assert action in INCREMENT|UNCHANGED|{'RECOVERY_CASE_CREATED'},'Unrecognized action'
  assert row['before_data'] is not None and row['after_data'] is not None
  safe_keys(row['before_data']);safe_keys(row['after_data'])
  b=row['before_data']['recovery_snapshot'];a=row['after_data']['recovery_snapshot']
  assert a['snapshot_version']==1 and a['case']['id']==str(row['aggregate_id'])
  assert a['case']['swap_id']==str(row['correlation_id']) and row['actor_id'] and row['actor_type']
  assert row['created_at'] is not None
  if action=='RECOVERY_CASE_CREATED':
   assert b is None and a['case']['state']=='OPEN'
  else:
   assert b['case']['id']==a['case']['id'] and b['snapshot_version']==1
   assert a['case']['version']==b['case']['version']+(action in INCREMENT),'Incorrect actual version transition'
   if action not in {'MANUAL_RECOVERY_SETTLED','RECOVERY_RESUMED_COMPLETED'}:
    for key in ('swap','batteries','payments','holds','commands'):assert b[key]==a[key],f'Unexpected {key} change'
   if action in {'FOREIGN_OBJECT_RETURN_SETTLED','MANUAL_RECOVERY_SETTLED'}:
    op=str(row['after_data']['operation_id'])
    assert b['operations'][op]['consumed_at'] is None and a['operations'][op]['consumed_at']
   if action in {'RECOVERY_NO_EFFECT_CLOSED','RECOVERY_OPERATION_SUPERSEDED'}:
    op=str(row['after_data']['operation_id'])
    assert b['operations'][op]['cancelled_at'] is None and a['operations'][op]['cancelled_at']
   if action in {'RECOVERY_OPERATION_CREATED','RECOVERY_REINSPECTION_REQUESTED'}:
    added=set(a['operations'])-set(b['operations'])
    assert added=={a['case']['operation_id']},'Fabricated before child or missing created operation'
  transitions.append({'action':action,'actor_type':row['actor_type'],'created_at':jsonable_encoder(row['created_at']),
      'before_case_version':b['case']['version'] if b else None,'after_case_version':a['case']['version'],
      'before_state':b['case']['state'] if b else None,'after_state':a['case']['state']})
  prev=latest.get(a['case']['id'])
  if prev is None or a['case']['version']>prev[0]['case']['version']:latest[a['case']['id']]=(a,action)
 cases=[]
 for identity,(snapshot,action) in latest.items():
  t=table('recovery_cases');case=connection.execute(select(t).where(t.c.id==UUID(identity))).mappings().one()
  assert snapshot['case']=={k:jsonable_encoder(case[k]) for k in snapshot['case']}
  ops=connection.execute(select(table('recovery_operations')).where(table('recovery_operations').c.case_id==UUID(identity))).mappings().all()
  current={str(p['id']):p for p in ops}
  assert set(current)==set(snapshot['operations'])
  for key,op in snapshot['operations'].items():assert op=={k:jsonable_encoder(current[key][k]) for k in op}
  if action in {'FOREIGN_OBJECT_RETURN_SETTLED','MANUAL_RECOVERY_SETTLED','RECOVERY_RESUMED_COMPLETED','RECOVERY_NO_EFFECT_CLOSED'}:
   for group,name in [('batteries','batteries'),('payments','payments'),('holds','resource_reservations')]:
    for key,expected in snapshot[group].items():
     t=table(name);actual=connection.execute(select(t).where(t.c.id==UUID(key))).mappings().one()
     assert expected=={k:jsonable_encoder(actual[k]) for k in expected},f'Final {group} differs from committed audit'
  holds=table('resource_reservations');payments=table('payments')
  active=connection.execute(select(holds.c.id).where(holds.c.swap_id==case['swap_id'],holds.c.released_at.is_(None))).all()
  states=list(connection.scalars(select(payments.c.state).where(payments.c.swap_id==case['swap_id'])))
  cases.append({'id':identity,'version':case['version'],'state':case['state'],'old_pin_settled':case['old_pin_settled'],
      'new_pin_delivered':case['new_pin_delivered'],'active_holds':len(active),'payment_states':states})
 connection.rollback()
 return {'schema':schema,'audit_events':len(events),'actions':counts,'transitions':transitions,
     'cases':cases,'status':'PASSED','read_only':True}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--report',action='append',required=True)
 parser.add_argument('--output',required=True);args=parser.parse_args()
 root=Path(__file__).resolve().parents[1]/'docs/PHASE8A_TESTS'
 output=Path(args.output).resolve()
 if not output.is_relative_to(root) or output.exists():raise ValueError('Use a new evidence path under PHASE8A_TESTS')
 engine=create_engine(Settings.from_env().database_url,hide_parameters=True,connect_args={'connect_timeout':5})
 results=[]
 try:
  for path in args.report:
   report=Path(path).resolve()
   if not report.is_relative_to(root):raise ValueError('Expected test report')
   data=json.loads(report.read_text(encoding='utf-8-sig'));schema=data['schema']
   if not re.fullmatch(r'phase5_test_[a-f0-9]+',schema):raise ValueError('Refusing non-fixture schema')
   with engine.connect() as c:results.append(verify(c,schema))
 finally:engine.dispose()
 with output.open('x',encoding='utf8') as f:json.dump(results,f,indent=2)
 print(json.dumps(results,indent=2))

if __name__=='__main__':main()
