"""B0 only: schemas/examples/OpenAPI composition. No lifespan, DB or HTTP calls."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'services/backend'))
import yaml
from jsonschema import Draft202012Validator,FormatChecker
from openapi_spec_validator import validate_spec

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def example(s,defs,path='root'):
 if '$ref' in s:return example(defs[s['$ref'].split('/')[-1]],defs,path)
 if 'const' in s:return s['const']
 if 'enum' in s:return s['enum'][0]
 if 'oneOf' in s or 'anyOf' in s:return example(s.get('oneOf',s.get('anyOf'))[0],defs,path)
 t=s.get('type')
 if isinstance(t,list):t=next((v for v in t if v!='null'),t[0])
 if t=='object':
  value={k:example(s['properties'][k],defs,path+'.'+k) for k in s.get('required',[])}
  for clause in s.get('allOf',[]):
   if 'if' in clause and Draft202012Validator(clause['if']).is_valid(value):
    then=clause.get('then',{})
    for k in then.get('required',[]):
     if k not in value:value[k]=example(s['properties'][k],defs,path+'.'+k)
    for k,v in then.get('properties',{}).items():
     if 'const' in v:value[k]=v['const']
  return value
 if t=='array':return [example(s['items'],defs,path+'.'+str(i)) for i in range(s.get('minItems',0))]
 if t=='integer':return s.get('minimum',0)
 if t=='boolean':return False
 if t=='null':return None
 if s.get('format')=='uuid':return str(uuid5(NAMESPACE_URL,path))
 if s.get('format')=='date-time':return '2026-11-16T00:00:00Z'
 if '{64}' in s.get('pattern',''):return 'a'*64
 return 'example'
def validate(output):
 basepath=ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml';baseline=yaml.safe_load(basepath.read_text(encoding='utf8'))
 bundles={v:read(ROOT/'docs/implementation-contracts'/v/'contract.schema.json') for v in ('P8-REF-0.1','P8-REC-0.3')}
 checks=[]
 for name,bundle in bundles.items():
  Draft202012Validator.check_schema(bundle)
  for key,schema in bundle['$defs'].items():
   full={'$schema':bundle['$schema'],'$defs':bundle['$defs'],'$ref':'#/$defs/'+key}
   v=Draft202012Validator(full,format_checker=FormatChecker());sample=example(schema,bundle['$defs'])
   v.validate(sample);checks.append(name+':'+key+':positive-shape')
   if isinstance(sample,dict):
    assert list(v.iter_errors({**sample,'unexpected_field':'forbidden'}));checks.append(name+':'+key+':reject-extra')
  # Strictness is recursively required on all declared object structures.
  def strict(v):
   if isinstance(v,dict):
    if v.get('type')=='object':assert v.get('additionalProperties') is False
    for x in v.values():strict(x)
   if isinstance(v,list):
    for x in v:strict(x)
  strict(bundle)
 rf=bundles['P8-REF-0.1'];rd=rf['$defs'];nd=bundles['P8-REC-0.3']
 for forbidden,value in [('amount_minor',9000),('currency','VND'),('actor_id',str(uuid5(NAMESPACE_URL,'actor'))),('role','ADMIN'),('state','SUCCEEDED'),('custody','CUSTOMER')]:
  v=Draft202012Validator({'$defs':rd,'$ref':'#/$defs/ReasonAction'})
  assert list(v.iter_errors({'expected_version':1,'reason':'Admin review',forbidden:value}));checks.append('public-request-reject-'+forbidden)
 assert rd['ReasonAction']==baseline['components']['schemas']['ReasonAction']
 assert rd['LegacyProviderRefundRequest']==baseline['components']['schemas']['ProviderRefundRequest']
 assert rd['LegacyProviderResult']==baseline['components']['schemas']['ProviderResult']
 for field,value in [('result','SUCCEEDED'),('result','FAILED')]:
  v=Draft202012Validator({'$defs':rd,'$ref':'#/$defs/AttemptResult'})
  data=example(rd['AttemptResult'],rd);data[field]=value
  assert list(v.iter_errors(data));checks.append('reject-result-with-inconsistent-phase/effect-'+value)
 q=example(rd['QueryContext'],rd);q['mode']='SEAL_UNACCEPTED'
 assert list(Draft202012Validator({'$defs':rd,'$ref':'#/$defs/QueryContext'}).iter_errors(q));checks.append('seal-requires-reconciliation-reference')
 # Build current Phase8A spec only; lifespan is never entered, Database not constructed.
 from app.main import create_app
 spec=create_app().openapi();prior=copy.deepcopy(spec);oldpaths=set(prior['paths'])
 for folder,prefix in [('P8-REF-0.1','P8RF'),('P8-REC-0.3','P8ND')]:
  overlay=yaml.safe_load((ROOT/'docs/implementation-contracts'/folder/'openapi.overlay.yaml').read_text(encoding='utf8'))
  validate_spec(overlay)
  for k,v in overlay['components']['schemas'].items():
   if k.startswith(prefix):spec['components']['schemas'][k]=v
  for path,methods in overlay['paths'].items():
   for method,new in methods.items():
    if method not in ('get','post'):continue
    old=spec['paths'].get(path,{}).get(method)
    if old:
     assert old['security']==new['security'] and old['operationId']==new['operationId']
     op=copy.deepcopy(old)
     if 'requestBody' in new:
      a=old['requestBody']['content']['application/json']['schema'];b=new['requestBody']['content']['application/json']['schema']
      op['requestBody']['content']['application/json']['schema']={'anyOf':[a,b]}
     for status,response in new['responses'].items():
      if status in op['responses'] and 'content' in response and 'content' in op['responses'][status]:
       a=op['responses'][status]['content']['application/json']['schema'];b=response['content']['application/json']['schema']
       op['responses'][status]['content']['application/json']['schema']={'anyOf':[a,b]}
      elif status not in op['responses']:op['responses'][status]=response
    else:op=copy.deepcopy(new)
    spec['paths'].setdefault(path,{})[method]=op
 # Only the existing Customer-owned field may gain the0.3 projection branch.
 view=spec['components']['schemas'][spec['paths']['/v1/swaps/{swap_id}']['get']['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]]
 oldprojection=copy.deepcopy(view['properties']['recovery_confirmation'])
 view['properties']['recovery_confirmation']={'anyOf':[oldprojection,{'$ref':'#/components/schemas/P8NDCustomerProjection'}]}
 validate_spec(spec)
 expected={'/v1/payments/{payment_id}/refund','/v1/refunds/{refund_id}/reconcile','/mock/v1/refunds','/mock/v1/refunds/{provider_key}'}
 assert set(spec['paths'])-oldpaths==expected
 for path,methods in prior['paths'].items():
  for method,old in methods.items():
   if method in ('get','post','patch','delete') and 'security' in old:assert spec['paths'][path][method]['security']==old['security']
 for name in ('PaymentCallback','ProviderChargeRequest','ProviderResult','PaymentState','RefundState'):
  assert spec['components']['schemas'][name]==prior['components']['schemas'][name]
 # Frozen caller/resource lock direction is asserted by contract, not runtime tested here.
 source=read(ROOT/'docs/PHASE8A_TESTS/nfr06_fix_20261115_01/source_final_before.json')
 delta=[v['path'] for v in source if sha(ROOT/v['path'])!=v['sha256']];assert not delta
 old=read(ROOT/'docs/implementation-contracts/P8-REF-0.1/source_baseline.json')
 assert hashlib.sha256(basepath.read_bytes()).hexdigest()==old['baseline_openapi_sha256']
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in old['prior_overlays'].items())
 result={'time_utc':datetime.now(timezone.utc).isoformat(),'status':'PASSED','exit':0,'schema_bundles':len(bundles),
 'schema_definitions':sum(len(v['$defs']) for v in bundles.values()),'shape_checks':len(checks),'checks':checks,
 'standalone_overlays_validated':2,'composed_OpenAPI_valid':True,'legacy_inputs_and_charge_schemas_unchanged':True,
 'existing_endpoint_security_unchanged':True,'new_paths':sorted(expected),'source_files':179,'source_delta':delta,
 'historical_overlays_unchanged':True,'runtime_tests':'NOT RUN','database_migrations':'NOT RUN','refund_effects':0}
 if output:
  with Path(output).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
 print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args();validate(args.output)
