"""Represent the user's simulation approval without claiming team approval (P0-01)."""
from alembic import op

revision = '0002_user_approval'
down_revision = '0001_baseline'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE demo_policies DROP CONSTRAINT demo_policies_review_status_check')
    op.execute("ALTER TABLE demo_policies ADD CONSTRAINT demo_policies_review_status_check CHECK (review_status IN ('PROPOSED','TEAM_CONFIRMED','APPROVED_FOR_SIMULATION_BY_USER'))")
    op.execute("ALTER TABLE demo_policies ADD COLUMN approval_evidence jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("""CREATE FUNCTION reject_audit_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'audit_events is append-only'; END $$""")
    op.execute('CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION reject_audit_change()')
    op.execute("""CREATE FUNCTION reject_policy_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Policy revisions are immutable; insert a new revision'; END $$""")
    op.execute('CREATE TRIGGER policy_immutable BEFORE UPDATE OR DELETE ON demo_policies FOR EACH ROW EXECUTE FUNCTION reject_policy_change()')


def downgrade():
    raise RuntimeError('Destructive downgrade disabled. Use a reviewed forward migration.')
