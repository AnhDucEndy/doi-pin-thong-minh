"""Real PostgreSQL migration and least-privilege checks for recovery evidence."""
from sqlalchemy import text


def test_recovery_schema_and_runtime_grants(environment):
    schema = environment['settings'].schema
    with environment['owner'].connect() as conn:
        assert conn.scalar(text('select version_num from alembic_version')) == '0008_recovery_reconciliation'
        for table in ('recovery_operations', 'recovery_attestations', 'recovery_action_authorizations', 'recovery_action_activations', 'recovery_closure_intents', 'recovery_closure_receipts'):
            assert conn.scalar(text('select to_regclass(:name)'), {'name': f'{schema}.{table}'})
            for permission in ('SELECT', 'INSERT'):
                assert conn.scalar(text("select has_table_privilege('doi_pin_runtime', :name, :permission)"),
                    {'name': f'{schema}.{table}', 'permission': permission})
            assert not conn.scalar(text("select has_table_privilege('doi_pin_runtime', :name, 'DELETE')"),
                {'name': f'{schema}.{table}'})
        assert not conn.scalar(text("select has_table_privilege('doi_pin_runtime', :name, 'UPDATE')"),
            {'name': f'{schema}.recovery_attestations'})
        assert not conn.scalar(text("select has_table_privilege('doi_pin_runtime', :name, 'UPDATE')"),
            {'name': f'{schema}.recovery_action_activations'})
        assert not conn.scalar(text("select has_column_privilege('doi_pin_runtime', :name, 'context', 'UPDATE')"),
            {'name': f'{schema}.recovery_operations'})
        assert conn.scalar(text("select has_column_privilege('doi_pin_runtime', :name, 'consumed_at', 'UPDATE')"),
            {'name': f'{schema}.recovery_operations'})
        assert conn.scalar(text("select count(*) from pg_trigger where tgrelid = to_regclass(:name) and not tgisinternal"),
            {'name': f'{schema}.recovery_attestations'}) == 2


def test_existing_recovery_cases_not_backfilled(environment):
    # Fresh fixture plus historical user marker is created across 0001->head by
    # conftest; no seed is permitted to manufacture recovery proof.
    with environment['owner'].connect() as conn:
        assert conn.scalar(text('select count(*) from recovery_operations')) == 0
        assert conn.scalar(text('select count(*) from recovery_attestations')) == 0
