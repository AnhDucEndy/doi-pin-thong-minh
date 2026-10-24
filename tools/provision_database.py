"""Provision only this project's new roles/schema; never replace existing credentials."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/backend'))
from app.config import Settings
from sqlalchemy import create_engine
from psycopg import sql


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else 'roles'
    schema = os.getenv('DATABASE_SCHEMA', 'doi_pin')
    Settings(os.environ['DATABASE_ADMIN_URL'], schema)
    engine = create_engine(os.environ['DATABASE_ADMIN_URL'], hide_parameters=True)
    with engine.begin() as conn:
        cursor = conn.connection.driver_connection.cursor()
        if stage == 'roles':
            for role, secret in [('doi_pin_migrator', 'MIGRATOR_PASSWORD'), ('doi_pin_runtime', 'RUNTIME_PASSWORD')]:
                password = os.environ[secret]
                if len(password) < 24 or password.startswith('REPLACE_'):
                    raise ValueError('Use a strong generated database secret')
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                if not cursor.fetchone():
                    cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(
                        sql.Identifier(role), sql.Literal(password)))
            cursor.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION doi_pin_migrator').format(sql.Identifier(schema)))
            cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO doi_pin_runtime').format(sql.Identifier(schema)))
        elif stage == 'grants':
            cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO doi_pin_runtime').format(sql.Identifier(schema)))
            cursor.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO doi_pin_runtime').format(sql.Identifier(schema)))
            for name in ('users', 'auth_sessions', 'login_limits', 'user_station_assignments', 'idempotency_records',
                         'stations', 'devices', 'compartments', 'batteries'):
                cursor.execute(sql.SQL('GRANT INSERT, UPDATE ON {}.{} TO doi_pin_runtime').format(sql.Identifier(schema), sql.Identifier(name)))
            cursor.execute(sql.SQL('GRANT DELETE ON {}.user_station_assignments TO doi_pin_runtime').format(sql.Identifier(schema)))
            cursor.execute(sql.SQL('GRANT INSERT ON {}.audit_events TO doi_pin_runtime').format(sql.Identifier(schema)))
            cursor.execute(sql.SQL('GRANT UPDATE (state, review_reason, version) ON {}.swap_transactions TO doi_pin_runtime').format(sql.Identifier(schema)))
            cursor.execute(sql.SQL('GRANT UPDATE (state, resolved_by, resolution_note, last_event_id, version) ON {}.alerts TO doi_pin_runtime').format(sql.Identifier(schema)))
        else:
            raise ValueError('Stage must be roles or grants')
    engine.dispose()
    print(f'Project database {stage} ready; no credentials or existing data overwritten')


if __name__ == '__main__':
    main()
