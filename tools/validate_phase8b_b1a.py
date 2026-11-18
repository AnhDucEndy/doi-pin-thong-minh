"""B1a static contract validation; B0 validator/freeze remains historical, unchanged."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/backend'))
from app.main import create_app
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec
import yaml


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main(output):
    loader=importlib.util.spec_from_file_location('b0_static',ROOT/'docs/implementation-contracts/P8-REF-0.1/validate_static.py')
    b0=importlib.util.module_from_spec(loader);loader.loader.exec_module(b0)
    checks=[];bundles={};overlays=[]
    for version in ('P8-REF-0.1','P8-REC-0.3'):
        root=ROOT/'docs/implementation-contracts'/version
        bundle=read(root/'contract.schema.json');bundles[version]=bundle
        Draft202012Validator.check_schema(bundle)
        for name,schema in bundle['$defs'].items():
            validator=Draft202012Validator({'$defs':bundle['$defs'],'$ref':'#/$defs/'+name},format_checker=FormatChecker())
            sample=b0.example(schema,bundle['$defs'])
            validator.validate(sample);checks.append(version+':'+name+':positive')
            if isinstance(sample,dict):
                assert list(validator.iter_errors({**sample,'unexpected_field':'forbidden'}))
                checks.append(version+':'+name+':strict')
        overlay=yaml.safe_load((root/'openapi.overlay.yaml').read_text(encoding='utf8'))
        validate_spec(overlay);overlays.append(overlay)
    rf=bundles['P8-REF-0.1']['$defs']
    for key,value in [('amount_minor',9000),('currency','VND'),('actor_id','actor'),('role','ADMIN'),('state','SUCCEEDED'),('custody','CUSTOMER')]:
        assert not Draft202012Validator(rf['ReasonAction']).is_valid({'expected_version':1,'reason':'review',key:value})
        checks.append('request-reject-'+key)
    for result in ('SUCCEEDED','FAILED'):
        data=b0.example(rf['AttemptResult'],rf);data['result']=result
        assert not Draft202012Validator({'$defs':rf,'$ref':'#/$defs/AttemptResult'}).is_valid(data)
        checks.append('reject-inconsistent-result-'+result)
    data=b0.example(rf['QueryContext'],rf);data['mode']='SEAL_UNACCEPTED'
    assert not Draft202012Validator({'$defs':rf,'$ref':'#/$defs/QueryContext'}).is_valid(data)
    checks.append('seal-requires-reference')
    actual=create_app().openapi();validate_spec(actual)
    original=yaml.safe_load((ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml').read_text(encoding='utf8'))
    refund_paths={'/v1/payments/{payment_id}/refund','/v1/refunds/{refund_id}/reconcile'}
    for path in refund_paths:
        assert actual['paths'][path]==original['paths'][path]
    assert not any(p.startswith('/mock/') for p in actual['paths'])
    # Design-only composition does NOT register 0.3/provider routes in runtime.
    composed=deepcopy(actual)
    for overlay,prefix in zip(overlays,('P8RF','P8ND')):
        composed['components']['schemas'].update({n:d for n,d in overlay['components']['schemas'].items() if n.startswith(prefix)})
        for path,methods in overlay['paths'].items():
            for method,op in methods.items():
                old=composed['paths'].get(path,{}).get(method)
                if old:
                    assert old['security']==op['security'] and old['operationId']==op['operationId']
                    merged=deepcopy(old)
                    if 'requestBody' in op:
                        a=old['requestBody']['content']['application/json']['schema']
                        b=op['requestBody']['content']['application/json']['schema']
                        merged['requestBody']['content']['application/json']['schema']={'anyOf':[a,b]}
                    for status,response in op['responses'].items():
                        if status in merged['responses'] and 'content' in response and 'content' in merged['responses'][status]:
                            a=merged['responses'][status]['content']['application/json']['schema']
                            b=response['content']['application/json']['schema']
                            merged['responses'][status]['content']['application/json']['schema']={'anyOf':[a,b]}
                    composed['paths'][path][method]=merged
                else:composed['paths'].setdefault(path,{})[method]=deepcopy(op)
    projection=composed['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation']
    composed['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation']={
        'anyOf':[deepcopy(projection),{'$ref':'#/components/schemas/P8NDCustomerProjection'}]}
    validate_spec(composed)
    assert set(composed['paths'])-set(actual['paths'])=={'/mock/v1/refunds','/mock/v1/refunds/{provider_key}'}
    for path,methods in actual['paths'].items():
        for method,op in methods.items():
            if 'security' in op:assert composed['paths'][path][method]['security']==op['security']
    baseline=read(ROOT/'docs/implementation-contracts/P8-REF-0.1/source_baseline.json')
    assert hashlib.sha256((ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml').read_bytes()).hexdigest()==baseline['baseline_openapi_sha256']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in baseline['prior_overlays'].items())
    freeze=read(ROOT/'docs/PHASE8A_TESTS/nfr06_fix_20261115_01/source_final_before.json')
    delta=[v['path'] for v in freeze if hashlib.sha256((ROOT/v['path']).read_bytes()).hexdigest().upper()!=v['sha256'].upper()]
    expected={'services/backend/app/main.py','services/backend/app/application/assets.py',
        'services/backend/app/application/identity.py','services/backend/app/api/assets.py',
        'services/backend/app/api/batteries.py','services/backend/app/api/device.py',
        'tests/test_phase1.py','tests/test_phase8a_migration.py','tools/provision_database.py'}
    assert set(delta)==expected
    b0_freeze=read(ROOT/'docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json')
    assert all(v['path']=='docs/IMPLEMENTATION_STATUS.md' or hashlib.sha256((ROOT/v['path']).read_bytes()).hexdigest().upper()==v['sha256'].upper() for v in b0_freeze['files'])
    result={'exit_code':0,'static_shape_checks':len(checks),'schema_definitions':sum(len(b['$defs']) for b in bundles.values()),
        'checks':checks,'runtime_openapi_valid':True,'design_composition_valid':True,
        'baseline_and_historical_overlays_unchanged':True,'b0_contract_files_unchanged':True,
        'expected_delta_from_179_file_8a_freeze':delta,'new_runtime_public_paths':sorted(refund_paths),
        'provider_and_recovery_03_runtime_implemented':False}
    with Path(output).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))


if __name__=='__main__':main(sys.argv[1])
