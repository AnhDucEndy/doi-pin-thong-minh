"""One immutable action activation for an acknowledged no-effect intent."""
from alembic import op
revision = '0007_recovery_activation'
down_revision = '0006_authorization_ack'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE recovery_action_activations (
      id uuid PRIMARY KEY,
      authorization_id uuid NOT NULL UNIQUE REFERENCES recovery_action_authorizations(id),
      acknowledgment_id uuid NOT NULL UNIQUE REFERENCES recovery_authorization_acks(id),
      operation_id uuid NOT NULL UNIQUE REFERENCES recovery_operations(id),
      activated_by uuid NOT NULL REFERENCES users(id),
      issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL CHECK(expires_at>issued_at),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'))''')
    op.execute('''CREATE FUNCTION validate_recovery_activation() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE intent recovery_action_authorizations%ROWTYPE; ack recovery_authorization_acks%ROWTYPE;
      BEGIN
        SELECT * INTO STRICT intent FROM recovery_action_authorizations WHERE id=NEW.authorization_id;
        SELECT * INTO STRICT ack FROM recovery_authorization_acks WHERE id=NEW.acknowledgment_id;
        IF intent.operation_id<>NEW.operation_id OR ack.authorization_id<>intent.id
           OR intent.authorized_by<>NEW.activated_by OR intent.revoked_at IS NOT NULL
           OR NEW.expires_at<>intent.expires_at OR NEW.issued_at<ack.received_at THEN
          RAISE EXCEPTION 'Invalid activation intent/ack/context';
        END IF;
        RETURN NEW;
      END $$''')
    op.execute('CREATE TRIGGER recovery_activation_binding BEFORE INSERT ON recovery_action_activations FOR EACH ROW EXECUTE FUNCTION validate_recovery_activation()')
    op.execute('CREATE TRIGGER recovery_activation_immutable BEFORE UPDATE OR DELETE ON recovery_action_activations FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')


def downgrade():
    raise RuntimeError('Action history must be retained; use a reviewed forward migration.')
