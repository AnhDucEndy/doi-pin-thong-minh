"""B1b readonly no-delivery storage; no data/proof/issuer backfill."""
from alembic import op

revision = '0010_no_delivery_eligibility'
down_revision = '0009_refund_foundation'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE recovery_operations DROP CONSTRAINT recovery_operations_purpose_check')
    op.execute("""ALTER TABLE recovery_operations ADD CONSTRAINT recovery_operations_purpose_check
      CHECK(purpose IN ('VERIFY_OLD_POSSESSION','RETURN_OLD_TO_CUSTOMER','VERIFY_NEW_DELIVERY',
                       'RETURN_FOREIGN_OBJECT','RESUME_SWAP','VERIFY_NO_DELIVERY'))""")
    op.execute('ALTER TABLE recovery_operations DROP CONSTRAINT recovery_operations_protocol_version_check')
    op.execute("""ALTER TABLE recovery_operations ADD CONSTRAINT recovery_operations_protocol_version_check
      CHECK(protocol_version IS NULL OR protocol_version IN ('0.2','0.3'))""")
    op.execute('ALTER TABLE recovery_operations DROP CONSTRAINT recovery_protocol_purpose')
    # IS NOT DISTINCT FROM is deliberate: NULL must not admit a 0.3 purpose.
    op.execute("""ALTER TABLE recovery_operations ADD CONSTRAINT recovery_protocol_purpose CHECK(
      (protocol_version IS NULL AND purpose IN ('VERIFY_OLD_POSSESSION','RETURN_OLD_TO_CUSTOMER',
        'VERIFY_NEW_DELIVERY','RETURN_FOREIGN_OBJECT','RESUME_SWAP')) OR
      (protocol_version IS NOT DISTINCT FROM '0.2' AND purpose='RETURN_FOREIGN_OBJECT') OR
      (protocol_version IS NOT DISTINCT FROM '0.3' AND purpose='VERIFY_NO_DELIVERY'))""")
    op.execute('ALTER TABLE recovery_attestations DROP CONSTRAINT recovery_attestations_stage_check')
    op.execute("""ALTER TABLE recovery_attestations ADD CONSTRAINT recovery_attestations_stage_check
      CHECK(stage IN ('LEGACY','PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT',
                      'RECONCILIATION_INSPECTION','NO_DELIVERY_INSPECTION'))""")
    op.execute("""CREATE FUNCTION validate_no_delivery_operation() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE s swap_transactions%ROWTYPE; c recovery_cases%ROWTYPE;
      BEGIN
        IF NEW.protocol_version IS DISTINCT FROM '0.3' THEN RETURN NEW; END IF;
        SELECT * INTO STRICT s FROM swap_transactions WHERE id=NEW.swap_id;
        SELECT * INTO STRICT c FROM recovery_cases WHERE id=NEW.case_id;
        IF NEW.purpose<>'VERIFY_NO_DELIVERY' OR NEW.pin_id IS DISTINCT FROM s.new_battery_id
          OR NEW.station_id<>s.station_id OR NEW.customer_id<>s.customer_id OR c.swap_id<>s.id
          OR NEW.context->>'protocol_version' IS DISTINCT FROM '0.3'
          OR NEW.context->>'purpose' IS DISTINCT FROM 'VERIFY_NO_DELIVERY'
          OR NEW.context->>'operation_id' IS DISTINCT FROM NEW.id::text
          OR NEW.context->>'case_id' IS DISTINCT FROM c.id::text
          OR NEW.context->>'swap_id' IS DISTINCT FROM s.id::text
          OR NEW.context->>'station_id' IS DISTINCT FROM s.station_id::text
          OR NEW.context->>'customer_id' IS DISTINCT FROM s.customer_id::text
          OR NEW.context->>'created_by' IS DISTINCT FROM NEW.created_by::text
          OR NEW.context->>'new_battery_id' IS DISTINCT FROM s.new_battery_id::text
          OR NEW.context->>'expected_serial' IS DISTINCT FROM NEW.expected_serial
          OR NEW.context->>'supply_compartment_id' IS DISTINCT FROM s.supply_compartment_id::text
          OR NEW.context->>'return_compartment_id' IS DISTINCT FROM s.return_compartment_id::text
          OR NEW.context->>'context_hash' IS DISTINCT FROM NEW.context_hash
          OR NEW.context ? 'reconciliation_only'
        THEN RAISE EXCEPTION 'Invalid no-delivery operation binding'; END IF;
        IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS(
          SELECT 1 FROM recovery_operations p WHERE p.id=NEW.supersedes_id
            AND p.protocol_version='0.3' AND p.purpose='VERIFY_NO_DELIVERY'
            AND p.case_id=NEW.case_id AND p.swap_id=NEW.swap_id AND p.station_id=NEW.station_id
            AND NEW.context->>'predecessor_id'=p.id::text
            AND NEW.context->>'predecessor_context_hash'=p.context_hash)
        THEN RAISE EXCEPTION 'Invalid no-delivery predecessor'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER no_delivery_operation_binding BEFORE INSERT ON recovery_operations
      FOR EACH ROW EXECUTE FUNCTION validate_no_delivery_operation()""")
    op.execute("""CREATE OR REPLACE FUNCTION validate_recovery_stage() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE context recovery_operations%ROWTYPE; receipt recovery_attestations%ROWTYPE;
              source device_events%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT context FROM recovery_operations WHERE id=NEW.operation_id;
        IF context.protocol_version IS NOT DISTINCT FROM '0.3' THEN
          IF NEW.stage<>'NO_DELIVERY_INSPECTION' OR context.purpose<>'VERIFY_NO_DELIVERY'
            OR NEW.payload->>'context_hash' IS DISTINCT FROM context.context_hash
          THEN RAISE EXCEPTION 'No-delivery stage/context mismatch'; END IF;
        ELSE
          IF NEW.stage='NO_DELIVERY_INSPECTION'
            OR (context.protocol_version IS NULL) <> (NEW.stage='LEGACY')
          THEN RAISE EXCEPTION 'Recovery protocol/stage mismatch'; END IF;
        END IF;
        IF NEW.stage='LEGACY' THEN
          IF NEW.reference_receipt_id IS NOT NULL THEN RAISE EXCEPTION 'Legacy receipt reference forbidden'; END IF;
        ELSIF NEW.source_kind='SIMULATOR' THEN
          IF NEW.reference_receipt_id IS NOT NULL THEN RAISE EXCEPTION 'Device receipt cannot attest to another receipt'; END IF;
        ELSE
          IF NEW.reference_receipt_id IS NULL THEN RAISE EXCEPTION 'Stage receipt reference required'; END IF;
          SELECT * INTO STRICT receipt FROM recovery_attestations WHERE id=NEW.reference_receipt_id;
          IF receipt.operation_id<>NEW.operation_id OR receipt.stage<>NEW.stage OR receipt.source_kind<>'SIMULATOR'
            OR NEW.observed_at<receipt.received_at
          THEN RAISE EXCEPTION 'Recovery receipt scope/stage/chronology mismatch'; END IF;
        END IF;
        IF context.protocol_version IS NOT DISTINCT FROM '0.3' THEN
          IF NEW.source_kind='SIMULATOR' THEN
            SELECT * INTO STRICT source FROM device_events WHERE id=NEW.source_event_id;
            IF source.device_id<>NEW.device_id OR source.boot_id<>NEW.source_boot
              OR source.kind<>'SNAPSHOT' OR source.accepted IS DISTINCT FROM true OR source.processed_at IS NULL
              OR NEW.payload->>'snapshot_event_id' IS DISTINCT FROM source.id::text
              OR NEW.payload->>'snapshot_hash' IS DISTINCT FROM source.payload_hash
              OR NEW.payload->>'device_id' IS DISTINCT FROM NEW.device_id::text
              OR NOT EXISTS(SELECT 1 FROM devices d WHERE d.id=NEW.device_id AND d.station_id=context.station_id)
            THEN RAISE EXCEPTION 'No-delivery source provenance mismatch'; END IF;
          ELSIF NEW.actor_user_id<>(CASE WHEN NEW.source_kind='TECHNICIAN' THEN context.created_by ELSE context.customer_id END)
            OR NEW.payload->>'receipt_hash' IS DISTINCT FROM receipt.payload_hash
          THEN RAISE EXCEPTION 'No-delivery human binding mismatch'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    # Null private fields on historical rows remain null; no invented issuer.
    op.execute('ALTER TABLE refund_eligibility_certificates ADD COLUMN issued_by uuid REFERENCES users(id)')
    op.execute('ALTER TABLE refund_eligibility_certificates ADD COLUMN issuer_session_id uuid REFERENCES auth_sessions(id)')
    op.execute("""CREATE TABLE refund_certificate_revocations (
      id uuid PRIMARY KEY, certificate_id uuid NOT NULL UNIQUE REFERENCES refund_eligibility_certificates(id),
      revoked_at timestamptz NOT NULL, reason_code text NOT NULL CHECK(length(reason_code)>0),
      source_event_id uuid REFERENCES device_events(id), actor_user_id uuid REFERENCES users(id),
      correlation_id uuid NOT NULL)""")
    op.execute("""CREATE TRIGGER refund_certificate_revocations_immutable
      BEFORE UPDATE OR DELETE ON refund_certificate_revocations
      FOR EACH ROW EXECUTE FUNCTION reject_audit_change()""")
    op.execute("""CREATE OR REPLACE FUNCTION guard_refund_certificate_protocol() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE o recovery_operations%ROWTYPE; c recovery_cases%ROWTYPE;
              s swap_transactions%ROWTYPE; charge payments%ROWTYPE;
              sim recovery_attestations%ROWTYPE; tech recovery_attestations%ROWTYPE;
              customer recovery_attestations%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT o FROM recovery_operations WHERE id=NEW.operation_id;
        SELECT * INTO STRICT c FROM recovery_cases WHERE id=o.case_id;
        SELECT * INTO STRICT s FROM swap_transactions WHERE id=o.swap_id;
        SELECT * INTO STRICT charge FROM payments WHERE id=NEW.payment_id;
        SELECT * INTO STRICT sim FROM recovery_attestations WHERE id=NEW.receipt_id;
        SELECT * INTO STRICT tech FROM recovery_attestations WHERE id=NEW.technician_attestation_id;
        SELECT * INTO STRICT customer FROM recovery_attestations WHERE id=NEW.customer_attestation_id;
        IF o.protocol_version IS DISTINCT FROM '0.3' OR o.purpose<>'VERIFY_NO_DELIVERY'
          OR charge.swap_id<>o.swap_id OR charge.state<>'SUCCEEDED' OR charge.verified_at IS NULL
          OR charge.provider_reference IS NULL OR charge.currency<>'VND'
          OR c.operation_id IS DISTINCT FROM o.id OR c.new_pin_delivered<>'NO' OR c.state<>'EVIDENCE_RECORDED'
          OR o.consumed_at IS NOT NULL OR o.cancelled_at IS NOT NULL
          OR sim.operation_id<>o.id OR tech.operation_id<>o.id OR customer.operation_id<>o.id
          OR sim.stage<>'NO_DELIVERY_INSPECTION' OR tech.stage<>sim.stage OR customer.stage<>sim.stage
          OR sim.source_kind<>'SIMULATOR' OR tech.source_kind<>'TECHNICIAN' OR customer.source_kind<>'CUSTOMER'
          OR tech.reference_receipt_id IS DISTINCT FROM sim.id OR customer.reference_receipt_id IS DISTINCT FROM sim.id
          OR tech.actor_user_id<>o.created_by OR customer.actor_user_id<>o.customer_id
          OR tech.payload->>'confirm' IS DISTINCT FROM 'true' OR customer.payload->>'confirm' IS DISTINCT FROM 'true'
          OR NEW.issued_by IS NULL OR NEW.issuer_session_id IS NULL
          OR NOT EXISTS(SELECT 1 FROM users u JOIN auth_sessions a ON a.user_id=u.id
            JOIN user_station_assignments x ON x.user_id=u.id AND x.station_id=o.station_id
            WHERE u.id=NEW.issued_by AND u.role='TECHNICIAN' AND u.state='ACTIVE'
              AND a.id=NEW.issuer_session_id AND a.revoked_at IS NULL AND a.expires_at>NEW.validated_at)
          OR NEW.payload->>'protocol_version' IS DISTINCT FROM '0.3'
          OR NEW.payload->>'certificate_id' IS DISTINCT FROM NEW.id::text
          OR NEW.payload->>'operation_id' IS DISTINCT FROM o.id::text
          OR NEW.payload->>'context_hash' IS DISTINCT FROM o.context_hash
          OR NEW.payload->>'case_id' IS DISTINCT FROM c.id::text
          OR NEW.payload->>'case_version' IS DISTINCT FROM c.version::text
          OR NEW.payload->>'swap_id' IS DISTINCT FROM s.id::text
          OR NEW.payload->>'swap_version' IS DISTINCT FROM s.version::text
          OR NEW.payload->>'payment_id' IS DISTINCT FROM charge.id::text
          OR NEW.payload->>'receipt_id' IS DISTINCT FROM sim.id::text
          OR NEW.payload->>'receipt_hash' IS DISTINCT FROM sim.payload_hash
          OR NEW.payload->>'technician_attestation_id' IS DISTINCT FROM tech.id::text
          OR NEW.payload->>'customer_attestation_id' IS DISTINCT FROM customer.id::text
          OR NEW.payload->>'new_pin_delivered' IS DISTINCT FROM 'NO'
          OR NEW.payload->>'effect_count_delta' IS DISTINCT FROM '0'
          OR NEW.validated_at<GREATEST(sim.received_at,tech.received_at,customer.received_at)
          OR NEW.valid_until>LEAST(o.expires_at,sim.observed_at+interval '15 seconds',
            sim.received_at+interval '15 seconds',tech.observed_at+interval '15 seconds',
            tech.received_at+interval '15 seconds',customer.observed_at+interval '15 seconds',
            customer.received_at+interval '15 seconds')
        THEN RAISE EXCEPTION 'Certificate requires current bound no-delivery proof and issuer'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE FUNCTION validate_refund_certificate_redemption() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE cert refund_eligibility_certificates%ROWTYPE; intent refunds%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT cert FROM refund_eligibility_certificates WHERE id=NEW.certificate_id;
        SELECT * INTO STRICT intent FROM refunds WHERE id=NEW.refund_id;
        IF cert.payment_id<>NEW.payment_id OR intent.payment_id<>NEW.payment_id
          OR cert.issued_by IS NULL OR cert.issuer_session_id IS NULL
          OR NEW.redeemed_at<cert.validated_at OR NEW.redeemed_at>=cert.valid_until
          OR EXISTS(SELECT 1 FROM refund_certificate_revocations WHERE certificate_id=cert.id)
        THEN RAISE EXCEPTION 'Invalid certificate redemption binding or validity'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER refund_certificate_redemption_binding BEFORE INSERT ON refund_certificate_redemptions
      FOR EACH ROW EXECUTE FUNCTION validate_refund_certificate_redemption()""")
    for table in ('refund_eligibility_certificates', 'refund_certificate_redemptions', 'refund_certificate_revocations'):
        op.execute(f'GRANT SELECT, INSERT ON {table} TO doi_pin_runtime')


def downgrade():
    raise RuntimeError('No-delivery proof, issuer and revocation history must be retained.')
