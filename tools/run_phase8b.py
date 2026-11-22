"""Supervised B1b execution. No implicit compatibility provisioning or evidence reuse."""
import argparse
import builtins
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import threading
from uuid import uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'services/backend'), str(ROOT)]
from app.config import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXCLUDED = {
    'tests/test_provision_database.py': 'Separate approved compatibility launcher/UUID evidence protocol',
    'tests/test_phase8b_tooling.py': 'Synthetic harness tests; separate tooling profile',
}
EXTRA_SOURCE = tuple(EXCLUDED) + ('docs/PC_REFERENCE_0002_COMPATIBILITY.md',
                                'docs/PC_B1B_TEST_EXECUTION_PROTOCOL.md',
                                'tests/test_phase8b_fixture_isolation.py')
FIXTURE_SOURCE_SCOPE = frozenset(('tests/conftest.py', 'tests/test_phase4.py',
                                'tests/test_phase8b_fixture_isolation.py'))
FIXTURE_REGRESSION_TARGETS = (
    'tests/test_phase8b_fixture_isolation.py::test_committed_ingress_does_not_leak_to_session_schema',
    'tests/test_phase8b_fixture_isolation.py::test_pending_snapshot_still_requires_quiescence',
)
FIX_VERIFY_TARGETS = (
    'tests/test_phase4.py::test_CT11_concurrent_duplicate_event_once',
    'tests/test_phase8b_b1b_certificate.py::test_backend_certificate_is_bound_fresh_atomic_and_does_not_settle_old_pin',
    'tests/test_phase8b_b1b_certificate.py::test_rejected_customer_proof_cannot_issue_certificate',
    'tests/test_phase8b_b1b_certificate.py::test_revoked_witness_session_is_not_replaced_by_sibling_caller_session',
    'tests/test_phase8b_b1b_certificate.py::test_no_delivery_preserves_old_obligation_already_settled_by_legacy_proof',
    'tests/test_phase8b_b1b_no_delivery.py::test_current_three_source_transport_and_replay_do_not_change_protected_facts',
    'tests/test_phase8b_b1b_no_delivery.py::test_issuer_packet_tampering_cannot_create_or_rehabilitate_proof',
    'tests/test_phase8b_b1b_no_delivery.py::test_human_context_ownership_append_only_and_conflicting_replay',
    'tests/test_phase8b_b1b_no_delivery.py::test_human_audit_failure_rolls_back_proof_version_and_success_replay',
    'tests/test_phase8b_b1b_no_delivery.py::test_terminal_metadata_alone_does_not_release_backend_station_fence[consumed_at]',
    'tests/test_phase8b_b1b_no_delivery.py::test_terminal_metadata_alone_does_not_release_backend_station_fence[cancelled_at]',
    'tests/test_phase8b_b1b_races.py::test_accepted_uncertainty_after_certificate_blocks_first_intent',
    'tests/test_phase8b_b1b_refund.py::test_first_intent_rollback_replay_and_no_provider_dispatch',
    'tests/test_phase8b_b1b_refund.py::test_new_boot_revokes_certificate_without_refund_or_protected_mutation',
    *FIXTURE_REGRESSION_TARGETS,
)
STATES = ('RUNNING', 'COMPLETED', 'INTERRUPTED', 'UNKNOWN')
DB_ROLES = {'DATABASE_ADMIN_URL': 'postgres', 'MIGRATION_DATABASE_URL': 'doi_pin_migrator',
            'DATABASE_URL': 'doi_pin_runtime'}
ISOLATED_ENDPOINT = ('127.0.0.1', 5435, 'doi_pin_r2_rerun')
DERIVATION_SECRET = 'DEVICE_KEY_DERIVATION_SECRET'
TEST_SCHEMA = re.compile(r'(?:phase5_test_[a-f0-9]{12}|b1b_upgrade_[a-f0-9]{12}|b1b_bootstrap_[a-f0-9]{32})')
OS_ENV = ('SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE',
          'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'COMSPEC')
MIGRATION_TARGETS = ['tests/test_phase8b_b1b_migration.py::'+n for n in (
    'test_new_head_grants_constraints_and_no_backfill',
    *(f'test_operation_protocol_scope_binding_is_enforced[changes{i}]' for i in range(7)),
    'test_storage_accepts_readonly_context_but_no_cross_stage_proof',
    'test_0009_upgrade_preserves_marker_and_old_grants')]
ROUND3_TARGETS = (
    'tests/test_phase8b_b1b_no_delivery.py::test_current_three_source_transport_and_replay_do_not_change_protected_facts',
    'tests/test_phase8b_b1b_no_delivery.py::test_wrong_boot_receipt_refusal_is_durable_and_has_no_case_audit_write',
    'tests/test_phase8b_b1b_no_delivery.py::test_issuer_packet_tampering_cannot_create_or_rehabilitate_proof',
    'tests/test_phase8b_b1b_no_delivery.py::test_human_context_ownership_append_only_and_conflicting_replay',
    'tests/test_phase8b_b1b_no_delivery.py::test_human_audit_failure_rolls_back_proof_version_and_success_replay',
    'tests/test_phase8b_b1b_certificate.py::test_backend_certificate_is_bound_fresh_atomic_and_does_not_settle_old_pin',
    'tests/test_phase8b_b1b_certificate.py::test_rejected_customer_proof_cannot_issue_certificate',
    'tests/test_phase8b_b1b_certificate.py::test_revoked_witness_session_is_not_replaced_by_sibling_caller_session',
    'tests/test_phase8b_b1b_refund.py::test_first_intent_rollback_replay_and_no_provider_dispatch',
    'tests/test_phase8b_b1b_refund.py::test_new_boot_revokes_certificate_without_refund_or_protected_mutation',
    'tests/test_phase8b_b1b_contract.py::test_api_no_delivery_begin_preserves_technician_authority[admin]',
    'tests/test_phase8b_b1b_contract.py::test_api_no_delivery_begin_preserves_technician_authority[customer]',
    'tests/test_phase8b_b1b_contract.py::test_api_no_delivery_device_auth_and_closed_input',
)


ROUND4_TARGETS = (
    'tests/test_phase8b_b1b_races.py::test_accepted_uncertainty_after_certificate_blocks_first_intent',
    'tests/test_phase8b_b1b_races.py::test_native_session_expiry_after_observed_station_wait_has_no_certificate[caller]',
    'tests/test_phase8b_b1b_races.py::test_native_session_expiry_after_observed_station_wait_has_no_certificate[customer_witness]',
    'tests/test_phase8b_b1b_no_delivery.py::test_terminal_metadata_alone_does_not_release_backend_station_fence[consumed_at]',
    'tests/test_phase8b_b1b_no_delivery.py::test_terminal_metadata_alone_does_not_release_backend_station_fence[cancelled_at]',
    'tests/test_phase8b_b1b_ledger.py::test_receipt_replay_after_boot_never_renews_current_proof',
    'tests/test_phase8b_b1b_ledger.py::test_inspection_sequence_is_after_current_device_source_high_watermark',
    'tests/test_phase8b_b1b_ledger.py::test_receipt_waits_for_trailing_source_and_never_rehabilitates_refusal[202]',
    'tests/test_phase8b_b1b_ledger.py::test_receipt_waits_for_trailing_source_and_never_rehabilitates_refusal[409]',
    'tests/test_phase8b_b1b_ledger.py::test_inspection_refreshes_durable_queued_source_disposition_without_recapture[False]',
    'tests/test_phase8b_b1b_ledger.py::test_inspection_refreshes_durable_queued_source_disposition_without_recapture[True]',
    'tests/test_phase8b_b1b_ledger.py::test_actual_service_crash_is_not_no_effect_after_reboot',
    'tests/test_phase8b_b1b_ledger.py::test_delivered_then_returned_serial_is_not_certified_from_present_slot',
    'tests/test_phase8b_b1b_certificate.py::test_no_delivery_preserves_old_obligation_already_settled_by_legacy_proof',
)


ROUND5_TARGETS = tuple('tests/test_phase8b_b1b_contract.py::'+name for name in (
    *(f'test_all_frozen_definitions_round_trip[{name}]' for name in (
        'StageReference', 'InspectionTask', 'CommandEntry', 'ServiceEntry', 'Quiescence',
        'DeliveryHistory', 'TechnicianAttestation', 'DecideRequest', 'CustomerProjection',
        'ProofView', 'NoDeliveryResponse', 'TaskList')),
    *(f'test_inputs_cannot_select_authority_or_financial_state[{field}-{value}-{name}]'
      for field, value in (('actor_id', 'client'), ('custody', 'CUSTOMER'),
                           ('amount_minor', '1'), ('new_pin_delivered', 'NO'))
      for name in ('BeginRequest', 'TechnicianAttestation', 'DecideRequest', 'CustomerConfirmation', 'Observation')),
    *(f'test_case_version_is_strict_positive_integer[{value}]' for value in ('True', '1.0', '1', '0')),
    *(f'test_bool_and_numeric_literals_do_not_coerce[{value}]' for value in (
        'InspectionTask-effect_allowed-0', 'Observation-read_only-1',
        'Observation-effect_count_delta-False', 'CustomerConfirmation-confirm-1')),
))


def validate_pure_selection(config):
    if (config.get('execution_profile') != 'round5' or config['profile'] != 'business' or
        config['collect_only'] or config.get('isolation') or config['targets'] != list(ROUND5_TARGETS)):
        raise ValueError('Exact pure Round 5 contract selection required')


def pure_environment(system_env=None):
    env = {k: v for k, v in (os.environ if system_env is None else system_env).items() if k.upper() in OS_ENV}
    env.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
               PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(ROOT/'services/backend'))
    return env


class PureContracts:
    """Reviewed pure DTO cases: no credentials, DB, SQLite, native child or HTTP."""
    def __init__(self, out):
        self.out, self.failed, self.refusals = Path(out), False, 0

    def refuse(self, *args, **kwargs):
        self.failed = True
        self.refusals += 1
        write_new(self.out/f'pure_refused_{self.refusals:04}.json', dict(refused=True,
                  reason='Database/SQLite/process/provider operation forbidden in pure contract profile'))
        raise ValueError('Effect forbidden in pure contract profile')

    @contextlib.contextmanager
    def install(self):
        async def async_refuse(*args, **kwargs):
            return self.refuse()
        with contextlib.ExitStack() as stack:
            for target in ('psycopg.connect', 'sqlalchemy.create_engine', 'sqlite3.connect',
                           'subprocess.Popen', 'subprocess.run', 'httpx.HTTPTransport.handle_request',
                           'app.workers.payment.provider_request'):
                stack.enter_context(patch(target, self.refuse))
            stack.enter_context(patch('httpx.AsyncHTTPTransport.handle_async_request', async_refuse))
            yield


def isolation_endpoint(identity):
    """Round 2 remains pinned; Round 3 derives a new endpoint from its identity."""
    profile = identity.get('execution_profile', 'round2')
    endpoint = (identity['host'], identity['port'], identity['database'])
    if profile == 'round2' and endpoint == ISOLATED_ENDPOINT:
        return endpoint
    if (profile == 'round3' and endpoint[0] == '127.0.0.1' and
        type(endpoint[1]) is int and 1024 <= endpoint[1] <= 65535 and endpoint[1] not in (5433, 5434, 5435) and
        isinstance(endpoint[2], str) and
        re.fullmatch(r'doi_pin_b1b_r3_[a-f0-9]{12}', endpoint[2])):
        return endpoint
    if (profile == 'round4' and endpoint[0] == '127.0.0.1' and
        type(endpoint[1]) is int and 1024 <= endpoint[1] <= 65535 and endpoint[1] not in (5433, 5434, 5435, 5436) and
        isinstance(endpoint[2], str) and re.fullmatch(r'doi_pin_b1b_r4_[a-f0-9]{12}', endpoint[2])):
        return endpoint
    if (profile == 'full' and endpoint[0] == '127.0.0.1' and type(endpoint[1]) is int and
        1024 <= endpoint[1] <= 65535 and endpoint[1] not in range(5433, 5439) and
        endpoint[1] not in {x['port'] for x in identity.get('retained_instances', [])} and
        isinstance(endpoint[2], str) and re.fullmatch(r'doi_pin_full_[a-f0-9]{12}', endpoint[2])):
        return endpoint
    raise ValueError('Isolated endpoint required')


def canonical_node(node):
    # Only these two IDs are UUID4 values created at module import in the source.
    return re.sub(r'^(tests/test_phase8a_contract.py::test_client_cannot_select_settlement_result\[(?:holder_user_id|actor_id)-)[a-f0-9-]{36}(\])$',
                  r'\1<import-uuid4>\2', node)


def full_inventory(identity):
    path = Path(identity['collection_file']).resolve()
    if path.parent != Path(identity['env_file']).resolve().parent:
        raise ValueError('Collection must belong to isolated instance')
    return json.loads(path.read_text())['node_ids']


def reconcile_collection(nodes, expected):
    actual, saved = [canonical_node(n) for n in nodes], [canonical_node(n) for n in expected]
    if len(nodes) != len(expected) or len(actual) != len(set(actual)) or set(actual) != set(saved):
        raise ValueError('Business collection identity mismatch')
    return dict(count=len(nodes), exact_differences=sorted(set(nodes)^set(expected)),
                normalization='Only two source import-time UUID4 parameter values; no other identity normalization')


def schema_allowed(schema, identity):
    return bool(TEST_SCHEMA.fullmatch(schema) or (identity.get('execution_profile') == 'full' and
                re.fullmatch(r'b1a_(?:upgrade|clean)_[a-f0-9]{12}', schema)))


def denied_cluster_ids(identity):
    return {identity['original_system_identifier'], identity.get('previous_system_identifier')} | {
            x['system_identifier'] for x in identity.get('retained_instances', [])}


def validate_isolated_selection(config, identity):
    profile = config.get('execution_profile', 'round2')
    approved = {'round2': MIGRATION_TARGETS, 'round3': list(ROUND3_TARGETS), 'round4': list(ROUND4_TARGETS)}
    if profile == 'full':
        expected = full_inventory(identity)
        kind = identity.get('selection_kind', 'full')
        targets = list(FIX_VERIFY_TARGETS) if kind == 'fixture_interaction' else sorted({n.split('::')[0] for n in expected})
        if (kind not in ('full', 'fixture_interaction') or
            (kind == 'fixture_interaction' and expected != list(FIX_VERIFY_TARGETS)) or
            config['profile'] != 'business' or config['targets'] != targets or identity.get('execution_profile') != 'full'):
            raise ValueError('Exact full business modules required')
        isolation_endpoint(identity)
        return
    if (profile not in approved or config['profile'] != 'business' or config['collect_only'] or
        config['targets'] != approved[profile] or identity.get('execution_profile', 'round2') != profile):
        raise ValueError('Exact approved isolated execution profile required')
    isolation_endpoint(identity)


def isolated_environment(values, identity, system_env=None):
    """No inherited DB/PG/config values and no dotenv fallback in any child."""
    endpoint = isolation_endpoint(identity)
    env = {k: v for k, v in (os.environ if system_env is None else system_env).items()
           if k.upper() in OS_ENV}
    for key, role in DB_ROLES.items():
        try:
            u = make_url(values[key])
            okay = (u.drivername, u.host, u.port, u.database, u.username) == (
                'postgresql+psycopg', *endpoint, role)
            okay = okay and not u.query and u.password and len(u.password) >= 24
        except Exception:
            okay = False
        if not okay:
            raise ValueError('Missing or invalid isolated credentials')
        env[key] = values[key]
    for key, url_key in (('POSTGRES_PASSWORD', 'DATABASE_ADMIN_URL'),
                         ('MIGRATOR_PASSWORD', 'MIGRATION_DATABASE_URL'),
                         ('RUNTIME_PASSWORD', 'DATABASE_URL')):
        if not values.get(key) or values[key] != make_url(env[url_key]).password:
            raise ValueError('Isolated password mismatch')
        env[key] = values[key]
    if len({env[k] for k in ('POSTGRES_PASSWORD', 'MIGRATOR_PASSWORD', 'RUNTIME_PASSWORD')}) != 3:
        raise ValueError('Independent role credentials required')
    secret = values.get(DERIVATION_SECRET)
    # Match qr_token's contract; never refill from the parent/default .env.
    if not isinstance(secret, str) or len(secret) < 32 or secret.startswith('REPLACE_'):
        raise ValueError('Missing or invalid test-only derivation secret')
    env[DERIVATION_SECRET] = secret
    schema = values.get('DATABASE_SCHEMA', '')
    if not schema_allowed(schema, identity):
        raise ValueError('Fresh test schema required')
    env.update(DATABASE_SCHEMA=schema, PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(ROOT/'services/backend'), PGCONNECT_TIMEOUT='5',
               PGOPTIONS='-cstatement_timeout=15000 -clock_timeout=5000')
    if identity.get('execution_profile') == 'full':
        for key in ('PAYMENT_SERVICE_KEY', 'PAYMENT_CALLBACK_KEY'):
            if not values.get(key) or len(values[key]) < 32 or values[key].startswith('REPLACE_'):
                raise ValueError('Full regression requires explicit test payment keys')
            env[key] = values[key]
        env['PAYMENT_MOCK_URL'] = 'http://127.0.0.1:'+str(identity['mock_port'])
        env['PAYMENT_LEDGER_PATH'] = str(Path(identity['env_file']).parent/'runtime/payment.sqlite3')
        env['PYTHONNOUSERSITE'] = '1'
        env['PYTHONPATH'] = os.pathsep.join([str(ROOT/'.venv/Lib/site-packages'),str(ROOT/'services/backend'),str(ROOT)])
    return env


def load_isolation(path):
    from dotenv import dotenv_values
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT/'.local/pc-b1b'):
        raise ValueError('Local ignored isolation identity required')
    identity = json.loads(path.read_text(encoding='utf-8'))
    isolation_endpoint(identity)
    if identity.get('execution_profile') == 'round3':
        retained = identity.get('retained_instances', [])
        if len(retained) != 3 or {x['port'] for x in retained} != {5433, 5434, 5435}:
            raise ValueError('All three preserved cluster identities required')
    if identity.get('execution_profile') == 'round4':
        retained = identity.get('retained_instances', [])
        if len(retained) != 4 or {x['port'] for x in retained} != {5433, 5434, 5435, 5436}:
            raise ValueError('All four preserved cluster identities required')
    if identity.get('execution_profile') == 'full':
        retained = identity.get('retained_instances', [])
        ports = {x['port'] for x in retained}
        if len(ports) != len(retained) or not set(range(5433,5439)).issubset(ports):
            raise ValueError('All six preserved cluster identities required, without duplicate ports')
    private = Path(identity['env_file']).resolve()
    if private.parent != path.parent:
        raise ValueError('Private environment must belong to isolation instance')
    if identity['system_identifier'] in denied_cluster_ids(identity):
        raise ValueError('Protected cluster refused')
    denied_containers = {identity['original_container_id'], identity['previous_container_id']} | {
        x['container_id'] for x in identity.get('retained_instances', [])}
    if identity['container_id'] in denied_containers:
        raise ValueError('Protected container refused')
    values = dotenv_values(private, interpolate=False)
    return identity, isolated_environment(values, identity)


def isolated_catalog(identity, env, pristine=False, require_quiescence=True):
    """Quiescent read-only inventory; each schema has its own finite transaction.

    Namespace/identity checks bracket every batch. This is not an atomic global
    snapshot; callers must first wait for their owned test processes to exit.
    """
    import psycopg
    from psycopg import sql
    u = make_url(env['DATABASE_ADMIN_URL'])
    with psycopg.connect(host=u.host, port=u.port, dbname=u.database, user=u.username,
                        password=u.password, connect_timeout=5, autocommit=True,
                        options='-cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000') as c:
        def boundary():
            system = c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]
            if system != identity['system_identifier'] or system in denied_cluster_ids(identity):
                raise ValueError('Isolated cluster identity mismatch')
            clients = c.execute("SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchall()
            if require_quiescence and clients:
                raise ValueError('Isolated database is not quiescent')
            return c.execute("SELECT oid,nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('information_schema','public') ORDER BY nspname").fetchall()
        schemas = boundary()
        if pristine and schemas:
            raise ValueError('Fresh isolated cluster required; retained schemas cannot be reused')
        inventory = []
        for oid, schema, owner, acl in schemas:
            if not schema_allowed(schema, identity) or owner != 'doi_pin_migrator':
                raise ValueError('Unexpected isolated schema or owner')
            if boundary() != schemas:
                raise ValueError('Schema inventory drift during catalog scan')
            with c.transaction():
                c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                tables = c.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY 1', (schema,)).fetchall()
                data = {t: c.execute(sql.SQL("SELECT count(*),md5(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) FROM {} t").format(sql.Identifier(schema, t))).fetchone()
                        for t, in tables}
                revision = (c.execute(sql.SQL('SELECT version_num FROM {}.alembic_version').format(sql.Identifier(schema))).fetchall()
                            if 'alembic_version' in data else [])
                objects = c.execute('SELECT relname,relkind,pg_get_userbyid(relowner),relacl::text FROM pg_class WHERE relnamespace=%s ORDER BY 1,2', (oid,)).fetchall()
                columns = c.execute('SELECT c.relname,a.attname,a.atttypid::regtype::text,a.attacl::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid WHERE c.relnamespace=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2', (oid,)).fetchall()
                constraints = c.execute('SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace=%s ORDER BY 1', (oid,)).fetchall()
                triggers = c.execute('SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE c.relnamespace=%s AND NOT t.tgisinternal ORDER BY 1,2', (oid,)).fetchall()
                functions = c.execute('SELECT proname,pg_get_function_identity_arguments(oid),pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace=%s ORDER BY 1,2', (oid,)).fetchall()
                inventory.append(dict(schema=schema, owner=owner, acl=acl, revision=[r[0] for r in revision],
                    state='MIGRATED' if revision else 'PARTIAL', table_rows={t:v[0] for t,v in data.items()},
                    table_digests={t:v[1] for t,v in data.items()}, objects=objects, columns=columns,
                    constraints=constraints, triggers=triggers, functions=functions))
            # Autocommit boundary observes fresh activity/namespace state after
            # the per-schema transaction releases all of its relation locks.
        if boundary() != schemas:
            raise ValueError('Schema inventory drift after catalog scan')
        return dict(system_identifier=identity['system_identifier'], schemas=inventory,
                    namespace_inventory=schemas, quiescence_verified=require_quiescence,
                    snapshot_mode='Per-schema read-only repeatable-read transactions; not a global atomic snapshot')


def verify_container(identity):
    """Supervisor only. Never expose docker inspect's environment/passwords."""
    container = json.loads(subprocess.check_output(['docker', 'inspect', identity['container']],
                           cwd=ROOT, text=True, encoding='utf-8', timeout=30))[0]
    mounts = container['Mounts']
    endpoint = isolation_endpoint(identity)
    retained = identity.get('retained_instances', [])
    denied_containers = {identity['original_container_id'], identity['previous_container_id']} | {x['container_id'] for x in retained}
    denied_mounts = identity['original_mounts'] + identity['previous_mounts'] + [m for x in retained for m in x['mounts']]
    denied_networks = {n for x in retained for n in x['network_ids']}
    if (container['Id'] != identity['container_id'] or
        container['Id'] in denied_containers or
        container['State']['Health']['Status'] != 'healthy' or len(mounts) != 1 or
        mounts[0]['Type'] != 'volume' or mounts[0]['Name'] != identity['volume'] or
        mounts[0]['Source'] != identity['mount_source'] or
        any(mounts[0]['Source'] == m['source'] for m in denied_mounts) or
        container['NetworkSettings']['Ports']['5432/tcp'] != [{'HostIp': endpoint[0], 'HostPort': str(endpoint[1])}] or
        set(container['NetworkSettings']['Networks']) != {identity['network']} or
        container['NetworkSettings']['Networks'][identity['network']]['NetworkID'] != identity['network_id'] or
        identity['network_id'] in denied_networks):
        raise ValueError('Physical isolation mismatch')


class MigrationProcesses:
    """Exact fixture adapter, not an OS sandbox. Cluster separation is mandatory."""
    def __init__(self, out, identity, env, launch=None, catalog=None):
        self.out, self.identity, self.env = Path(out), identity, env
        self.launch = launch or subprocess.Popen
        # Fixture-time metadata reads may coexist with its owned idle pools;
        # mandatory supervisor pre/post checks always require quiescence.
        self.catalog = catalog or (lambda ident, values: isolated_catalog(ident, values, require_quiescence=False))
        self.folder = self.out/'subprocesses'
        self.folder.mkdir(exist_ok=False)
        self.number, self.claimed, self.failed = 0, set(), False

    def run(self, args, **kwargs):
        self.number += 1
        record = self.folder/f'{self.number:04}.json'
        result = dict(state='REFUSED', exit_code=None, timed_out=False)
        try:
            if (not isinstance(args, list) or len(args) != 3 or
                args[:2] != [sys.executable, str(ROOT/'tools/provision_database.py')] or
                args[2] not in ('roles', 'grants') or kwargs != {'check': True} or
                Path.cwd().resolve() != ROOT):
                raise ValueError('Unexpected fixture subprocess')
            current = isolated_environment(dict(os.environ), self.identity)
            if any(current[k] != self.env[k] for k in (*DB_ROLES, 'POSTGRES_PASSWORD', 'MIGRATOR_PASSWORD', 'RUNTIME_PASSWORD', DERIVATION_SECRET)):
                raise ValueError('Fixture credentials changed')
            schema = current['DATABASE_SCHEMA']
            existing = {s['schema'] for s in self.catalog(self.identity, current)['schemas']}
            if args[2] == 'roles':
                if schema in existing or schema in self.claimed:
                    raise ValueError('Existing schema cannot be claimed')
                self.claimed.add(schema)
            elif schema not in self.claimed or schema not in existing:
                raise ValueError('Schema not created by this run')
            for key in ('TEMP', 'TMP', 'B1B_REPORT_DIR'):
                current[key] = str(self.out/'tmp') if key != 'B1B_REPORT_DIR' else str(self.out)
            # Provisioning only needs database credentials; QR runs in the worker.
            current.pop(DERIVATION_SECRET)
            result.update(state='STARTING', command=args, cwd=str(ROOT), schema=schema,
                          cluster=self.identity['system_identifier'], timeout_seconds=60)
            write_new(self.folder/f'{self.number:04}_start.json', result)
            with (self.folder/f'{self.number:04}_stdout.log').open('xb') as stdout, \
                 (self.folder/f'{self.number:04}_stderr.log').open('xb') as stderr:
                child = self.launch(args, cwd=ROOT, env=current, shell=False, stdout=stdout, stderr=stderr)
                result['pid'] = child.pid
                try:
                    code = child.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    result['timed_out'] = True
                    child.terminate()
                    try:
                        code = child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        code = child.wait(timeout=5)
                    result.update(state='TIMEOUT', exit_code=code)
                    raise subprocess.TimeoutExpired(args, 60) from None
            result.update(state='COMPLETED', exit_code=code)
            if code:
                raise subprocess.CalledProcessError(code, args)
            return subprocess.CompletedProcess(args, code)
        except BaseException as error:
            self.failed = True
            result['error_type'] = type(error).__name__
            raise
        finally:
            write_new(record, result)

    @contextlib.contextmanager
    def install(self):
        import psycopg
        connect = psycopg.connect
        endpoint = isolation_endpoint(self.identity)
        def guarded_connect(*args, **kwargs):
            role = kwargs.get('user')
            key = next((k for k, r in DB_ROLES.items() if r == role), None)
            if (args or key is None or kwargs.get('host') != endpoint[0] or
                str(kwargs.get('port')) != str(endpoint[1]) or kwargs.get('dbname') != endpoint[2] or
                kwargs.get('password') != make_url(self.env[key]).password or
                set(kwargs) - {'host', 'port', 'dbname', 'user', 'password', 'options', 'connect_timeout', 'context', 'autocommit'}):
                self.failed = True
                raise ValueError('Non-isolated database connection refused')
            return connect(**kwargs)
        def forbidden(*args, **kwargs):
            self.failed = True
            raise ValueError('Unsupervised subprocess refused')
        with patch('subprocess.run', self.run), patch('subprocess.Popen', forbidden), \
             patch('psycopg.connect', guarded_connect):
            yield

    @contextlib.contextmanager
    def local_transports(self):
        """Round 3 permits MockTransport/TestClient and explicit pure charge callbacks."""
        number = 0
        def forbidden(*args, **kwargs):
            nonlocal number
            number += 1
            self.failed = True
            write_new(self.out/f'network_refused_{number:04}.json', dict(refused=True,
                      reason='External HTTP/provider transport not approved'))
            raise ValueError('External HTTP/provider transport refused')
        async def async_forbidden(*args, **kwargs):
            return forbidden()
        with patch('httpx.HTTPTransport.handle_request', forbidden), \
             patch('httpx.AsyncHTTPTransport.handle_async_request', async_forbidden), \
             patch('app.workers.payment.provider_request', forbidden):
            yield


class FullOutputGuard:
    """Routes reviewed legacy cache paths without touching an old cache directory."""
    def __init__(self, out):
        self.out = Path(out).resolve()
        self.routes = {}

    def path(self, value):
        p = Path(value).resolve()
        cache = ROOT/'.cache'
        if p.is_relative_to(cache):
            name = p.relative_to(cache).parts[0]
            if not re.fullmatch(r'(?:p6-(?:ledger|provider|key-test|callback|callback-url)-[a-f0-9]{32}|phase5-two-api-[a-f0-9]{8})', name):
                raise ValueError('Unreviewed legacy cache path')
            if name not in self.routes:
                if (cache/name).exists():
                    raise ValueError('Existing cache evidence cannot be claimed')
                self.routes[name] = str(self.out/'legacy-cache'/name)
            return Path(self.routes[name]).joinpath(*p.relative_to(cache/name).parts)
        return p

    @contextlib.contextmanager
    def install(self):
        mkdir, connect = Path.mkdir, __import__('sqlite3').connect
        target = OutputGuard.target
        from simulators.payment.main import Ledger
        init = Ledger.__init__
        def directories(path, *args, **kwargs):
            p = self.path(path)
            if p.is_relative_to(ROOT/'docs'):
                p = self.out/'reports'/p.relative_to(ROOT/'docs')
            return mkdir(p, *args, **kwargs)
        def ledger(obj, path, *args, **kwargs):
            return init(obj, self.path(path), *args, **kwargs)
        def sqlite(path, *args, **kwargs):
            if path == ':memory:':
                return connect(path,*args,**kwargs)
            p = self.path(path)
            if not p.is_relative_to(self.out):
                raise ValueError('SQLite outside this full run refused')
            return connect(p,*args,**kwargs)
        def routed(guard,path):
            return target(guard,self.path(path)) if not isinstance(path,int) else path
        with patch.object(Path,'mkdir',directories), patch.object(Ledger,'__init__',ledger), patch('sqlite3.connect',sqlite),patch.object(OutputGuard,'target',routed):
            yield


class NativeChild:
    def __init__(self, adapter, process, folder, command, expected_failure):
        self.adapter,self.process,self.folder = adapter,process,folder
        self.command,self.expected_failure,self.stopped,self.saved = command,expected_failure,False,False
    def __getattr__(self,name):
        return getattr(self.process,name)
    def finish(self,code):
        if code is not None and not self.saved:
            self.saved = True
            write_new(self.folder/'exit.json',dict(exit_code=code,fixture_terminated=self.stopped,
                expected_nonzero=self.expected_failure,command=self.command,pid=self.pid))
            if code and not (self.expected_failure or self.stopped):self.adapter.failed=True
        return code
    def poll(self):return self.finish(self.process.poll())
    def wait(self,timeout=None):return self.finish(self.process.wait(timeout=timeout))
    def communicate(self,*args,**kwargs):
        result=self.process.communicate(*args,**kwargs);self.finish(self.process.returncode);return result
    def terminate(self):self.stopped=True;return self.process.terminate()
    def kill(self):self.stopped=True;return self.process.kill()


class FullProcesses(MigrationProcesses):
    """Reviewed --once workers and two single-process API servers, test cluster only."""
    def __init__(self,out,identity,env):
        super().__init__(out,identity,env)
        self.native=[];self.native_lock=threading.Lock();self.cache=FullOutputGuard(out)
        self.native_dir=self.out/'native';self.native_dir.mkdir()
        self.http_ports={identity['mock_port']};self.http_count=0
        def catalog(ident,values):
            import psycopg
            u=make_url(values['DATABASE_ADMIN_URL'])
            with psycopg.connect(host=u.host,port=u.port,dbname=u.database,user=u.username,password=u.password,
                connect_timeout=5,options='-cdefault_transaction_read_only=on -cstatement_timeout=15000') as c:
                return dict(schemas=[dict(schema=x[0]) for x in c.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('public','information_schema')")])
        self.catalog=catalog

    def child_environment(self,values):
        current=isolated_environment(values,self.identity)
        if any(current[k]!=self.env[k] for k in (*DB_ROLES,DERIVATION_SECRET)):
            raise ValueError('Native child database/derivation credentials changed')
        if current['DATABASE_SCHEMA'] not in self.claimed:
            raise ValueError('Native child schema not created by this run')
        current.update(TEMP=str(self.out/'tmp'),TMP=str(self.out/'tmp'),PYTHONNOUSERSITE='1',
            PYTHONPATH=os.pathsep.join([str(ROOT/'.venv/Lib/site-packages'),str(ROOT/'services/backend'),str(ROOT)]))
        current['PAYMENT_LEDGER_PATH']=str(self.out/'runtime/provider.sqlite3')
        return current

    def popen(self,args,**kwargs):
        worker=args in ([sys.executable,'-m','app.workers.payment','--once'],[sys.executable,'-m','app.workers.device','--once'])
        api=(isinstance(args,list) and len(args)==11 and args[:8]==[sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port'] and args[8] in ('8005','8006') and args[9:]==['--no-access-log','--no-proxy-headers'])
        if not(worker or api) or Path(kwargs.get('cwd','')).resolve()!=ROOT or set(kwargs)-{'cwd','env','stdout','stderr','creationflags'}:
            self.failed=True;raise ValueError('Unreviewed native process refused')
        env=self.child_environment(kwargs.get('env',{}))
        output=kwargs.get('stdout')
        if output not in (subprocess.PIPE,None) and not Path(output.name).resolve().is_relative_to(self.out):
            self.failed=True;raise ValueError('Native log outside run')
        if api:
            import socket
            with socket.socket() as sock:sock.bind(('127.0.0.1',int(args[8])))
            self.http_ports.add(int(args[8]))
        with self.native_lock:
            folder=self.native_dir/f'{len(self.native)+1:04}';folder.mkdir(exist_ok=False)
            ticket=dict(command=args[1:],schema=env['DATABASE_SCHEMA'],identity_file=self.identity['identity_file'],out=str(self.out))
            write_new(folder/'ticket.json',ticket)
            command=[sys._base_executable,'-B',str(ROOT/'tools/run_phase8b.py'),'--_native',str(folder)]
            process=self.launch(command,cwd=ROOT,env=env,stdout=output,stderr=kwargs.get('stderr'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            node=os.environ.get('PYTEST_CURRENT_TEST','')
            expected='test_persistent_lock_timeout_exhausts_budget_preserving_inbox' in node
            child=NativeChild(self,process,folder,args[1:],expected);self.native.append(child)
            write_new(folder/'start.json',dict(pid=child.pid,command=args[1:],schema=env['DATABASE_SCHEMA'],node=node,actual_executable=sys._base_executable))
            return child

    def run(self,args,**kwargs):
        if isinstance(args,list) and len(args)==3 and args[1]==str(ROOT/'tools/provision_database.py'):
            return super().run(args,**kwargs)
        allowed={'cwd','env','capture_output','text','encoding','errors','timeout','creationflags','check'}
        if set(kwargs)-allowed or not kwargs.get('capture_output'):
            self.failed=True;raise ValueError('Native run options refused')
        child=self.popen(args,cwd=kwargs.get('cwd'),env=kwargs.get('env'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:stdout,stderr=child.communicate(timeout=kwargs.get('timeout',60))
        except subprocess.TimeoutExpired:
            self.failed=True;child.kill();child.wait(timeout=10);raise
        (child.folder/'stdout.log').write_bytes(stdout);(child.folder/'stderr.log').write_bytes(stderr)
        if kwargs.get('text') or kwargs.get('encoding'):
            stdout=stdout.decode(kwargs.get('encoding','utf-8'),kwargs.get('errors','strict'))
            stderr=stderr.decode(kwargs.get('encoding','utf-8'),kwargs.get('errors','strict'))
        result=subprocess.CompletedProcess(args,child.returncode,stdout,stderr)
        if kwargs.get('check'):result.check_returncode()
        return result

    @contextlib.contextmanager
    def install(self):
        import httpx
        original=httpx.HTTPTransport.handle_request
        def http(transport,request):
            port=request.url.port or 80
            if request.url.scheme!='http' or request.url.host!='127.0.0.1' or port not in self.http_ports:
                self.failed=True;raise ValueError('Unowned real HTTP endpoint refused')
            if port==self.identity['mock_port'] and not request.url.path.startswith('/mock/v1/charges'):
                self.failed=True;raise ValueError('Only CHARGE mock routes approved')
            self.http_count+=1
            return original(transport,request)
        with super().install(),self.cache.install(),patch('subprocess.Popen',self.popen),patch('subprocess.run',self.run),patch('httpx.HTTPTransport.handle_request',http):
            yield

    def close(self):
        for child in self.native:
            if child.poll() is None:
                self.failed=True;child.terminate();child.wait(timeout=10)
        if hasattr(self,'server'):
            self.server.should_exit=True;self.server_thread.join(timeout=10)
            if self.server_thread.is_alive():self.failed=True
        write_new(self.out/'full_effect_manifest.json',dict(native_children=len(self.native),real_loopback_HTTP=self.http_count,
            external_provider=0,cache_routes=self.cache.routes,failed=self.failed,
            local_workers_quiescent=all(child.poll() is not None for child in self.native) and
                (not hasattr(self,'server_thread') or not self.server_thread.is_alive())))

    def start_mock(self):
        import socket,uvicorn
        from simulators.payment.main import create_app
        self.server=uvicorn.Server(uvicorn.Config(create_app(self.out/'runtime/provider.sqlite3'),
            host='127.0.0.1',port=self.identity['mock_port'],access_log=False,log_config=None))
        self.server_thread=threading.Thread(target=self.server.run,daemon=True)
        self.server_thread.start();until=time.monotonic()+15
        while not self.server.started:
            if not self.server_thread.is_alive() or time.monotonic()>until:raise RuntimeError('Owned mock failed to start')
            time.sleep(.05)
        write_new(self.out/'local_mock.json',dict(host='127.0.0.1',port=self.identity['mock_port'],
            ledger=str(self.out/'runtime/provider.sqlite3'),scope='CHARGE mock only; no refund dispatcher'))


def native_main(folder):
    import runpy
    folder=Path(folder);ticket=json.loads((folder/'ticket.json').read_text())
    identity,base=load_isolation(ticket['identity_file']);env=isolated_environment(dict(os.environ),identity)
    if any(base[k]!=env[k] for k in (*DB_ROLES,DERIVATION_SECRET)):raise ValueError('Native identity mismatch')
    write_new(folder/'actual_pid.json',dict(pid=os.getpid(),executable=sys.executable))
    guard=object.__new__(MigrationProcesses);guard.out=Path(ticket['out']);guard.identity=identity;guard.env=env;guard.failed=False
    def refuse(*args,**kwargs):raise ValueError('Native descendant refused')
    argv=ticket['command'];module=argv[1];sys.argv=[module,*argv[2:]]
    if module not in ('uvicorn','app.workers.payment','app.workers.device'):raise ValueError('Unreviewed native module')
    with guard.install(),patch('subprocess.Popen',refuse),patch('subprocess.run',refuse),OutputGuard(guard.out).install():
        runpy.run_module(module,run_name='__main__')
    return 0


@contextlib.contextmanager
def observe_422(out):
    """Observe existing responses only; no request replay or assertion changes."""
    import httpx
    send, number, proof_number = httpx.Client.send, 0, 0
    def observed(client, request, *args, **kwargs):
        nonlocal number, proof_number
        response = send(client, request, *args, **kwargs)
        if request.method == 'POST' and request.url.path == '/v1/device/recovery-observations':
            try:
                packet = json.loads(request.content)
                is_proof = isinstance(packet, dict) and packet.get('protocol_version') == '0.3' and packet.get('stage') == 'NO_DELIVERY_INSPECTION'
            except (ValueError, httpx.RequestNotRead):
                is_proof = False
            if is_proof:
                proof_number += 1
                try:
                    code = response.json().get('code')
                except (ValueError, httpx.ResponseNotRead, AttributeError):
                    code = None
                if code not in ('QUIESCENCE_REQUIRED', 'EVIDENCE_REQUIRED', 'RECOVERY_CONTEXT_MISMATCH',
                                'EVENT_STALE', 'DEVICE_DISABLED', 'IDEMPOTENCY_CONFLICT'):
                    code = None
                write_new(Path(out)/f'proof_ingress_{proof_number:04}.json', dict(
                    node=os.environ.get('PYTEST_CURRENT_TEST', '').split(' (')[0],
                    status=response.status_code, code=code))
        if response.status_code == 422:
            number += 1
            try:
                body = response.json()
            except (ValueError, httpx.ResponseNotRead):
                body = None
            # Only the application's fixed public error strings are retained.
            safe = {'body': '<redacted or unavailable>'}
            if isinstance(body, dict):
                safe = {k if k in ('code', 'message', 'details', 'correlation_id') else '<redacted key>':
                        '<redacted>' for k in body}
                for key, approved in (
                    ('code', ('CONFIG_NOT_READY', 'VALIDATION_ERROR')),
                    ('message', ('Approved simulation configuration is required', 'Request fields are invalid'))):
                    if body.get(key) in approved:
                        safe[key] = body[key]
            write_new(Path(out)/f'http_422_{number:04}.json', dict(status=422,
                path='/v1/qr-challenges' if request.url.path == '/v1/qr-challenges' else '<redacted>',
                node=os.environ.get('PYTEST_CURRENT_TEST', '').split(' (')[0], body=safe))
        return response
    with patch('httpx.Client.send', observed):
        yield


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def hashes():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = sorted(set(filter(None, paths)) | {p for p in EXTRA_SOURCE if (ROOT/p).is_file()})
    return [{'path': p, 'sha256': sha(ROOT/p)} for p in paths]


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())


def profiles(profile, targets=(), root=ROOT):
    if profile == 'compatibility':
        raise ValueError('Use tests/test_provision_database.py launcher; not a business runner profile')
    if profile not in ('business', 'tooling'):
        raise ValueError('Unknown profile')
    modules = (['tests/test_phase8b_tooling.py'] if profile == 'tooling' else
               sorted(p.relative_to(root).as_posix() for p in (root/'tests').glob('test_*.py')
                      if p.relative_to(root).as_posix() not in EXCLUDED))
    for target in targets:
        if target.startswith('-') or target.split('::')[0] not in modules:
            raise ValueError('Target outside selected profile: '+target)
    return list(targets) or modules


def reserve(label=None, parent=None):
    parent = Path(parent) if parent is not None else ROOT/'.local/pc-b1b'
    parent.mkdir(parents=True, exist_ok=True)
    label = label or uuid4().hex
    if not label or not label.replace('_', '').isalnum():
        raise ValueError('Alphanumeric/underscore run label required')
    out = parent/('b1b-harness-'+label)
    out.mkdir(exist_ok=False)
    return out


class Journal:
    """Append-only fsynced events. Nonterminal journals never establish a pass."""
    def __init__(self, out):
        self.out = Path(out)
        self.number = 0

    def emit(self, state, **fields):
        if state not in STATES:
            raise ValueError('Unknown state')
        self.number += 1
        value = {'state': state, 'at': datetime.now(timezone.utc).isoformat(), **fields}
        write_new(self.out/f'journal_{self.number:04}.json', value)
        return value


def inspect_run(out):
    events = sorted(Path(out).glob('journal_*.json'))
    if not events:
        return {'state': 'UNKNOWN', 'passed': False, 'reason': 'No durable start record'}
    last = json.loads(events[-1].read_text(encoding='utf-8'))
    if last['state'] == 'RUNNING':
        return {**last, 'recorded_state': 'RUNNING', 'state': 'UNKNOWN',
                'passed': False, 'reason': 'Incomplete; do not resume/reuse or assume cleanup'}
    return last


def protected_snapshot():
    """PC-only read-only data/catalog/ACL snapshot; no migrations/seed or runtime startup."""
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    for key, role in (('DATABASE_ADMIN_URL', 'postgres'), ('DATABASE_URL', 'doi_pin_runtime'),
                      ('MIGRATION_DATABASE_URL', 'doi_pin_migrator')):
        u = make_url(os.environ[key])
        if (u.host, u.port, u.database, u.username) != ('127.0.0.1', 5433, 'doi_pin', role):
            raise ValueError('PC database identity mismatch')
    u = make_url(os.environ['DATABASE_ADMIN_URL'])
    with psycopg.connect(host=u.host, port=u.port, dbname=u.database, user=u.username,
                        password=u.password, connect_timeout=5, row_factory=dict_row,
                        options='-cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000') as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        def q(statement, params=None):
            return c.execute(statement, params).fetchall()
        schemas = q("SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl::text AS acl FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' ORDER BY 1")
        names = [s['nspname'] for s in schemas]
        if 'doi_pin' not in names or 'pc_dev_b1b' not in names:
            raise ValueError('Protected PC schemas missing')
        data = {}
        for schema in names:
            data[schema] = {}
            for row in q('SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY 1', (schema,)):
                table = row['tablename']
                data[schema][table] = q(sql.SQL("SELECT count(*) AS n,md5(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) AS hash FROM {} t").format(sql.Identifier(schema, table)))[0]
        objects = q("SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2", (names,))
        columns = q("SELECT n.nspname,c.relname,a.attname,a.atttypid::regtype::text AS type,a.attacl::text AS acl FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3", (names,))
        definitions = q("SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS args,pg_get_functiondef(p.oid) AS body FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2,3", (names,))
        roles = q("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolcanlogin,rolreplication,rolbypassrls,rolconfig FROM pg_roles WHERE rolname IN ('doi_pin_migrator','doi_pin_runtime') ORDER BY 1")
        membership = q("SELECT roleid::regrole::text AS role,member::regrole::text AS member,admin_option FROM pg_auth_members ORDER BY 1,2")
        defaults = q("SELECT defaclrole::regrole::text AS role,defaclnamespace::regnamespace::text AS schema,defaclobjtype,defaclacl::text AS acl FROM pg_default_acl ORDER BY 1,2,3")
    evidence = {}
    roots = [ROOT/'docs/PHASE8B_TESTS', ROOT/'.local/device', ROOT/'.local/payment']
    roots += [p for p in (ROOT/'.local/pc-b1b').glob('reference-*') if p.is_dir()]
    roots += list((ROOT/'.cache').glob('b1b_real_*'))
    for folder in roots:
        for p in folder.rglob('*'):
            if p.is_file():
                evidence[p.relative_to(ROOT).as_posix()] = sha(p)
    for p in ('docs/PHASE8A_NFR06_AUDIT_COVERAGE.json', '.env'):
        evidence[p] = sha(ROOT/p)
    result = dict(schemas=schemas, data=data, objects=objects, columns=columns,
                  definitions=definitions, roles=roles, membership=membership,
                  defaults=defaults, evidence=evidence, source=hashes())
    return json.loads(json.dumps(result, default=str))


def preservation(before, after):
    names = {r['nspname'] for r in before['schemas']}
    if before['source'] != after['source'] or before['roles'] != after['roles'] or before['membership'] != after['membership'] or before['defaults'] != after['defaults']:
        return False
    if any(after['evidence'].get(p) != h for p, h in before['evidence'].items()):
        return False
    for key in ('schemas', 'objects', 'columns', 'definitions'):
        if before[key] != [r for r in after[key] if r['nspname'] in names]:
            return False
    if any(after['data'].get(s) != d for s, d in before['data'].items()):
        return False
    new = {r['nspname'] for r in after['schemas']} - names
    return all(s.startswith(('phase5_test_', 'b1a_upgrade_', 'b1a_clean_', 'b1b_')) for s in new)


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


class OutputGuard:
    """Same-process write barrier; Python subprocesses remain a documented boundary."""
    def __init__(self, out, root=ROOT):
        self.out, self.root = Path(out).resolve(), Path(root).resolve()

    def target(self, path):
        if isinstance(path, int):
            return path
        p = Path(path).resolve()
        if p.is_relative_to(self.out):
            return p
        if p.is_relative_to(self.root/'docs'):
            p = self.out/'reports'/p.relative_to(self.root/'docs')
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        raise PermissionError('Output outside this run refused')

    @contextlib.contextmanager
    def install(self):
        original_open, original_io = builtins.open, io.open
        def guarded(original):
            def opening(file, mode='r', *a, **kw):
                if any(c in mode for c in 'wax+'):
                    file = self.target(file)
                return original(file, mode, *a, **kw)
            return opening
        with patch('builtins.open', guarded(original_open)), patch('io.open', guarded(original_io)):
            yield


def worker(out):
    out = Path(out).resolve()
    config = json.loads((out/'command.json').read_text())
    os.environ.update(TEMP=str(out/'tmp'), TMP=str(out/'tmp'), B1B_REPORT_DIR=str(out))
    (out/'tmp').mkdir()
    class Reports:
        def pytest_collection_finish(self, session):
            nodes = [i.nodeid for i in session.items]
            write_new(out/'collected.json', {'node_ids': nodes,
                      'profile': config['profile'], 'execution_profile': config.get('execution_profile', 'round2'),
                      'exclusions': EXCLUDED})
            if pure and nodes != list(ROUND5_TARGETS):
                pure.failed = True
                raise ValueError('Unexpected Round 5 collection; execution refused')
            if config.get('execution_profile') == 'full':
                result=reconcile_collection(nodes,full_inventory(adapter.identity))
                if adapter.identity.get('selection_kind') == 'fixture_interaction' and nodes != list(FIX_VERIFY_TARGETS):
                    raise ValueError('CT11 must precede all affected cases in exact focused order')
                write_new(out/'collection_reconciliation.json',result)
        def pytest_runtest_setup(self, item):
            if pure and item.nodeid not in ROUND5_TARGETS:
                pure.failed = True
                raise ValueError('Unexpected Round 5 node; fixture execution refused')
        def pytest_runtest_logstart(self,nodeid,location):
            with (out/'node_events.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(dict(nodeid=nodeid,phase='start',outcome='running',pid=os.getpid(),at=datetime.now(timezone.utc).isoformat()))+'\n');f.flush();os.fsync(f.fileno())
        def pytest_runtest_logreport(self, report):
            with (out/'node_events.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps({'nodeid': report.nodeid, 'phase': report.when,
                                   'outcome': report.outcome})+'\n')
                f.flush()
                os.fsync(f.fileno())
    adapter, pure = None, None
    if config.get('execution_profile') == 'round5':
        validate_pure_selection(config)
        prohibited = [k for k in os.environ if k.startswith(('DATABASE_', 'MIGRATION_', 'POSTGRES_',
                      'PAYMENT_', 'DEMO_', 'DEVICE_KEY_', 'PG')) or k in ('MIGRATOR_PASSWORD', 'RUNTIME_PASSWORD')]
        if os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or prohibited:
            raise ValueError('Pure worker must start without database/application credentials or dotenv fallback')
        pure = PureContracts(out)
    if config.get('isolation'):
        identity, env = load_isolation(config['isolation'])
        validate_isolated_selection(config, identity)
        if os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or any(
            os.environ.get(k) != env[k] for k in (*DB_ROLES, DERIVATION_SECRET)):
            raise ValueError('Worker must start with isolated environment and dotenv disabled')
        isolated_catalog(identity, env, pristine=True)
        if config.get('execution_profile') == 'full':
            env['PAYMENT_LEDGER_PATH']=str(out/'runtime/provider.sqlite3');os.environ['PAYMENT_LEDGER_PATH']=env['PAYMENT_LEDGER_PATH']
            adapter = FullProcesses(out,identity,env)
        else:adapter = MigrationProcesses(out, identity, env)
    with contextlib.ExitStack() as stack:
        stack.enter_context(OutputGuard(out).install())
        if pure:
            stack.enter_context(pure.install())
        if adapter:
            stack.enter_context(adapter.install())
            stack.enter_context(observe_422(out))
            if isinstance(adapter,FullProcesses) and not config['collect_only']:adapter.start_mock()
            if config.get('execution_profile') in ('round3', 'round4'):
                stack.enter_context(adapter.local_transports())
        import pytest
        args = config['targets'] + ['-q', '--tb=short', '-p', 'no:cacheprovider',
                '--log-file='+str(out/'pytest-events.log'),
                '--basetemp='+str(out/'pytest-tmp'), '--junitxml='+str(out/'results.xml')]
        if config['profile'] == 'tooling':
            args += ['--noconftest']
        if config['collect_only']:
            args += ['--collect-only']
        try:
            return int(pytest.main(args, plugins=[Reports()]))
        finally:
            if pure:
                write_new(out/'pure_summary.json', dict(failed=pure.failed, refusals=pure.refusals,
                          database_operations=0, SQLite_operations=0, native_subprocesses=0,
                          provider_operations=0, credentials_present=False))
            if adapter:
                if isinstance(adapter,FullProcesses):adapter.close()
                write_new(out/'subprocess_summary.json', dict(failed=adapter.failed,
                          invocations=adapter.number, claimed_schemas=sorted(adapter.claimed)))


def machine_sample():
    import shutil,ctypes
    result=dict(at=datetime.now(timezone.utc).isoformat(),disk_free_bytes=shutil.disk_usage(ROOT).free,
                supervisor_cpu_seconds=os.times().user+os.times().system)
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        m=Memory();m.length=ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            result.update(available_RAM_bytes=m.available,memory_load_percent=m.load)
    return result


def full_wait(child,out,before,snapshot):
    start=last_check=time.monotonic();sample=0;next_sample=0
    while True:
        now=time.monotonic()
        if now>=next_sample:
            sample+=1;resource=machine_sample();resource.update(child_pid=child.pid,elapsed_seconds=now-start)
            write_new(Path(out)/f'resource_{sample:04}.json',resource);next_sample=now+30
            if resource['disk_free_bytes']<2*1024**3 or resource.get('available_RAM_bytes',2*1024**3)<1024**3:
                raise RuntimeError('Resource exhaustion threshold')
        code=child.poll()
        if code is not None:return code
        if now-start>14400:raise subprocess.TimeoutExpired('full-business-worker',14400)
        if now-last_check>=300:
            if not preservation(before,snapshot()):raise RuntimeError('Protected drift during regression')
            last_check=now
        time.sleep(2)


def execute(out, config, snapshot=protected_snapshot, launch=subprocess.Popen):
    journal = Journal(out)
    command = [sys.executable, '-B', str(ROOT/'tools/run_phase8b.py'), '--_worker', str(out)]
    full=config.get('execution_profile')=='full'
    if full:command[0]=sys._base_executable
    journal.emit('RUNNING', stage='preflight', pid=os.getpid(), command=command,
                 profile=config['profile'], collect_only=config['collect_only'],
                 execution_profile=config.get('execution_profile', 'round2'),
                 head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    child, code, power = None, None, False
    try:
        before = snapshot()
        write_new(out/'protected_before.json', before)
        identity = None
        pure = config.get('execution_profile') == 'round5'
        if pure:
            validate_pure_selection(config)
        if config.get('execution_profile') in ('round3', 'round4','full') and not config.get('isolation'):
            raise ValueError('Selected round requires physical isolation')
        if config.get('isolation'):
            identity, env = load_isolation(config['isolation'])
            validate_isolated_selection(config, identity)
            if any(make_url(os.environ[k]).password == make_url(env[k]).password for k in DB_ROLES):
                raise ValueError('Protected credentials cannot be reused')
            if env[DERIVATION_SECRET] == os.environ.get(DERIVATION_SECRET):
                raise ValueError('Protected derivation secret cannot be reused')
            verify_container(identity)
            write_new(out/'isolated_before.json', isolated_catalog(identity, env, pristine=True))
            write_new(out/'environment_contract.json', dict(endpoint=list(isolation_endpoint(identity)),
                      worker_keys=sorted(env), derivation_secret_valid=True,
                      dotenv_disabled=True, provisioning_derivation_secret=False))
        elif pure:
            env = pure_environment()
            write_new(out/'environment_contract.json', dict(mode='pure_contract', worker_keys=sorted(env),
                      database_credentials=False, dotenv_disabled=True, effects='FORBIDDEN'))
        else:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
                       PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        write_new(out/'command.json', {**config, 'command': command})
        env.pop('PYTEST_ADDOPTS', None)
        env.pop('PYTEST_PLUGINS', None)
        with (out/'run.log').open('xb') as log:
            if full and os.name=='nt':
                import ctypes
                power=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
                write_new(out/'power_request.json',dict(process_scoped_system_required=power,Windows_policy_changed=False))
            child = launch(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            journal.emit('RUNNING', stage='child-started', child_pid=child.pid)
            code = full_wait(child,out,before,snapshot) if full else (child.wait(timeout=600) if identity or pure else child.wait())
        journal.emit('RUNNING', stage='post-check', test_exit_code=code)
        if full:
            if child.poll() is None:
                raise RuntimeError('Test worker is not quiescent')
            effects = json.loads((out/'full_effect_manifest.json').read_text())
            if effects.get('local_workers_quiescent') is not True:
                raise RuntimeError('Local test workers are not quiescent')
            native = list((out/'native').glob('*/start.json'))
            if len(native) != effects['native_children']:
                raise RuntimeError('Incomplete native process inventory')
            for start_path in native:
                start = json.loads(start_path.read_text())
                actual = json.loads((start_path.parent/'actual_pid.json').read_text())
                ended = json.loads((start_path.parent/'exit.json').read_text())
                if start['pid'] != actual['pid'] or actual['pid'] != ended['pid'] or ended['exit_code'] is None:
                    raise RuntimeError('Native process exit identity not verified')
        after = snapshot()
        write_new(out/'protected_after.json', after)
        subprocess_failed = False
        if pure:
            summary = json.loads((out/'pure_summary.json').read_text())
            subprocess_failed = summary['failed'] or summary['refusals'] != 0
        if identity:
            verify_container(identity)
            write_new(out/'isolated_after.json', isolated_catalog(identity, env))
            summary = json.loads((out/'subprocess_summary.json').read_text())
            subprocess_failed = summary['failed'] or any(
                json.loads(p.read_text())['state'] != 'COMPLETED' or json.loads(p.read_text())['exit_code'] != 0
                for p in (out/'subprocesses').glob('[0-9][0-9][0-9][0-9].json'))
        okay = preservation(before, after)
        if not okay:
            raise RuntimeError('Protected snapshot mismatch')
        result = dict(state='COMPLETED', passed=code == 0 and not subprocess_failed, test_exit_code=code,
                      post_checks='PASS', profile=config['profile'], collect_only=config['collect_only'])
        if identity:
            result['subprocess_checks'] = 'FAILED' if subprocess_failed else 'PASS'
            result['execution_profile'] = config.get('execution_profile', 'round2')
        if pure:
            result['execution_profile'] = 'round5'
            result['pure_contract_checks'] = 'FAILED' if subprocess_failed else 'PASS'
        write_new(out/'exit.json', result)
        journal.emit(**result)
        return code or int(subprocess_failed)
    except BaseException as error:
        state = 'INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'UNKNOWN'
        if child is not None and code is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass  # Preserve identity/journal; no claim that an orphan was cleaned up.
        sqlstate = getattr(error, 'sqlstate', None)
        journal.emit(state, passed=False, test_exit_code=code, error_type=type(error).__name__, sqlstate=sqlstate)
        write_new(out/'exit.json', dict(state=state, passed=False, test_exit_code=code,
                                      post_checks='UNKNOWN_OR_FAILED', error_type=type(error).__name__, sqlstate=sqlstate))
        return 130 if state == 'INTERRUPTED' else 1
    finally:
        if power:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        write_new(out/'artifacts.json', {'files': {p.relative_to(out).as_posix(): sha(p)
                  for p in out.rglob('*') if p.is_file()}, 'excludes': 'This manifest itself'})


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--_native':return native_main(sys.argv[2])
    if len(sys.argv) > 1 and sys.argv[1] == '--_worker':
        return worker(sys.argv[2])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label', nargs='?')
    parser.add_argument('--profile', default='business', choices=('business', 'tooling', 'compatibility'))
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--status', type=Path)
    parser.add_argument('--isolation', type=Path, help='Explicit local isolated-instance identity JSON')
    parser.add_argument('--execution-profile', choices=('round2', 'round3', 'round4', 'round5','full'), default='round2')
    args, targets = parser.parse_known_args()
    if args.status:
        print(json.dumps(inspect_run(args.status), indent=2))
        return 0
    if args.execution_profile in ('round3', 'round4','full') and not args.isolation:
        parser.error('Selected round requires --isolation; no unisolated fallback')
    selection = profiles(args.profile, targets)
    out = reserve(args.label)
    print(str(out), flush=True)
    config = dict(profile=args.profile, targets=selection, collect_only=args.collect_only,
                  execution_profile=args.execution_profile)
    if args.isolation:
        config['isolation'] = str(args.isolation.resolve())
    return execute(out, config)


if __name__ == '__main__':
    sys.exit(main())
