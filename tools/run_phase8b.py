"""Isolated B1a test reports, source hashes and read-only demo fingerprints.

Usage: .venv/Scripts/python tools/run_phase8b.py UNIQUE_LABEL [pytest arguments]
Never runs an Alembic upgrade against the configured demo schema.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
import runpy
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT)]
from app.config import Settings
from sqlalchemy import create_engine, text


def hashes():
    base = json.loads((ROOT/'docs/PHASE8A_TESTS/nfr06_fix_20261115_01/source_final_before.json').read_text(encoding='utf8'))
    paths = {v['path'] for v in base}
    frozen = json.loads((ROOT/'docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json').read_text(encoding='utf8'))
    paths.update(v['path'] for v in frozen['files'] if v['path']!='docs/IMPLEMENTATION_STATUS.md')
    paths.add('docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json')
    paths.update(str(p.relative_to(ROOT)).replace('\\', '/') for folder in
        ('services/backend/app', 'services/backend/alembic/versions') for p in (ROOT/folder).rglob('*.py'))
    paths.update(('tests/test_phase8b_b1a.py', 'tools/run_phase8b.py', 'tools/provision_database.py'))
    paths.update(str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT/'tests').glob('test_phase8b*.py'))
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'simulators/device').glob('*.py'))
    paths.update(p.relative_to(ROOT).as_posix() for name in
                 ('smoke_phase8b_b1b.py', 'validate_phase8b_b1b.py')
                 if (p := ROOT/'tools'/name).is_file())
    return [{'path': p, 'sha256': hashlib.sha256((ROOT/p).read_bytes()).hexdigest().upper()} for p in sorted(paths)]


def demo(schema=None):
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True,
        connect_args={'connect_timeout': 5, 'options': '-cdefault_transaction_read_only=on'})
    schema = schema or Settings.from_env().schema
    tables = ('users','stations','compartments','batteries','swap_transactions','payments','refunds','audit_events')
    with engine.connect() as c:
        result = {name: c.scalar(text(f'SELECT md5(COALESCE(string_agg(row_to_json(t)::text,\'\' ORDER BY t.id),\'\')) FROM {schema}.{name} t')) for name in tables}
        result['revision'] = c.scalar(text(f'SELECT version_num FROM {schema}.alembic_version'))
    engine.dispose()
    return result


def main():
    label, *args = sys.argv[1:]
    if not label.replace('_', '').isalnum():
        raise ValueError('Unique alphanumeric/underscore label required')
    out = ROOT/'docs/PHASE8B_TESTS'/label
    out.mkdir(parents=True, exist_ok=False)
    temp = ROOT/'.cache'/('b1a-'+uuid4().hex)
    temp.mkdir(parents=True)
    os.environ.update(PYTHONPATH=str(ROOT/'services/backend'), TEMP=str(temp), TMP=str(temp))
    demo_schema = Settings.from_env().schema
    before, fingerprint = hashes(), demo(demo_schema)
    (out/'source_before.json').write_text(json.dumps(before, indent=2), encoding='utf8')
    started = datetime.now(timezone.utc).isoformat()
    write = Path.write_text

    def routed(path, *a, **kw):
        resolved = path.resolve()
        if resolved.is_relative_to(ROOT/'docs') and not resolved.is_relative_to(out):
            path = out/'reports'/resolved.relative_to(ROOT/'docs')
            path.parent.mkdir(parents=True, exist_ok=True)
        return write(path, *a, **kw)

    code = 1
    with (out/'run.log').open('w', encoding='utf8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), patch.object(Path, 'write_text', routed):
            if args and args[0]=='script':
                script_args=args[1:]
                if not script_args or script_args[0]!='tools/smoke_phase8b_b1b.py':
                    raise ValueError('Only the approved B1b runner is supported')
                os.environ['B1B_REPORT_DIR']=str(out)
                sys.argv=script_args
                try:
                    runpy.run_path(str(ROOT/script_args[0]),run_name='__main__')
                    code=0
                except SystemExit as exc:
                    code=int(exc.code or 0)
                except Exception as exc:
                    print('Script failure:',type(exc).__name__,str(exc))
                    code=1
            else:
                import pytest
                code = int(pytest.main([*args, '-q', '--tb=short', '--basetemp='+str(temp/'pytest'), '--junitxml='+str(out/'results.xml')]))
    after, demo_after = hashes(), demo(demo_schema)
    result = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'fingerprint_schema': demo_schema,
        'exit_code': code, 'source_unchanged_during_run': before == after,
        'demo_fingerprint_unchanged': fingerprint == demo_after,
        'demo_before': fingerprint, 'demo_after': demo_after,
        'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()}
    (out/'source_after.json').write_text(json.dumps(after, indent=2), encoding='utf8')
    (out/'exit.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))
    print((out/'run.log').read_text(encoding='utf8')[-3500:])
    return code if before == after and fingerprint == demo_after else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8', errors='replace')
    sys.exit(main())
