"""Retain accepted AND refused inspection identities, without custody backfill."""
from alembic import op
revision = '0005_inspection_inbox'
down_revision = '0004_recovery_stages'
branch_labels = depends_on = None

def upgrade():
    op.execute('''CREATE TABLE recovery_inspection_inbox (
      event_id uuid PRIMARY KEY, device_id uuid NOT NULL REFERENCES devices(id),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL, status integer NOT NULL CHECK(status IN (202,409,422)),
      response jsonb NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp())''')
    op.execute('CREATE TRIGGER recovery_inspection_inbox_immutable BEFORE UPDATE OR DELETE ON recovery_inspection_inbox FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')

def downgrade():
    raise RuntimeError('Inspection history must be retained; use a reviewed forward migration.')
