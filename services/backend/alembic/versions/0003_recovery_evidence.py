"""P8-REC-0.1: immutable recovery contexts and append-only attestations.

No evidence/custody backfill. Existing cases retain their original meaning.
"""
from alembic import op

revision = '0003_recovery_evidence'
down_revision = '0002_user_approval'
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE recovery_operations (
      id uuid PRIMARY KEY,
      case_id uuid NOT NULL REFERENCES recovery_cases(id),
      swap_id uuid NOT NULL REFERENCES swap_transactions(id),
      station_id uuid NOT NULL REFERENCES stations(id),
      customer_id uuid NOT NULL REFERENCES users(id),
      pin_id uuid REFERENCES batteries(id),
      expected_serial text NOT NULL CHECK (length(expected_serial) > 0),
      purpose text NOT NULL CHECK (purpose IN ('VERIFY_OLD_POSSESSION',
        'RETURN_OLD_TO_CUSTOMER','VERIFY_NEW_DELIVERY','RETURN_FOREIGN_OBJECT','RESUME_SWAP')),
      context jsonb NOT NULL CHECK (jsonb_typeof(context) = 'object'),
      context_hash text NOT NULL CHECK (context_hash ~ '^[0-9a-f]{64}$'),
      created_by uuid NOT NULL REFERENCES users(id),
      created_at timestamptz NOT NULL,
      expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
      base_case_version integer NOT NULL CHECK (base_case_version > 0),
      base_swap_version integer NOT NULL CHECK (base_swap_version > 0),
      supersedes_id uuid REFERENCES recovery_operations(id),
      consumed_at timestamptz,
      cancelled_at timestamptz,
      CHECK (created_by <> customer_id),
      CHECK ((purpose = 'RETURN_FOREIGN_OBJECT') = (pin_id IS NULL)),
      CHECK (consumed_at IS NULL OR cancelled_at IS NULL),
      CHECK (consumed_at IS NULL OR consumed_at >= created_at),
      CHECK (cancelled_at IS NULL OR cancelled_at >= created_at)
    )""")
    op.execute('CREATE UNIQUE INDEX recovery_operation_active ON recovery_operations(case_id, purpose) WHERE consumed_at IS NULL AND cancelled_at IS NULL')
    op.execute('CREATE INDEX recovery_operation_station ON recovery_operations(station_id, created_at)')
    op.execute('CREATE INDEX recovery_operation_swap ON recovery_operations(swap_id)')
    op.execute("""CREATE TABLE recovery_attestations (
      id uuid PRIMARY KEY,
      event_id uuid NOT NULL UNIQUE,
      operation_id uuid NOT NULL REFERENCES recovery_operations(id),
      source_kind text NOT NULL CHECK (source_kind IN ('SIMULATOR','TECHNICIAN','CUSTOMER')),
      actor_user_id uuid REFERENCES users(id),
      device_id uuid REFERENCES devices(id),
      observed_at timestamptz NOT NULL,
      received_at timestamptz NOT NULL,
      payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
      payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
      source_boot uuid,
      source_seq bigint CHECK (source_seq > 0),
      source_event_id uuid REFERENCES device_events(id),
      UNIQUE(operation_id, source_kind),
      UNIQUE(device_id, source_boot, source_seq),
      CHECK ((source_kind = 'SIMULATOR' AND device_id IS NOT NULL
         AND actor_user_id IS NULL AND source_boot IS NOT NULL AND source_seq IS NOT NULL)
        OR (source_kind IN ('TECHNICIAN','CUSTOMER') AND actor_user_id IS NOT NULL
         AND device_id IS NULL AND source_boot IS NULL AND source_seq IS NULL))
    )""")
    op.execute('CREATE TRIGGER recovery_attestations_append_only BEFORE UPDATE OR DELETE ON recovery_attestations FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')
    op.execute('ALTER TABLE recovery_cases ADD COLUMN operation_id uuid REFERENCES recovery_operations(id)')
    op.execute('CREATE INDEX recovery_case_operation ON recovery_cases(operation_id) WHERE operation_id IS NOT NULL')
    op.execute("""CREATE FUNCTION protect_recovery_operation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Recovery history is immutable'; END IF;
        IF (to_jsonb(NEW) - 'consumed_at' - 'cancelled_at') IS DISTINCT FROM
           (to_jsonb(OLD) - 'consumed_at' - 'cancelled_at')
           OR OLD.consumed_at IS NOT NULL OR OLD.cancelled_at IS NOT NULL THEN
          RAISE EXCEPTION 'Recovery context is immutable';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER recovery_operation_immutable BEFORE UPDATE OR DELETE ON recovery_operations FOR EACH ROW EXECUTE FUNCTION protect_recovery_operation()')


def downgrade():
    raise RuntimeError('Recovery evidence must be retained. Use a reviewed forward migration.')
