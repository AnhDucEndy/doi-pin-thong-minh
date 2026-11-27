"""Read-only PostgreSQL collectors. Identity authority is never a runtime child.

No collector provisions, grants, or turns synthetic facts into launch authority.
TEMP/CONNECT inherited from PUBLIC are recorded, not falsely revoked per-role.
"""
from psycopg import sql

from .adapter import require
from tools.provision_database import columns_for, grant_plan

REVISION = '0010_no_delivery_eligibility'


def verify_system_acl(control_acl, explicit_runtime_grants, parameter_grants):
    # Stock pg_control_system has a NULL ACL (default PUBLIC EXECUTE). Reading
    # control metadata is not admin authority. Never GRANT it or rely on runtime
    # testimony as identity authority. Any altered ACL requires separate review.
    require(control_acl is None,'CONTROL_SYSTEM_ACL_DRIFT')
    require(not explicit_runtime_grants and not parameter_grants,'SYSTEM_AUTHORITY_GRANTS')


def binding(config, connection):
    config.validate()
    i = connection.info
    require((i.host, i.port, i.dbname) == ('127.0.0.1', config.target[0], config.database), 'DB_ENDPOINT')
    require(connection.execute('SHOW transaction_read_only').fetchone()[0] == 'on', 'READONLY_INSPECTION')


def collect_identity(config, authority):
    """Separate authorized read-only session; never pass this connection to child."""
    binding(config, authority)
    row = authority.execute('SELECT current_database(),system_identifier::text FROM pg_control_system()').fetchone()
    require(row == (config.database, config.system_identifier), 'ACTUAL_CLUSTER_IDENTITY')
    return dict(database=row[0], system_identifier=row[1], port=config.target[0])


def collect_runtime(config, connection):
    """Exact effective grants, including column rights and inherited authority."""
    binding(config, connection)
    q = connection.execute
    require(q('SELECT session_user,current_user').fetchone() == (config.role, config.role), 'RUNTIME_SESSION')
    flags = q('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
    require(flags is not None and not any(flags), 'ROLE_FLAGS')
    memberships = q("SELECT rolname FROM pg_roles WHERE rolname<>current_user AND (pg_has_role(oid,'MEMBER') OR pg_has_role(oid,'USAGE') OR pg_has_role(oid,'SET'))").fetchall()
    require(not memberships, 'ROLE_ESCALATION')
    schemas = q("SELECT nspname,pg_get_userbyid(nspowner),obj_description(oid,'pg_namespace'),has_schema_privilege(oid,'USAGE'),has_schema_privilege(oid,'CREATE') FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' ORDER BY nspname").fetchall()
    own = [r for r in schemas if r[0] == config.schema]
    require(len(own) == 1 and own[0][1:]==('doi_pin_migrator','g6_business:'+config.run_id,True,False), 'SCHEMA_MARKER_OWNER')
    require(not any(r[4] or (r[3] and r[0] not in (config.schema, 'public')) for r in schemas), 'CROSS_SCHEMA_AUTHORITY')
    relations = q("SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner),c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f','S') ORDER BY 1,2").fetchall()
    expected = columns_for(REVISION)
    tables, updates = grant_plan(REVISION)
    ours = [r for r in relations if r[0] == config.schema]
    require({r[1] for r in ours} == set(expected) and all(r[2]=='r' and r[3]=='doi_pin_migrator' for r in ours), 'RELATIONS')
    require(q(sql.SQL('SELECT version_num FROM {}.alembic_version').format(sql.Identifier(config.schema))).fetchall()==[(REVISION,)], 'REVISION')
    table_facts=[]; column_facts=[]
    for schema, name, kind, owner, oid in relations:
        if kind == 'S':
            require(not any(q('SELECT has_sequence_privilege(%s,%s)',(oid,p)).fetchone()[0] for p in ('USAGE','SELECT','UPDATE')), 'SEQUENCE_AUTHORITY')
            continue
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'):
            effective, grantable = q('SELECT has_table_privilege(%s,%s),has_table_privilege(%s,%s)',(oid,privilege,oid,privilege+' WITH GRANT OPTION')).fetchone()
            allowed = schema==config.schema and privilege in tables[name]
            require(effective==allowed and not grantable, 'TABLE_GRANT:'+schema+'.'+name+':'+privilege)
            table_facts.append([schema,name,privilege,effective,grantable])
        columns = q('SELECT attname FROM pg_attribute WHERE attrelid=%s AND attnum>0 AND NOT attisdropped ORDER BY attname',(oid,)).fetchall()
        if schema==config.schema:
            require({r[0] for r in columns}==expected[name], 'COLUMNS')
        for (column,) in columns:
            for privilege in ('SELECT','INSERT','UPDATE','REFERENCES'):
                effective, grantable=q('SELECT has_column_privilege(%s,%s,%s),has_column_privilege(%s,%s,%s)',(oid,column,privilege,oid,column,privilege+' WITH GRANT OPTION')).fetchone()
                allowed = schema==config.schema and (privilege in tables[name] or privilege=='UPDATE' and column in updates.get(name,set()))
                require(effective==allowed and not grantable,'COLUMN_GRANT:'+schema+'.'+name+'.'+column+':'+privilege)
                column_facts.append([schema,name,column,privilege,effective,grantable])
    functions=q("SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),p.prosecdef,has_function_privilege(p.oid,'EXECUTE'),has_schema_privilege(n.oid,'USAGE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' ORDER BY 1,2,3").fetchall()
    for schema,name,args,definer,execute,usage in functions:
        require(not definer and (not (execute and usage) or schema==config.schema), 'FUNCTION_PATH')
    control=q("SELECT proacl::text,has_function_privilege(oid,'EXECUTE') FROM pg_proc WHERE oid='pg_catalog.pg_control_system()'::regprocedure").fetchone()
    system_grants=q("SELECT p.proname,x.privilege_type,x.is_grantable FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) x WHERE n.nspname='pg_catalog' AND x.grantee=current_user::regrole").fetchall()
    parameter_grants=q("SELECT parname,x.privilege_type FROM pg_parameter_acl CROSS JOIN LATERAL aclexplode(paracl) x WHERE x.grantee IN (0,current_user::regrole)").fetchall()
    verify_system_acl(control[0],system_grants,parameter_grants)
    require(not q("SELECT 1 FROM pg_default_acl WHERE defaclrole IN (current_user::regrole,'doi_pin_migrator'::regrole)").fetchall(), 'DEFAULT_ACL_DRIFT')
    trigger=q("SELECT t.tgtype,t.tgenabled,p.proname,p.prosecdef FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname=%s AND c.relname='audit_events' AND t.tgname='audit_append_only' AND NOT t.tgisinternal",(config.schema,)).fetchall()
    require(trigger==[(27,'O','reject_audit_change',False)], 'APPEND_ONLY_TRIGGER')
    require(not q("SELECT 1 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid LEFT JOIN pg_class f ON f.oid=k.confrelid WHERE c.relnamespace=%s::regnamespace AND (NOT k.convalidated OR k.contype='f' AND f.relnamespace<>c.relnamespace)",(config.schema,)).fetchall(), 'CONSTRAINT_SCOPE')
    db=q("SELECT has_database_privilege(current_database(),'CONNECT'),has_database_privilege(current_database(),'CREATE'),has_database_privilege(current_database(),'TEMP')").fetchone()
    require(db[0] and not db[1], 'DATABASE_AUTHORITY')
    return dict(accepted=True,role=config.role,schemas=schemas,tables=table_facts,columns=column_facts,functions=functions,
                revision=REVISION,public_connect=db[0],residual_public_temp=db[2],permanent_ddl=False,
                application_cross_schema_access=False,audit_trigger=trigger,role_memberships=memberships,
                control_metadata=dict(default_public_execute=control[1],acl=control[0],new_runtime_grants=False,identity_authority='SEPARATE_TRUSTED_SESSION'))


def admit(config, authority, runtime):
    """Fresh collectors on two distinct live sessions, never caller-supplied facts."""
    require(authority is not runtime, 'SEPARATE_AUTHORITY')
    identity=collect_identity(config, authority)
    return dict(identity=identity, runtime=collect_runtime(config, runtime))
