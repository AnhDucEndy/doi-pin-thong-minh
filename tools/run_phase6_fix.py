"""Run existing tests/scripts while routing reports away from pre-fix evidence."""
import contextlib
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend'), str(ROOT/'tests'), str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
label, mode, *args = sys.argv[1:]
if not label.replace('_', '').isalnum() or mode not in ('pytest', 'script'):
    raise ValueError('Use LABEL pytest [args] or LABEL script path [args]')
report_root = os.environ.get('TEST_REPORT_ROOT', 'PHASE6_FIX')
if report_root not in ('PHASE6_FIX', 'PHASE7_TESTS'):
    raise ValueError('Unsupported report directory')
OUT = ROOT/'docs'/report_root/label
OUT.mkdir(parents=True, exist_ok=False)
temp = ROOT/'.cache'/('p6-fix-'+uuid4().hex[:10]); temp.mkdir()
os.environ.update(PYTHONPATH=str(ROOT/'services/backend'), PYTHONIOENCODING='utf-8', TEMP=str(temp), TMP=str(temp))
write_text, write_bytes = Path.write_text, Path.write_bytes


def destination(path):
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT/'docs') and not resolved.is_relative_to(OUT):
        path = OUT/'reports'/resolved.relative_to(ROOT/'docs')
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


code = 0
with (OUT/'run.log').open('w', encoding='utf-8') as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), patch.object(
        Path, 'write_text', lambda p, *a, **k: write_text(destination(p), *a, **k)), patch.object(
        Path, 'write_bytes', lambda p, *a, **k: write_bytes(destination(p), *a, **k)):
        try:
            if mode == 'pytest':
                import pytest
                code = pytest.main([*args, '-q', '--tb=short', '--basetemp='+str(temp/'pytest'),
                                    '--junitxml='+str(OUT/'results.xml')])
            else:
                sys.argv = args
                runpy.run_path(str(ROOT/args[0]), run_name='__main__')
        except SystemExit as exc:
            code = exc.code or 0
        except Exception:
            import traceback
            traceback.print_exc(); code = 1
print((OUT/'run.log').read_text(encoding='utf-8')[-9000:])
sys.exit(code)
