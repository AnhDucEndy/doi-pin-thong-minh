"""Reuse the real-process E2E without overwriting its committed implementation report."""
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OLD = ROOT / 'docs/PHASE6_TESTS/E2E_FINAL_RESULTS.json'
NEW = ROOT / 'docs/PHASE6_ACCEPTANCE/E2E_RESULTS.json'
original = Path.write_text


def write_report(path, data, *args, **kwargs):
    return original(NEW if path.resolve() == OLD.resolve() else path, data, *args, **kwargs)


if __name__ == '__main__':
    NEW.parent.mkdir(exist_ok=True)
    with patch.object(Path, 'write_text', write_report):
        runpy.run_path(str(ROOT / 'tools/smoke_phase6.py'), run_name='__main__')
