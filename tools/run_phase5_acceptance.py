"""Acceptance runner: keep prior reports intact; never reset databases or ledgers."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.getenv('P5_EVIDENCE_DIR', 'docs/PHASE5_ACCEPTANCE')
if not OUT.resolve().is_relative_to(ROOT):
    raise ValueError('Keep acceptance evidence inside the workspace')
OUT.mkdir(parents=True, exist_ok=True)
label, *args = sys.argv[1:]
if not label.replace('_', '').isalnum():
    raise ValueError('Use an alphanumeric evidence label')
protected = [ROOT / p for p in ('docs/PHASE5_TEST_ENVIRONMENT.json',
    'docs/PHASE4_ACCEPTANCE/LATE_TELEMETRY_FINDING.json',
    'docs/PHASE5_E2E_RESULTS.json', 'docs/PHASE4_E2E_RESULTS.json',
    'docs/PHASE5_HTTP_SMOKE_RESULTS.json')]
previous = {p: p.read_bytes() if p.exists() else None for p in protected}
for name in ('STALE_DOOR_1', 'STALE_DOOR_2', 'STRICTLY_OLDER_DOOR_1', 'STRICTLY_OLDER_DOOR_2'):
    p = ROOT / 'docs/PHASE5_ACCEPTANCE' / (name + '.json')
    previous[p] = p.read_bytes() if p.exists() else None
for p in protected:
    p.parent.mkdir(parents=True, exist_ok=True)
temp = ROOT / '.cache' / ('p5-acceptance-' + uuid.uuid4().hex[:10])
temp.mkdir(parents=True)
env = dict(os.environ, PYTHONPATH=str(ROOT / 'services/backend'),
           PYTHONIOENCODING='utf-8', TEMP=str(temp), TMP=str(temp))
if args and args[0] == '--script':
    command = [sys.executable, *args[1:]]
else:
    command = [sys.executable, '-m', 'pytest', *args, '-q', '--tb=short',
        '--basetemp=' + str(temp / 'pytest'), '--junitxml=' + str(OUT / (label + '.xml'))]
try:
    with (OUT / (label + '.log')).open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    print((OUT / (label + '.log')).read_text(encoding='utf-8'))
finally:
    for p, old in previous.items():
        if p.exists() and p.read_bytes() != old:
            (OUT / (label + '_' + p.name)).write_bytes(p.read_bytes())
            if old is not None:
                p.write_bytes(old)
            else:
                # Preserve newly produced evidence at its original path as well.
                pass
sys.exit(result.returncode)
