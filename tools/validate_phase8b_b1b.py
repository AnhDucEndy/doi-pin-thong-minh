"""B1b static/provenance and read-only audit verification. Never migrates data.

Usage: python tools/validate_phase8b_b1b.py NEW_OUTPUT.json [E2E_LABEL ...]
Raw private fixtures remain local. Output contains hashes/counts, never tokens.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'services/backend'), str(ROOT)]

AUDIT_ACTIONS = frozenset(('ND_OPERATION_CREATED', 'ND_SUCCESSOR_LINKED',
    'ND_INSPECTION_ACCEPTED', 'ND_HUMAN_ATTESTED', 'ND_CERTIFICATE_ISSUED',
    'ND_CERTIFICATE_REVOKED', 'ND_CERTIFICATE_REDEEMED', 'REFUND_REQUEST_CREATED'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def audit_check(events):
    """Assert actual transition values, not merely non-null before/after."""
    result = []
    for event in events:
        action = event['action']
        if action not in AUDIT_ACTIONS:
            continue
        before, after = event['before_data'], event['after_data']
        assert before is not None and after is not None
        if action == 'REFUND_REQUEST_CREATED':
            assert before['refund'] is None
            refund = after['refund']
            assert refund['state'] == 'REQUESTED' and refund['version'] == 1
            assert refund['provider_reference'] is None and refund['verified_at'] is None
            assert refund['charge_state'] == 'SUCCEEDED' and refund['currency'] == 'VND'
            before, after = before['recovery_snapshot'], after['recovery_snapshot']
        bc, ac = before['case'], after['case']
        assert bc['id'] == ac['id'] and bc['swap_id'] == ac['swap_id']
        assert bc['old_pin_settled'] == ac['old_pin_settled']
        for name in ('batteries', 'payments', 'holds'):
            assert before[name] == after[name], (action, name)
        if action in ('ND_CERTIFICATE_REDEEMED', 'REFUND_REQUEST_CREATED'):
            assert bc == ac
            assert before['swap']['state'] == 'REVIEW_REQUIRED'
            assert after['swap']['state'] == 'COMPENSATING'
            assert after['swap']['version'] == before['swap']['version'] + 1
            assert len(after['no_delivery_redemptions']) == len(before['no_delivery_redemptions']) + 1
            assert before['no_delivery_certificates'] == after['no_delivery_certificates']
        else:
            assert before['swap'] == after['swap']
            delta = 0 if action == 'ND_CERTIFICATE_REVOKED' and bc['new_pin_delivered'] != 'NO' else 1
            assert ac['version'] == bc['version'] + delta
        if action in ('ND_OPERATION_CREATED', 'ND_SUCCESSOR_LINKED'):
            added = set(after['operations']) - set(before['operations'])
            assert len(added) == 1 and ac['operation_id'] in added
            op = after['operations'][ac['operation_id']]
            assert op['protocol_version'] == '0.3' and op['purpose'] == 'VERIFY_NO_DELIVERY'
            assert op['consumed_at'] is None and op['cancelled_at'] is None
            assert op['base_case_version'] == bc['version']
            if action == 'ND_SUCCESSOR_LINKED':
                prior = op['supersedes_id']
                assert prior == bc['operation_id'] and before['operations'][prior]['cancelled_at'] is None
                assert after['operations'][prior]['cancelled_at'] is not None
            else:
                assert op['supersedes_id'] is None
            assert ac['new_pin_delivered'] == 'UNKNOWN'
        elif action in ('ND_INSPECTION_ACCEPTED', 'ND_HUMAN_ATTESTED'):
            added = set(after['attestations']) - set(before['attestations'])
            assert len(added) == 1
            proof = after['attestations'][added.pop()]
            assert proof['operation_id'] == ac['operation_id'] and proof['stage'] == 'NO_DELIVERY_INSPECTION'
            assert ac['new_pin_delivered'] == 'UNKNOWN'
            if action == 'ND_INSPECTION_ACCEPTED':
                assert proof['source_kind'] == 'SIMULATOR' and proof['source_boot']
                assert proof['device_id'] and proof['source_event_id'] == ac['evidence_event_id']
            else:
                assert proof['source_kind'] in ('TECHNICIAN', 'CUSTOMER') and proof['actor_user_id']
                assert proof['reference_receipt_id'] in before['attestations']
        elif action == 'ND_CERTIFICATE_ISSUED':
            assert bc['new_pin_delivered'] == 'UNKNOWN'
            assert ac['new_pin_delivered'] == 'NO' and ac['state'] == 'EVIDENCE_RECORDED'
            added = set(after['no_delivery_certificates']) - set(before['no_delivery_certificates'])
            assert len(added) == 1
            cert = after['no_delivery_certificates'][added.pop()]
            assert cert['operation_id'] == ac['operation_id'] and cert['issued_by'] and cert['issuer_session_id']
            assert cert['validated_at'] < cert['valid_until']
            for key in ('receipt_id', 'technician_attestation_id', 'customer_attestation_id'):
                assert cert[key] in before['attestations']
        elif action == 'ND_CERTIFICATE_REVOKED':
            assert ac['new_pin_delivered'] == 'UNKNOWN'
            assert len(after['no_delivery_revocations']) == len(before['no_delivery_revocations']) + 1
            assert before['no_delivery_certificates'] == after['no_delivery_certificates']
        assert event['actor_id'] and event['correlation_id']
        # Check structural secret boundaries; session/receipt UUID references
        # are provenance, not reusable credentials. Never output payload values.
        prohibited = {'password', 'password_hash', 'token', 'access_token', 'token_hash',
            'authorization', 'cookie', 'device_key', 'raw_qr', 'qr_token', 'note', 'reason',
            'headers', 'payload', 'raw_payload', 'resolution_note', 'credentials'}
        def clean(value):
            if isinstance(value, dict):
                assert not prohibited.intersection(k.lower().replace('-', '_') for k in value)
                for item in value.values(): clean(item)
            elif isinstance(value, list):
                for item in value: clean(item)
        clean(event['before_data']); clean(event['after_data'])
        result.append(action)
    return Counter(result)


# Reviewed PC portability exceptions. Each path still requires the original raw
# digest to be reproduced; this is not a normalized replacement manifest.
EOL_ALLOWLIST = frozenset((
    ".gitattributes",
    "README.md",
    "apps/web/src/styles.css",
    "docs/CONTRACT_VALIDATION.json",
    "docs/HTTP_SMOKE_RESULTS.json",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/PHASE0_CHECKS.json",
    "docs/PHASE1_ENVIRONMENT.json",
    "docs/PHASE2_CONTRACT_VALIDATION.json",
    "docs/PHASE2_DISK_USAGE.json",
    "docs/PHASE2_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE2_IMPLEMENTATION.md",
    "docs/PHASE3_CONTRACT_VALIDATION.json",
    "docs/PHASE3_DATABASE_CHECK.json",
    "docs/PHASE3_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE4_CONTRACT_VALIDATION.json",
    "docs/PHASE4_DISK_USAGE.json",
    "docs/PHASE4_E2E_RESULTS.json",
    "docs/PHASE4_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE4_TEST_ENVIRONMENT.json",
    "docs/PHASE4_UI_RESULTS.json",
    "docs/PHASE5_ACCEPTANCE/STALE_DOOR_1.json",
    "docs/PHASE5_ACCEPTANCE/STALE_DOOR_2.json",
    "docs/PHASE5_ACCEPTANCE/STRICTLY_OLDER_DOOR_1.json",
    "docs/PHASE5_ACCEPTANCE/STRICTLY_OLDER_DOOR_2.json",
    "docs/PHASE5_BMS_GUARD_RESULTS.json",
    "docs/PHASE5_BROWSER_RESULTS.json",
    "docs/PHASE5_CONTRACT_VALIDATION.json",
    "docs/PHASE5_DISK_USAGE.json",
    "docs/PHASE5_E2E_RESULTS.json",
    "docs/PHASE5_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE5_IOT_REGRESSION_RESULTS.json",
    "docs/PHASE5_P5_A01_FIX/BEFORE.xml",
    "docs/PHASE5_P5_A01_FIX/CONTRACTS.json",
    "docs/PHASE5_P5_A01_FIX/E2E_IOT_PHASE4_E2E_RESULTS.json",
    "docs/PHASE5_P5_A01_FIX/E2E_PHASE5_PHASE5_E2E_RESULTS.json",
    "docs/PHASE5_P5_A01_FIX/E2E_PHASE5_PHASE5_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE5_VERIFICATION_SUMMARY.json",
    "docs/PHASE6_ACCEPTANCE.md",
    "docs/PHASE6_ACCEPTANCE/REFERENCE_COLLISION.json",
    "docs/PHASE6_ACCEPTANCE/SLOW_READ_CONSENT.json",
    "docs/PHASE6_ACCEPTANCE/SLOW_READ_SETTLEMENT.json",
    "docs/PHASE6_BLOCKER_FIX.md",
    "docs/PHASE6_FIX/COMMIT_EVIDENCE.md",
    "docs/PHASE6_FIX/HISTORICAL_P6_A02/manifest.json",
    "docs/PHASE6_FIX/HISTORICAL_P6_A03/manifest.json",
    "docs/PHASE6_FIX/LOCK_TIMEOUT_CHARACTERIZATION/reports/PHASE6_FIX/LOCK_TIMEOUT_device.json",
    "docs/PHASE6_FIX/LOCK_TIMEOUT_CHARACTERIZATION/reports/PHASE6_FIX/LOCK_TIMEOUT_payment.json",
    "docs/PHASE6_TESTS/E2E_FINAL_RESULTS.json",
    "docs/PHASE6_TESTS/REGRESSION_E2E_PHASE5_PHASE5_E2E_RESULTS.json",
    "docs/PHASE6_TESTS/REGRESSION_E2E_PHASE5_PHASE5_HTTP_SMOKE_RESULTS.json",
    "docs/PHASE6_TESTS/REGRESSION_IOT_PHASE4_E2E_RESULTS.json",
    "docs/PHASE6_TESTS/RELEASE_CONTRACTS.json",
    "docs/PHASE7_ACCEPTANCE.md",
    "docs/PHASE7_IMPLEMENTATION.md",
    "docs/PHASE7_TESTS/FINAL_VERIFICATION.json",
    "docs/PHASE8A_GIT_READINESS.md",
    "docs/PHASE8A_HANDOFF/STAGING_PROPOSAL.txt",
    "docs/PHASE8A_IMPLEMENTATION.md",
    "docs/PHASE8A_INDEPENDENT_ACCEPTANCE_R2.md",
    "docs/PHASE8A_INDEPENDENT_ACCEPTANCE_R3.md",
    "docs/PHASE8A_NFR06_FIX.md",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/audit_readonly.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/audit_transition_keys.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/baseline_api_review.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/baseline_nfr.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/curated_staging_manifest.txt",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/evidence_validation.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/historical_validation_corrected.json",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/probe_delta.diff",
    "docs/PHASE8A_TESTS/independent_r2_20261115_01/process_evidence.json",
    "docs/PHASE8A_TESTS/independent_r3_20261115_01/inheritance_validation.json",
    "docs/PHASE8A_TESTS/independent_r3_20261115_01/requirements_original.json",
    "docs/PHASE8A_TESTS/independent_r3_20261115_01/source_review.json",
    "docs/PHASE8A_TESTS/independent_r3_20261115_01/sql_readonly_review.json",
    "docs/TEST_ENVIRONMENT.json",
    "requirements.lock.txt",
    "tools/dev.ps1",
))
APPROVED_TOOLING = frozenset((
    'tools/run_phase8b.py', 'tools/validate_phase8b_b1b.py',
    'tests/test_phase8b_tooling.py', 'docs/PC_B1B_TEST_EXECUTION_PROTOCOL.md',
    'tools/provision_database.py', 'tests/test_provision_database.py',
    'docs/PC_REFERENCE_0002_COMPATIBILITY.md',
))
INCIDENTAL_EVIDENCE = 'docs/PHASE8A_NFR06_AUDIT_COVERAGE.json'


def classify_bytes(path, data, expected, approved=(), frozen=(), eol_allowlist=EOL_ALLOWLIST):
    digest = hashlib.sha256(data).hexdigest().upper()
    if digest == expected.upper():
        return 'RAW_MATCH'
    if path in frozen:
        return 'UNEXPECTED_CONTENT_DELTA'
    # Reject malformed/mixed line endings even in a reviewed content-delta path.
    remainder = data.replace(b'\r\n', b'')
    if b'\r' in remainder or (b'\r\n' in data and b'\n' in remainder):
        return 'UNEXPECTED_CONTENT_DELTA'
    if path in eol_allowlist:
        try:
            data.decode('utf-8')  # Preserve BOM bytes; never strip/parse/reformat.
        except UnicodeDecodeError:
            return 'UNEXPECTED_CONTENT_DELTA'
        lf = data.replace(b'\r\n', b'\n')
        candidates = (lf, lf.replace(b'\n', b'\r\n'))
        if any(hashlib.sha256(c).hexdigest().upper() == expected.upper() for c in candidates):
            return 'HISTORICAL_EOL_EQUIVALENT'
    return 'APPROVED_CONTENT_DELTA' if path in approved else 'UNEXPECTED_CONTENT_DELTA'


def source_classification(baseline, allowed, frozen, root=ROOT):
    result = {}
    for path, expected in baseline.items():
        file = root/path
        result[path] = (classify_bytes(path, file.read_bytes(), expected, allowed, frozen)
                        if file.is_file() else 'UNEXPECTED_CONTENT_DELTA')
    return result


def main(output, labels):
    from app.main import create_app
    from app.api import no_delivery_schemas as dto
    from jsonschema import Draft202012Validator, FormatChecker
    from openapi_spec_validator import validate_spec
    import yaml
    approved = read(ROOT/'docs/PHASE8B_HANDOFF/b1b_preimplementation_20261118_01/FILE_CHANGE_PROPOSAL.json')
    allowed = {r['path'] for r in approved['paths']}
    baseline = read(ROOT/'docs/PHASE8B_HANDOFF/b1b_transfer_20261119/source_baseline.json')['source_and_environment_hashes']
    allowed.update(APPROVED_TOOLING)
    normative = {v['path'] for v in read(ROOT/'docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json')['files']
                 if v['path'] != 'docs/IMPLEMENTATION_STATUS.md'}
    classified = source_classification(baseline, allowed, normative)
    assert 'UNEXPECTED_CONTENT_DELTA' not in classified.values(), 'UNEXPECTED_SOURCE_DELTA'
    changed = [p for p, status in classified.items() if status == 'APPROVED_CONTENT_DELTA']
    status = subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'], cwd=ROOT, text=True)
    assert all(line[3:] in allowed | {INCIDENTAL_EVIDENCE} for line in status.splitlines()), 'OUT_OF_SCOPE_GIT_DELTA'
    assert 'docs/PHASE5_TEST_ENVIRONMENT.json' not in changed
    assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).strip()
    freeze = read(ROOT/'docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json')['files']
    frozen = [v for v in freeze if v['path'] != 'docs/IMPLEMENTATION_STATUS.md']
    assert all(sha(ROOT/v['path']) == v['sha256'].upper() for v in frozen)
    historical = read(ROOT/'docs/implementation-contracts/P8-REF-0.1/source_baseline.json')
    assert all(sha(ROOT/p) == h.upper() for p, h in historical['prior_overlays'].items())
    spec = create_app().openapi(); validate_spec(spec)
    source = yaml.safe_load((ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml').read_text(encoding='utf-8-sig'))
    for path in ('/v1/payments/{payment_id}/refund', '/v1/refunds/{refund_id}/reconcile', '/v1/payment-events'):
        assert spec['paths'][path] == source['paths'][path]
    assert not any(p.startswith('/mock/') for p in spec['paths'])
    loader = importlib.util.spec_from_file_location('b0_examples', ROOT/'docs/implementation-contracts/P8-REF-0.1/validate_static.py')
    examples = importlib.util.module_from_spec(loader); loader.loader.exec_module(examples)
    bundle = read(ROOT/'docs/implementation-contracts/P8-REC-0.3/contract.schema.json')
    for name, schema in bundle['$defs'].items():
        value = getattr(dto, 'P8ND'+name).model_validate(examples.example(schema, bundle['$defs']))
        Draft202012Validator({'$defs': bundle['$defs'], '$ref': '#/$defs/'+name},
            format_checker=FormatChecker()).validate(value.model_dump(mode='json', exclude_unset=True))
    security = []
    for path in sorted(allowed):
        p = ROOT/path
        if not p.exists() or p.suffix not in ('.py', '.md'): continue
        data = p.read_text(encoding='utf-8-sig')
        for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                        r'gh[pousr]_[A-Za-z0-9]{30,}',
                        r'postgres(?:ql)?://[^\s:/]+:[^\s@/]+@'):
            if re.search(pattern, data): security.append(path)
    assert not security, 'HIGH_CONFIDENCE_SECRET_PATTERN'
    audited = []; total = Counter()
    if labels:
        from sqlalchemy import create_engine, text
        for label in labels:
            assert re.fullmatch(r'[A-Za-z0-9_]+', label)
            root = ROOT/'docs/PHASE8B_TESTS'/label
            assert read(root/'exit.json')['exit_code'] == 0
            metadata = read(root/'real_process.json'); schema = metadata['schema']
            assert re.fullmatch(r'phase5_test_[a-f0-9]+', schema)
            engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True,
                connect_args={'options': '-cdefault_transaction_read_only=on -csearch_path='+schema+',public'})
            try:
                with engine.connect() as c:
                    events = [dict(r) for r in c.execute(text('select * from audit_events order by created_at,id')).mappings()]
                counts = audit_check(events); total.update(counts)
                audited.append({'label': label, 'schema': schema, 'actions': dict(counts)})
            finally: engine.dispose()
        assert set(total) == AUDIT_ACTIONS, 'AUDIT_COVERAGE_INCOMPLETE'
    result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': 0,
        'mode': 'static and read-only fixture audit' if labels else 'static only; audit NOT RUN',
        'approved_paths': len(allowed), 'intended_tracked_delta': changed,
        'source_classification': classified,
        'source_classification_counts': dict(Counter(classified.values())),
        'raw_integrity_note': 'EOL equivalence is not raw-byte equality; historical digests unchanged',
        'local_environment': 'excluded from portable source baseline; preserve separately', 'frozen_unchanged': len(frozen),
        'freeze_status_document': 'intended approved implementation checkpoint delta; not normative change',
        'prior_overlays_unchanged': len(historical['prior_overlays']), 'runtime_definitions': len(bundle['$defs']),
        'openapi_valid': True, 'high_confidence_secret_findings': security,
        'audit_fixtures': audited, 'audit_action_counts': dict(total),
        'candidate_hashes': [{'path': p, 'sha256': sha(ROOT/p)} for p in sorted(allowed) if (ROOT/p).exists()]}
    with Path(output).open('x', encoding='utf8') as target: json.dump(result, target, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('candidate_hashes', 'intended_tracked_delta')}, indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
