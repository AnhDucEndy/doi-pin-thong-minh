"""P8-REC-0.2 storage only: stage-bound immutable proof and one permit per operation.

No custody backfill and no authorization is inferred from legacy attestations.
"""
from alembic import op

revision = '0004_recovery_stages'
down_revision = '0003_recovery_evidence'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE recovery_operations ADD COLUMN protocol_version text CHECK (protocol_version IS NULL OR protocol_version = '0.2')")
    op.execute("ALTER TABLE recovery_operations ADD CONSTRAINT recovery_protocol_purpose CHECK (protocol_version IS NULL OR purpose = 'RETURN_FOREIGN_OBJECT')")
    op.execute("ALTER TABLE recovery_attestations ADD COLUMN stage text NOT NULL DEFAULT 'LEGACY' CHECK (stage IN ('LEGACY','PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT'))")
    op.execute('ALTER TABLE recovery_attestations ADD COLUMN reference_receipt_id uuid REFERENCES recovery_attestations(id)')
    op.execute('ALTER TABLE recovery_attestations DROP CONSTRAINT recovery_attestations_operation_id_source_kind_key')
    op.execute('ALTER TABLE recovery_attestations ADD CONSTRAINT recovery_attestation_stage_source UNIQUE(operation_id,stage,source_kind)')
    op.execute('CREATE INDEX recovery_attestation_stage_time ON recovery_attestations(operation_id,stage,received_at)')
    op.execute('CREATE INDEX recovery_attestation_reference ON recovery_attestations(reference_receipt_id)')
    op.execute("""CREATE FUNCTION validate_recovery_stage() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE context recovery_operations%ROWTYPE; receipt recovery_attestations%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT context FROM recovery_operations WHERE id=NEW.operation_id;
        IF (context.protocol_version IS NULL) <> (NEW.stage='LEGACY') THEN
          RAISE EXCEPTION 'Recovery protocol/stage mismatch';
        END IF;
        IF NEW.stage='LEGACY' THEN
          IF NEW.reference_receipt_id IS NOT NULL THEN RAISE EXCEPTION 'Legacy receipt reference forbidden'; END IF;
        ELSIF NEW.source_kind='SIMULATOR' THEN
          IF NEW.reference_receipt_id IS NOT NULL THEN RAISE EXCEPTION 'Device receipt cannot attest to another receipt'; END IF;
        ELSE
          IF NEW.reference_receipt_id IS NULL THEN RAISE EXCEPTION 'Stage receipt reference required'; END IF;
          SELECT * INTO STRICT receipt FROM recovery_attestations WHERE id=NEW.reference_receipt_id;
          IF receipt.operation_id<>NEW.operation_id OR receipt.stage<>NEW.stage OR receipt.source_kind<>'SIMULATOR'
            OR NEW.observed_at<receipt.received_at THEN
            RAISE EXCEPTION 'Recovery receipt scope/stage/chronology mismatch';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER recovery_attestation_stage BEFORE INSERT ON recovery_attestations FOR EACH ROW EXECUTE FUNCTION validate_recovery_stage()')
    op.execute("""CREATE TABLE recovery_action_authorizations (
      id uuid PRIMARY KEY, operation_id uuid NOT NULL UNIQUE REFERENCES recovery_operations(id),
      context_hash text NOT NULL CHECK(context_hash ~ '^[0-9a-f]{64}$'),
      inspection_id uuid NOT NULL REFERENCES recovery_attestations(id),
      technician_attestation_id uuid NOT NULL REFERENCES recovery_attestations(id),
      customer_attestation_id uuid NOT NULL REFERENCES recovery_attestations(id),
      device_id uuid NOT NULL REFERENCES devices(id), boot_id uuid NOT NULL,
      ledger_id uuid NOT NULL, fence_generation bigint NOT NULL CHECK(fence_generation>0),
      authorized_by uuid NOT NULL REFERENCES users(id), issued_at timestamptz NOT NULL,
      expires_at timestamptz NOT NULL CHECK(expires_at>issued_at),
      authorization_hash text NOT NULL CHECK(authorization_hash ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'), revoked_at timestamptz,
      CHECK(revoked_at IS NULL OR revoked_at>=issued_at)
    )""")
    op.execute('CREATE INDEX recovery_authorization_device_expiry ON recovery_action_authorizations(device_id,expires_at)')
    op.execute("""CREATE FUNCTION protect_recovery_authorization() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE context recovery_operations%ROWTYPE; proof recovery_attestations%ROWTYPE; item record;
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Recovery authorization history is immutable'; END IF;
        IF TG_OP='UPDATE' THEN
          IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL OR
             (to_jsonb(NEW)-'revoked_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at') THEN
            RAISE EXCEPTION 'Recovery authorization is immutable';
          END IF;
          RETURN NEW;
        END IF;
        SELECT * INTO STRICT context FROM recovery_operations WHERE id=NEW.operation_id;
        IF context.protocol_version IS DISTINCT FROM '0.2' OR context.context_hash<>NEW.context_hash
          OR context.created_by<>NEW.authorized_by OR context.expires_at<>NEW.expires_at
          OR context.consumed_at IS NOT NULL OR context.cancelled_at IS NOT NULL
          OR NEW.issued_at<context.created_at THEN RAISE EXCEPTION 'Invalid recovery authorization context'; END IF;
        FOR item IN SELECT * FROM (VALUES
            (NEW.inspection_id,'SIMULATOR'),(NEW.technician_attestation_id,'TECHNICIAN'),
            (NEW.customer_attestation_id,'CUSTOMER')) AS expected(id,source)
        LOOP
          SELECT * INTO STRICT proof FROM recovery_attestations WHERE id=item.id;
          IF proof.operation_id<>NEW.operation_id OR proof.stage<>'PRE_ACTION_INSPECTION'
            OR proof.source_kind<>item.source OR proof.received_at>NEW.issued_at THEN
            RAISE EXCEPTION 'Authorization requires operation pre-action proof';
          END IF;
          IF item.source='SIMULATOR' THEN
            IF proof.device_id<>NEW.device_id OR proof.source_boot<>NEW.boot_id THEN
              RAISE EXCEPTION 'Authorization device provenance mismatch';
            END IF;
          ELSE
            IF proof.reference_receipt_id<>NEW.inspection_id OR
              proof.actor_user_id<>(CASE WHEN item.source='TECHNICIAN' THEN context.created_by ELSE context.customer_id END) THEN
              RAISE EXCEPTION 'Authorization human proof mismatch';
            END IF;
          END IF;
        END LOOP;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER recovery_authorization_immutable BEFORE INSERT OR UPDATE OR DELETE ON recovery_action_authorizations FOR EACH ROW EXECUTE FUNCTION protect_recovery_authorization()')


def downgrade():
    raise RuntimeError('Stage evidence and authorizations must be retained; use a reviewed forward migration.')
