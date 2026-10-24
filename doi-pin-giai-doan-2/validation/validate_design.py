"""Static design checks only; does not execute PostgreSQL or application code.
Install: pip install pyyaml openapi-spec-validator pglast jsonschema pillow
Run: python validation/validate_design.py from bundle root.
"""
from pathlib import Path
import json, csv, hashlib, re
from xml.etree import ElementTree as ET
import yaml
from openapi_spec_validator import validate_spec
from pglast import parse_sql
from jsonschema import Draft202012Validator
from PIL import Image
P=Path(__file__).resolve().parents[1]
spec=yaml.safe_load((P/'contracts/openapi.yaml').read_text())
validate_spec(spec)
statements=parse_sql((P/'database/schema.sql').read_text())
config=yaml.safe_load((P/'contracts/demo-config.proposed.yaml').read_text())
Draft202012Validator(json.loads((P/'contracts/demo-config.schema.json').read_text())).validate(config)
FR={f'FR{i:02}' for i in range(1,20)};UC={f'UC{i:02}' for i in range(1,18)}
seen_fr=set();seen_uc=set();ids=[]
for path,methods in spec['paths'].items():
 for method,op in methods.items():
  if method not in ('get','post','put','patch','delete'):continue
  assert set(op['x-fr'])<=FR and set(op['x-uc'])<=UC
  seen_fr.update(op['x-fr']);seen_uc.update(op['x-uc']);ids.append(op['operationId'])
assert seen_fr==FR and seen_uc==UC
assert len(ids)==len(set(ids))
trace=list(csv.DictReader((P/'contracts/traceability.csv').open(encoding='utf-8-sig')))
assert {r['FR'] for r in trace}==FR
for r in trace:
 assert set(r['Operation IDs'].split(';'))<=set(ids)
 for name in r['Diagrams'].split(';'):assert (P/'diagrams'/f'{name}.puml').exists()
for name,digest in json.loads((P/'baseline/SHA256.json').read_text()).items():
 assert hashlib.sha256((P/'baseline'/name).read_bytes()).hexdigest()==digest
for f in (P/'diagrams').glob('*.puml'):
 assert f.read_text().startswith('@startuml') and f.read_text().rstrip().endswith('@enduml')
 svg=f.with_suffix('.svg');ET.parse(svg)
 assert 'Syntax Error' not in svg.read_text()
 im=Image.open(f.with_suffix('.png'));im.load()
result={'baseline_sha256':'passed','openapi_validator':'passed','operations':len(ids),'fr_coverage':len(seen_fr),'uc_coverage':len(seen_uc),'sql_parser':'passed','sql_statements':len(statements),'config_schema':'passed','source_and_image_pairs':len(list((P/'diagrams').glob('*.puml'))),'database_executed':False,'application_tests_executed':False}
(P/'validation/structural-checks.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
