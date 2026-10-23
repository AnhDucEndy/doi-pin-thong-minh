"""Official validators, read-only inputs; write evidence only outside design bundle."""
from pathlib import Path
import hashlib
import json
import sys

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate_spec
from pglast import parse_sql

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'doi-pin-giai-doan-2'


def main():
    spec = yaml.safe_load((BUNDLE / 'contracts/openapi.yaml').read_text(encoding='utf-8-sig'))
    validate_spec(spec)
    config = yaml.safe_load((BUNDLE / 'contracts/demo-config.approved.yaml').read_text(encoding='utf-8-sig'))
    schema = json.loads((BUNDLE / 'contracts/demo-config.schema.json').read_text(encoding='utf-8-sig'))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(config)
    statements = parse_sql((BUNDLE / 'database/schema.sql').read_text(encoding='utf-8-sig'))
    for manifest, base in [('baseline/SHA256.json', BUNDLE / 'baseline'), ('validation/delivery-sha256.json', BUNDLE)]:
        for name, expected in json.loads((BUNDLE / manifest).read_text(encoding='utf-8-sig')).items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Design file changed: ' + name)
    result = {'openapi_validator': 'Passed', 'approved_json_schema': 'Passed', 'sql_parser': 'Passed',
              'sql_statements': len(statements), 'original_design_hashes': 'Passed',
              'database_executed_by_this_script': False}
    if len(sys.argv) > 1:
        output = (ROOT / sys.argv[1]).resolve()
        if not output.is_relative_to(ROOT / 'docs'):
            raise ValueError('Evidence output must be inside docs/')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
