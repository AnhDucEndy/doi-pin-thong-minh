import os
from alembic import context
from sqlalchemy import create_engine
from app.config import Settings

url = os.environ['MIGRATION_DATABASE_URL']
schema = os.getenv('DATABASE_SCHEMA', 'doi_pin')
Settings(url, schema)  # Validate PostgreSQL and identifier before SQL interpolation.
engine = create_engine(url, hide_parameters=True, connect_args={'options': f'-csearch_path={schema},public'})
with engine.connect() as connection:
    context.configure(connection=connection, version_table_schema=schema, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
