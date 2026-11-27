"""Explicit one-fixture integration wrapper; no import-time database access.

Uses official Alembic history and grant_plan/validate_catalog unchanged. Never
calls official provision_roles/apply_grants, which bind the shared runtime role.
Provisioning authority remains in the caller, separate from child configuration.
"""
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit, unquote

import psycopg
from psycopg import sql

from .adapter import require
from .admission import collect_identity, REVISION


def authority_parameters(config, url, expected_user):
    u=urlsplit(url.replace('postgresql+psycopg://','postgresql://'))
    require(u.scheme=='postgresql' and u.hostname=='127.0.0.1' and u.port==config.target[0]
            and u.path=='/'+config.database and not u.query and not u.fragment
            and unquote(u.username or '')==expected_user and bool(u.password), 'PROVISION_AUTHORITY_BINDING')
    return dict(host='127.0.0.1',hostaddr='127.0.0.1',port=config.target[0],dbname=config.database,
                user=expected_user,password=unquote(u.password),connect_timeout=5)


def provision_one(root, output, config, admin_url, migration_url):
    """Caller must first pass preservation/resources/isolation preflight.

    Exclusive intent precedes all writes. Any failure leaves partial resources;
    there is no cleanup, overwrite, adoption or second attempt.
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from tools.provision_database import validate_catalog, grant_plan
    config.validate();root=Path(root).resolve();output=Path(output).resolve()
    require(output.is_relative_to(root/'.local'),'PROVISION_OUTPUT')
    admin=authority_parameters(config,admin_url,'postgres')
    authority_parameters(config,migration_url,'doi_pin_migrator')
    with psycopg.connect(**admin,options='-cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000') as c:
        identity=collect_identity(config,c)
        require(not c.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(config.schema,)).fetchone(),'SCHEMA_COLLISION')
        require(not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(config.role,)).fetchone(),'ROLE_COLLISION')
    with (output/'provision_intent.json').open('x',encoding='utf-8') as f:
        json.dump(dict(run_id=config.run_id,schema=config.schema,role=config.role,identity=identity,cleanup=False),f)
    private=dict(runtime_password=secrets.token_urlsafe(36),payment_key=secrets.token_urlsafe(36),device_key=secrets.token_urlsafe(36))
    with (output/'private.json').open('x',encoding='utf-8') as f:json.dump(private,f)
    with psycopg.connect(**admin,options='-cstatement_timeout=15000 -clock_timeout=5000') as c:
        # Both names have passed strict Config validation; Identifier/Literal
        # quoting is still mandatory. Statement text is never logged.
        c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(config.role),sql.Literal(private['runtime_password'])))
        c.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION doi_pin_migrator').format(sql.Identifier(config.schema)))
        c.execute(sql.SQL('COMMENT ON SCHEMA {} IS {}').format(sql.Identifier(config.schema),sql.Literal('g6_business:'+config.run_id)))
    previous={k:os.environ.get(k) for k in ('MIGRATION_DATABASE_URL','DATABASE_SCHEMA')}
    try:
        os.environ.update(MIGRATION_DATABASE_URL=migration_url,DATABASE_SCHEMA=config.schema)
        command.upgrade(AlembicConfig(str(root/'services/backend/alembic.ini')),REVISION)
    finally:
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    with psycopg.connect(**admin,options='-cstatement_timeout=15000 -clock_timeout=5000') as c:
        with c.cursor() as cursor:
            revision,expected=validate_catalog(cursor,config.schema)
            require(revision==REVISION,'PROVISION_REVISION')
            tables,updates=grant_plan(revision)
            cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(config.schema),sql.Identifier(config.role)))
            for table,privileges in sorted(tables.items()):
                cursor.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(',').join(sql.SQL(p) for p in sorted(privileges)),sql.Identifier(config.schema,table),sql.Identifier(config.role)))
            for table,columns in sorted(updates.items()):
                cursor.execute(sql.SQL('GRANT UPDATE ({}) ON {} TO {}').format(sql.SQL(',').join(sql.Identifier(n) for n in sorted(columns)),sql.Identifier(config.schema,table),sql.Identifier(config.role)))
    with (output/'provision_completed.json').open('x',encoding='utf-8') as f:
        json.dump(dict(schema=config.schema,role=config.role,revision=revision,tables=len(expected),seed=False,shared_runtime_grants_changed=False),f)
    return private
