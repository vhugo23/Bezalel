"""Persist checked learning content and idempotent claim-derived follow-ups."""
from alembic import op

revision = '003_learning_loop'
down_revision = '002_ordered_mastery'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE prepcrew.lessons ADD COLUMN title TEXT NOT NULL DEFAULT 'Your next practice'")
    op.execute("ALTER TABLE prepcrew.lessons ADD COLUMN practice TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE prepcrew.lessons ADD COLUMN retest_prompt TEXT")
    op.execute("ALTER TABLE prepcrew.lessons ADD COLUMN expectations JSONB NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE prepcrew.lessons ADD COLUMN check_job_id TEXT REFERENCES prepcrew.generation_jobs(id)")
    op.execute("CREATE UNIQUE INDEX lessons_claim_once ON prepcrew.lessons(claim_id) WHERE claim_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX retest_claim_once ON prepcrew.retest_queue(claim_id) WHERE claim_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX memories_claim_once ON prepcrew.memories(source_claim_id) WHERE source_claim_id IS NOT NULL")


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
