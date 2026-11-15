"""Transport acknowledgment is not a physical receipt or permission to move."""
from alembic import op

revision = '0006_authorization_ack'
down_revision = '0005_inspection_inbox'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE recovery_authorization_acks (
      id uuid PRIMARY KEY,
      authorization_id uuid NOT NULL UNIQUE REFERENCES recovery_action_authorizations(id),
      event_id uuid NOT NULL UNIQUE,
      device_id uuid NOT NULL REFERENCES devices(id),
      boot_id uuid NOT NULL, seq bigint NOT NULL CHECK(seq>0),
      observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      UNIQUE(device_id,boot_id,seq))''')
    op.execute('CREATE TRIGGER recovery_authorization_ack_immutable BEFORE UPDATE OR DELETE ON recovery_authorization_acks FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')


def downgrade():
    raise RuntimeError('Authorization acknowledgments must be retained; use a reviewed forward migration.')
