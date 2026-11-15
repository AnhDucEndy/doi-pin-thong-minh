"""Approved ER-01/ER-02 evidence; no custody or historical evidence backfill."""
from alembic import op

revision = '0008_recovery_reconciliation'
down_revision = '0007_recovery_activation'
branch_labels = depends_on = None


def upgrade():
    # One effect-capable operation per purpose, plus at most one independent
    # read-only witness for its predecessor. Keep both live until chain commit.
    op.execute('DROP INDEX recovery_operation_active')
    op.execute("""CREATE UNIQUE INDEX recovery_operation_active ON recovery_operations(case_id,purpose)
        WHERE consumed_at IS NULL AND cancelled_at IS NULL AND NOT (context ? 'reconciliation_only')""")
    op.execute("""CREATE UNIQUE INDEX recovery_operation_one_reinspection ON recovery_operations(supersedes_id)
        WHERE consumed_at IS NULL AND cancelled_at IS NULL AND context ? 'reconciliation_only'""")
    op.execute("""ALTER TABLE recovery_operations ADD CONSTRAINT recovery_readonly_context
        CHECK (NOT (context ? 'reconciliation_only') OR
        (protocol_version IS NOT DISTINCT FROM '0.2' AND supersedes_id IS NOT NULL
        AND context @> jsonb_build_object('reconciliation_only',true)
        AND context->>'predecessor_id' IS NOT DISTINCT FROM supersedes_id::text))""")
    op.execute("""CREATE FUNCTION validate_reinspection_chain() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE predecessor recovery_operations%ROWTYPE; permit recovery_action_authorizations%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT predecessor FROM recovery_operations WHERE id=NEW.supersedes_id FOR UPDATE;
        SELECT * INTO STRICT permit FROM recovery_action_authorizations WHERE operation_id=predecessor.id;
        IF predecessor.protocol_version IS DISTINCT FROM '0.2' OR predecessor.context ? 'reconciliation_only'
           OR predecessor.consumed_at IS NOT NULL OR predecessor.cancelled_at IS NOT NULL
           OR NEW.created_at<predecessor.expires_at OR NEW.case_id<>predecessor.case_id
           OR NEW.swap_id<>predecessor.swap_id OR NEW.station_id<>predecessor.station_id
           OR NEW.customer_id<>predecessor.customer_id OR NEW.created_by<>predecessor.created_by
           OR NEW.expected_serial<>predecessor.expected_serial
           OR NEW.context->>'predecessor_context_hash' IS DISTINCT FROM predecessor.context_hash
           OR NEW.context->>'predecessor_authorization_id' IS DISTINCT FROM permit.id::text
           OR NEW.context->>'predecessor_authorization_hash' IS DISTINCT FROM permit.authorization_hash
        THEN RAISE EXCEPTION 'Invalid read-only predecessor chain'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER recovery_reinspection_chain BEFORE INSERT ON recovery_operations
        FOR EACH ROW WHEN (NEW.context ? 'reconciliation_only') EXECUTE FUNCTION validate_reinspection_chain()""")
    op.execute("""CREATE FUNCTION deny_readonly_authorization() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF EXISTS(SELECT 1 FROM recovery_operations WHERE id=NEW.operation_id AND context ? 'reconciliation_only')
        THEN RAISE EXCEPTION 'Read-only inspection cannot authorize an action'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER recovery_readonly_no_permit BEFORE INSERT ON recovery_action_authorizations
        FOR EACH ROW EXECUTE FUNCTION deny_readonly_authorization()""")
    op.execute('ALTER TABLE recovery_attestations DROP CONSTRAINT recovery_attestations_stage_check')
    op.execute("ALTER TABLE recovery_attestations ADD CONSTRAINT recovery_attestations_stage_check CHECK (stage IN ('LEGACY','PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT','RECONCILIATION_INSPECTION'))")
    # Same-operation/stage reference trigger remains in force for successor witnesses.
    op.execute('''CREATE TABLE recovery_closure_intents (
      id uuid PRIMARY KEY, operation_id uuid NOT NULL UNIQUE REFERENCES recovery_operations(id),
      created_by uuid NOT NULL REFERENCES users(id), auth_session_id uuid NOT NULL REFERENCES auth_sessions(id),
      created_at timestamptz NOT NULL, payload jsonb NOT NULL,
      payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'))''')
    op.execute('''CREATE TABLE recovery_closure_receipts (
      id uuid PRIMARY KEY, closure_id uuid NOT NULL UNIQUE REFERENCES recovery_closure_intents(id),
      event_id uuid NOT NULL UNIQUE, device_id uuid NOT NULL REFERENCES devices(id),
      boot_id uuid NOT NULL, seq bigint NOT NULL CHECK(seq>0),
      observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL,
      payload jsonb NOT NULL, payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      UNIQUE(device_id,boot_id,seq))''')
    for table in ('recovery_closure_intents', 'recovery_closure_receipts'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')


def downgrade():
    raise RuntimeError('Closure and reconciliation history must be retained.')
