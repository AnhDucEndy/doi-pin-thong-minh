"""B1a storage only. No eligibility backfill, provider dispatch or demo upgrade."""
from alembic import op

revision = '0009_refund_foundation'
down_revision = '0008_recovery_reconciliation'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE FUNCTION guard_refund_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE charge payments%ROWTYPE;
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Refund history is retained'; END IF;
      IF TG_OP='UPDATE' THEN
        IF ROW(NEW.id,NEW.payment_id,NEW.requested_by,NEW.provider_key,NEW.amount_minor,NEW.reason,NEW.created_at)
          IS DISTINCT FROM ROW(OLD.id,OLD.payment_id,OLD.requested_by,OLD.provider_key,OLD.amount_minor,OLD.reason,OLD.created_at)
          OR (OLD.provider_reference IS NOT NULL AND NEW.provider_reference IS DISTINCT FROM OLD.provider_reference)
          OR (OLD.state='SUCCEEDED' AND NEW.state<>'SUCCEEDED')
        THEN RAISE EXCEPTION 'Immutable refund identity or terminal result'; END IF;
        IF NEW.version<>OLD.version+1 THEN RAISE EXCEPTION 'Refund version must advance once'; END IF;
        IF NEW.state<>OLD.state AND NOT (
          (OLD.state='REQUESTED' AND NEW.state IN ('PENDING','UNKNOWN')) OR
          (OLD.state='PENDING' AND NEW.state IN ('UNKNOWN','FAILED','SUCCEEDED')) OR
          (OLD.state='UNKNOWN' AND NEW.state IN ('FAILED','SUCCEEDED')))
        THEN RAISE EXCEPTION 'Refund transition requires verified provider retry authority'; END IF;
      ELSE
        SELECT * INTO STRICT charge FROM payments WHERE id=NEW.payment_id;
        IF charge.state<>'SUCCEEDED' OR charge.verified_at IS NULL OR charge.provider_reference IS NULL
          OR charge.currency<>'VND' OR NEW.amount_minor<>charge.amount_minor
        THEN RAISE EXCEPTION 'Refund must bind the full verified charge'; END IF;
      END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER refund_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON refunds FOR EACH ROW EXECUTE FUNCTION guard_refund_identity()')
    op.execute('''CREATE TABLE refund_attempts (
      id uuid PRIMARY KEY, refund_id uuid NOT NULL REFERENCES refunds(id),
      generation integer NOT NULL CHECK(generation>=0), permit_id uuid,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(refund_id,generation), UNIQUE(refund_id,id,generation),
      CHECK ((generation=0 AND permit_id IS NULL) OR (generation>0 AND permit_id IS NOT NULL)))''')
    op.execute('''CREATE TABLE refund_retry_permissions (
      id uuid PRIMARY KEY, refund_id uuid NOT NULL REFERENCES refunds(id),
      prior_attempt_id uuid NOT NULL, prior_generation integer NOT NULL CHECK(prior_generation>=0),
      attempt_id uuid NOT NULL UNIQUE, generation integer NOT NULL,
      issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
      payload jsonb NOT NULL, payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      UNIQUE(refund_id,generation), CHECK(generation=prior_generation+1),
      CHECK(attempt_id<>prior_attempt_id), CHECK(expires_at>issued_at),
      FOREIGN KEY(refund_id,prior_attempt_id,prior_generation) REFERENCES refund_attempts(refund_id,id,generation))''')
    op.execute('ALTER TABLE refund_attempts ADD CONSTRAINT refund_attempt_permit_fk FOREIGN KEY(permit_id) REFERENCES refund_retry_permissions(id)')
    op.execute('''CREATE TABLE refund_permit_redemptions (
      permit_id uuid PRIMARY KEY REFERENCES refund_retry_permissions(id),
      attempt_id uuid NOT NULL UNIQUE REFERENCES refund_attempts(id),
      redeemed_at timestamptz NOT NULL)''')
    op.execute('''CREATE FUNCTION guard_refund_attempt_binding() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE permission refund_retry_permissions%ROWTYPE;
    BEGIN
      IF NEW.generation>0 THEN
        SELECT * INTO STRICT permission FROM refund_retry_permissions WHERE id=NEW.permit_id;
        IF ROW(NEW.refund_id,NEW.id,NEW.generation) IS DISTINCT FROM
           ROW(permission.refund_id,permission.attempt_id,permission.generation)
        THEN RAISE EXCEPTION 'Refund attempt/permit binding mismatch'; END IF;
      END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER refund_attempt_binding BEFORE INSERT ON refund_attempts FOR EACH ROW EXECUTE FUNCTION guard_refund_attempt_binding()')
    op.execute('''CREATE FUNCTION guard_refund_redemption() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE permission refund_retry_permissions%ROWTYPE;
    BEGIN
      SELECT * INTO STRICT permission FROM refund_retry_permissions WHERE id=NEW.permit_id;
      IF NEW.attempt_id<>permission.attempt_id OR NEW.redeemed_at<permission.issued_at
        OR NEW.redeemed_at>=permission.expires_at
      THEN RAISE EXCEPTION 'Refund permit redemption mismatch or expiry'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER refund_redemption_binding BEFORE INSERT ON refund_permit_redemptions FOR EACH ROW EXECUTE FUNCTION guard_refund_redemption()')
    for table in ('refund_attempts', 'refund_retry_permissions', 'refund_permit_redemptions'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')
        op.execute(f'GRANT SELECT, INSERT ON {table} TO doi_pin_runtime')
    op.execute('GRANT SELECT, INSERT ON refunds TO doi_pin_runtime')
    op.execute('GRANT UPDATE (state,version,provider_reference,verified_at) ON refunds TO doi_pin_runtime')
    # Relationships reserved for B1b; runtime has SELECT only, no issuer yet.
    # Existing 0.1/0.2 evidence cannot be inserted as a no-delivery certificate.
    op.execute('ALTER TABLE refunds ADD CONSTRAINT refund_identity_payment UNIQUE(id,payment_id)')
    op.execute('''CREATE TABLE refund_eligibility_certificates (
      id uuid PRIMARY KEY, operation_id uuid NOT NULL UNIQUE REFERENCES recovery_operations(id),
      payment_id uuid NOT NULL REFERENCES payments(id),
      receipt_id uuid NOT NULL REFERENCES recovery_attestations(id),
      technician_attestation_id uuid NOT NULL REFERENCES recovery_attestations(id),
      customer_attestation_id uuid NOT NULL REFERENCES recovery_attestations(id),
      validated_at timestamptz NOT NULL, valid_until timestamptz NOT NULL,
      payload jsonb NOT NULL, payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      UNIQUE(id,payment_id), CHECK(valid_until>validated_at))''')
    op.execute('''CREATE TABLE refund_certificate_redemptions (
      certificate_id uuid PRIMARY KEY, refund_id uuid NOT NULL, payment_id uuid NOT NULL,
      redeemed_at timestamptz NOT NULL,
      FOREIGN KEY(certificate_id,payment_id) REFERENCES refund_eligibility_certificates(id,payment_id),
      FOREIGN KEY(refund_id,payment_id) REFERENCES refunds(id,payment_id))''')
    op.execute('''CREATE FUNCTION guard_refund_certificate_protocol() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM recovery_operations o JOIN payments p ON p.id=NEW.payment_id
        WHERE o.id=NEW.operation_id AND o.protocol_version='0.3' AND o.purpose='VERIFY_NO_DELIVERY'
        AND o.swap_id=p.swap_id)
      THEN RAISE EXCEPTION 'Certificate requires a no-delivery operation for this charge'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER refund_certificate_protocol BEFORE INSERT ON refund_eligibility_certificates FOR EACH ROW EXECUTE FUNCTION guard_refund_certificate_protocol()')
    for table in ('refund_eligibility_certificates', 'refund_certificate_redemptions'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')
        op.execute(f'GRANT SELECT ON {table} TO doi_pin_runtime')


def downgrade():
    raise RuntimeError('Refund and permission history must be retained; forward migrations only.')
