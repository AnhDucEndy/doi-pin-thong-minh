"""Revision-aware atomic grants; never replace credentials or repair ACL drift."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/backend'))
from app.config import Settings
from sqlalchemy import create_engine
from psycopg import sql

OWNER, RUNTIME = 'doi_pin_migrator', 'doi_pin_runtime'
REVISIONS = ('0002_user_approval', '0009_refund_foundation', '0010_no_delivery_eligibility')

# Explicit inventories from 0001/0002; catalog discovery never chooses GRANT targets.
BASE_COLUMNS = {
    'alembic_version': 'version_num',
    'alerts': 'id station_id battery_id compartment_id dedup_key code state last_event_id acknowledged_by resolved_by resolution_note occurrences version created_at',
    'audit_events': 'id actor_type actor_id aggregate_type aggregate_id action before_data after_data correlation_id created_at',
    'auth_sessions': 'id user_id token_hash expires_at revoked_at created_at',
    'batteries': 'id serial family lifecycle location_kind compartment_id holder_user_id version created_at',
    'battery_telemetry': 'id event_id battery_id soc soh temperature_c fault_codes measured_at received_at quality_ok',
    'compartments': 'id station_id slot_no service_state door_state observed_present observed_serial observed_at version created_at',
    'credentials': 'id user_id kind credential_hash revoked_at created_at',
    'demo_policies': 'id revision parameters review_status confirmed_by confirmed_at created_at approval_evidence',
    'device_commands': 'id device_id swap_id compartment_id kind state expires_at payload_hash payload evidence_event_id version created_at',
    'device_events': 'id device_id boot_id seq kind compartment_id swap_id command_id observed_at received_at payload_hash payload processed_at processing_error accepted',
    'devices': 'id station_id serial key_hash enabled last_received_at boot_id last_seq version created_at',
    'idempotency_records': 'principal route key request_hash response_status response_body expires_at created_at',
    'login_limits': 'bucket_key failed_count window_started_at locked_until',
    'outbox_messages': 'id aggregate_type aggregate_id kind dedup_key payload attempts next_attempt_at delivered_at created_at',
    'payment_events': 'id provider_event_id payment_id refund_id payload_hash payload processed_at created_at',
    'payments': 'id swap_id provider_key provider_reference state amount_minor currency verified_at version created_at',
    'qr_challenges': 'id user_id station_id token_hash expires_at consumed_at created_at',
    'recovery_cases': 'id swap_id state assigned_to evidence_event_id new_pin_delivered old_pin_settled resolution_note version created_at',
    'refunds': 'id payment_id requested_by provider_key provider_reference state amount_minor verified_at reason version created_at',
    'resource_reservations': 'id swap_id battery_id compartment_id released_at created_at',
    'stations': 'id code name address state version created_at',
    'swap_transactions': 'id customer_id station_id verified_via qr_challenge_id credential_id state policy_id policy_snapshot old_battery_id new_battery_id return_compartment_id supply_compartment_id amount_minor currency consented_at reservation_expires_at return_observed_at pickup_observed_at review_reason closed_at version created_at',
    'user_station_assignments': 'user_id station_id created_at',
    'users': 'id username password_hash role state version created_at',
}
RECOVERY_COLUMNS = {
    'recovery_operations': 'id case_id swap_id station_id customer_id pin_id expected_serial purpose context context_hash created_by created_at expires_at base_case_version base_swap_version supersedes_id consumed_at cancelled_at protocol_version',
    'recovery_attestations': 'id event_id operation_id source_kind actor_user_id device_id observed_at received_at payload payload_hash source_boot source_seq source_event_id stage reference_receipt_id',
    'recovery_action_authorizations': 'id operation_id context_hash inspection_id technician_attestation_id customer_attestation_id device_id boot_id ledger_id fence_generation authorized_by issued_at expires_at authorization_hash payload revoked_at',
    'recovery_inspection_inbox': 'event_id device_id payload_hash payload status response received_at',
    'recovery_authorization_acks': 'id authorization_id event_id device_id boot_id seq observed_at received_at payload_hash payload',
    'recovery_action_activations': 'id authorization_id acknowledgment_id operation_id activated_by issued_at expires_at payload_hash payload',
    'recovery_closure_intents': 'id operation_id created_by auth_session_id created_at payload payload_hash',
    'recovery_closure_receipts': 'id closure_id event_id device_id boot_id seq observed_at received_at payload payload_hash',
}
REFUND_COLUMNS = {
    'refund_attempts': 'id refund_id generation permit_id created_at',
    'refund_retry_permissions': 'id refund_id prior_attempt_id prior_generation attempt_id generation issued_at expires_at payload payload_hash',
    'refund_permit_redemptions': 'permit_id attempt_id redeemed_at',
    'refund_eligibility_certificates': 'id operation_id payment_id receipt_id technician_attestation_id customer_attestation_id validated_at valid_until payload payload_hash',
    'refund_certificate_redemptions': 'certificate_id refund_id payment_id redeemed_at',
}
TABLE_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN')
COLUMN_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES')


class ProvisioningError(ValueError):
    """Stable, secret-free refusal; no automatic repair/revoke."""


def require(condition, message):
    if not condition:
        raise ProvisioningError(message)


def columns_for(revision):
    require(revision in REVISIONS, 'Unsupported revision')
    result = dict(BASE_COLUMNS)
    if revision != REVISIONS[0]:
        result.update(RECOVERY_COLUMNS)
        result.update(REFUND_COLUMNS)
        result['recovery_cases'] += ' operation_id'  # 0003
    if revision == REVISIONS[2]:
        result['refund_eligibility_certificates'] += ' issued_by issuer_session_id'
        result['refund_certificate_revocations'] = 'id certificate_id revoked_at reason_code source_event_id actor_user_id correlation_id'
    return {table: set(names.split()) for table, names in result.items()}


def grant_plan(revision, profile='runtime'):
    columns = columns_for(revision)
    require(profile in ('runtime', 'reference-readonly'), 'Unknown profile')
    require(profile != 'reference-readonly' or revision == REVISIONS[0], 'Reference profile requires 0002')
    tables = {name: {'SELECT'} for name in columns}
    updates = {}
    if profile == 'reference-readonly':
        return tables, updates
    for table in ('users', 'auth_sessions', 'login_limits', 'user_station_assignments', 'idempotency_records',
                  'stations', 'devices', 'compartments', 'batteries', 'device_events', 'device_commands', 'alerts',
                  'credentials', 'qr_challenges', 'swap_transactions', 'resource_reservations',
                  'payments', 'payment_events', 'outbox_messages'):
        tables[table].update(('INSERT', 'UPDATE'))
    tables['user_station_assignments'].add('DELETE')
    for table in ('audit_events', 'battery_telemetry', 'recovery_cases'):
        tables[table].add('INSERT')
    updates['recovery_cases'] = set('state assigned_to evidence_event_id new_pin_delivered old_pin_settled resolution_note version'.split())
    if revision != REVISIONS[0]:
        updates['recovery_cases'].add('operation_id')
        for table in (*RECOVERY_COLUMNS, 'refund_attempts', 'refund_retry_permissions', 'refund_permit_redemptions', 'refunds'):
            tables[table].add('INSERT')
        updates.update(recovery_operations={'consumed_at', 'cancelled_at'},
                       recovery_action_authorizations={'revoked_at'},
                       refunds={'state', 'version', 'provider_reference', 'verified_at'})
    if revision == REVISIONS[2]:
        for table in ('refund_eligibility_certificates', 'refund_certificate_redemptions', 'refund_certificate_revocations'):
            tables[table].add('INSERT')
    return tables, updates


def validate_roles(cursor):
    for role in (OWNER, RUNTIME):
        cursor.execute('SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (role,))
        row = cursor.fetchone()
        require(row is not None and row[0] and not any(row[1:]), 'Application role missing or privileged')
        cursor.execute('SELECT 1 FROM pg_auth_members WHERE member=%s::regrole', (role,))
        require(cursor.fetchone() is None, 'Application role membership drift')


def schema_owner(cursor, schema):
    cursor.execute('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=%s', (schema,))
    row = cursor.fetchone()
    return row[0] if row else None


def validate_catalog(cursor, schema):
    Settings('postgresql+psycopg://unused', schema)
    require(schema_owner(cursor, schema) == OWNER, 'Schema owner mismatch')
    validate_roles(cursor)
    cursor.execute(sql.SQL('SELECT version_num FROM {}.alembic_version FOR SHARE').format(sql.Identifier(schema)))
    rows = cursor.fetchall()
    require(len(rows) == 1 and rows[0][0] in REVISIONS, 'Missing or unsupported revision')
    revision = rows[0][0]
    expected = columns_for(revision)
    cursor.execute("SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f','S')", (schema,))
    relations = cursor.fetchall()
    require({r[0] for r in relations} == set(expected) and all(r[1] == 'r' and r[2] == OWNER for r in relations), 'Relation inventory/ownership mismatch')
    # Hold DDL locks through preflight, grants and commit.
    cursor.execute(sql.SQL('LOCK TABLE {} IN ACCESS SHARE MODE').format(sql.SQL(',').join(sql.Identifier(schema, t) for t in sorted(expected))))
    cursor.execute("SELECT c.relname,a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped", (schema,))
    actual = {t: set() for t in expected}
    for table, column in cursor.fetchall():
        actual[table].add(column)
    require(actual == expected, 'Column/revision mismatch')
    cursor.execute("SELECT 1 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid LEFT JOIN pg_class f ON f.oid=k.confrelid WHERE c.relnamespace=%s::regnamespace AND (NOT k.convalidated OR (k.contype='f' AND f.relnamespace<>c.relnamespace))", (schema,))
    require(cursor.fetchone() is None, 'Unvalidated or cross-schema constraint')
    cursor.execute("SELECT t.tgtype,t.tgenabled,p.proname,p.pronamespace=n.oid FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname=%s AND c.relname='audit_events' AND t.tgname='audit_append_only' AND NOT t.tgisinternal", (schema,))
    require(cursor.fetchone() == (27, 'O', 'reject_audit_change', True), 'Audit append-only trigger mismatch')
    cursor.execute("SELECT 1 FROM pg_default_acl WHERE defaclrole=%s::regrole AND defaclnamespace IN (0,%s::regnamespace)", (OWNER, schema))
    require(cursor.fetchone() is None, 'Default privilege drift')
    return revision, expected


def check_privilege_drift(cursor, schema, expected, tables, updates):
    cursor.execute("SELECT has_schema_privilege(%s,%s,'CREATE'),pg_has_role(%s,%s,'USAGE')", (RUNTIME, schema, RUNTIME, OWNER))
    require(cursor.fetchone() == (False, False), 'Runtime DDL/owner authority drift')
    for table, columns in sorted(expected.items()):
        qualified = sql.Identifier(schema, table).as_string(cursor)
        for privilege in TABLE_PRIVILEGES:
            cursor.execute('SELECT has_table_privilege(%s,%s,%s),has_table_privilege(%s,%s,%s)',
                           (RUNTIME, qualified, privilege, RUNTIME, qualified, privilege+' WITH GRANT OPTION'))
            effective, grantable = cursor.fetchone()
            require(not grantable and (not effective or privilege in tables[table]), 'Table privilege drift: '+table)
        for column in sorted(columns):
            for privilege in COLUMN_PRIVILEGES:
                cursor.execute('SELECT has_column_privilege(%s,%s,%s,%s),has_column_privilege(%s,%s,%s,%s)',
                               (RUNTIME, qualified, column, privilege, RUNTIME, qualified, column, privilege+' WITH GRANT OPTION'))
                effective, grantable = cursor.fetchone()
                allowed = privilege in tables[table] or (privilege == 'UPDATE' and column in updates.get(table, set()))
                require(not grantable and (not effective or allowed), 'Column privilege drift: '+table+'.'+column)


def execute_grant(cursor, statement):
    """Execution boundary for transaction-failure injection on isolated schemas."""
    cursor.execute(statement)


def apply_grants(cursor, schema, profile='runtime'):
    """Caller owns the transaction. All validation precedes the first GRANT."""
    revision, expected = validate_catalog(cursor, schema)
    tables, updates = grant_plan(revision, profile)
    check_privilege_drift(cursor, schema, expected, tables, updates)
    execute_grant(cursor, sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema), sql.Identifier(RUNTIME)))
    for table, privileges in sorted(tables.items()):
        execute_grant(cursor, sql.SQL('GRANT {} ON {} TO {}').format(
            sql.SQL(', ').join(sql.SQL(p) for p in sorted(privileges)), sql.Identifier(schema, table), sql.Identifier(RUNTIME)))
    for table, names in sorted(updates.items()):
        execute_grant(cursor, sql.SQL('GRANT UPDATE ({}) ON {} TO {}').format(
            sql.SQL(', ').join(sql.Identifier(c) for c in sorted(names)), sql.Identifier(schema, table), sql.Identifier(RUNTIME)))
    return revision


def provision_roles(cursor, schema):
    Settings('postgresql+psycopg://unused', schema)
    require(schema_owner(cursor, schema) in (None, OWNER), 'Schema owner mismatch')
    for role, secret in ((OWNER, 'MIGRATOR_PASSWORD'), (RUNTIME, 'RUNTIME_PASSWORD')):
        password = os.environ[secret]
        require(len(password) >= 24 and not password.startswith('REPLACE_'), 'Strong local database secret required')
        cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
        if cursor.fetchone() is None:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role), sql.Literal(password)))
    validate_roles(cursor)
    cursor.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}').format(sql.Identifier(schema), sql.Identifier(OWNER)))
    cursor.execute("SELECT has_schema_privilege(%s,%s,'CREATE')", (RUNTIME, schema))
    require(cursor.fetchone() == (False,), 'Runtime schema CREATE drift')
    cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema), sql.Identifier(RUNTIME)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('roles', 'grants'), nargs='?', default='roles')
    parser.add_argument('--profile', choices=('runtime', 'reference-readonly'), default='runtime')
    args = parser.parse_args()
    require(args.stage == 'grants' or args.profile == 'runtime', 'Profile is only valid for grants')
    schema = os.getenv('DATABASE_SCHEMA', 'doi_pin')
    Settings(os.environ['DATABASE_ADMIN_URL'], schema)
    engine = create_engine(os.environ['DATABASE_ADMIN_URL'], hide_parameters=True,
                           connect_args={'connect_timeout': 5, 'options': '-cstatement_timeout=15000 -clock_timeout=5000'})
    try:
        with engine.begin() as connection:
            cursor = connection.connection.driver_connection.cursor()
            try:
                if args.stage == 'roles':
                    provision_roles(cursor, schema)
                else:
                    apply_grants(cursor, schema, args.profile)
            finally:
                cursor.close()
    finally:
        engine.dispose()
    print('Project database provisioning ready; no credentials or existing data overwritten')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Driver/SQLAlchemy exception text can contain connection parameters.
        print('Provisioning refused: '+(str(error) if isinstance(error, ProvisioningError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
