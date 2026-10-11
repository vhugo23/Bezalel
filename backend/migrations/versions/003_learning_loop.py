"""Persist checked learning content and idempotent claim-derived follow-ups."""
from alembic import op

revision = '003_learning_loop'
down_revision = '002_ordered_mastery'
branch_labels = None
depends_on = None


def upgrade():
    schema = op.get_context().config.attributes['schema']
    def execute(sql):
        op.execute(sql.replace('prepcrew.', schema + '.'))
    execute("ALTER TABLE prepcrew.lessons ADD COLUMN title TEXT NOT NULL DEFAULT 'Your next practice'")
    execute("ALTER TABLE prepcrew.lessons ADD COLUMN practice TEXT NOT NULL DEFAULT ''")
    execute("ALTER TABLE prepcrew.lessons ADD COLUMN retest_prompt TEXT")
    execute("ALTER TABLE prepcrew.lessons ADD COLUMN expectations JSONB NOT NULL DEFAULT '[]'")
    execute("ALTER TABLE prepcrew.lessons ADD COLUMN check_job_id TEXT REFERENCES prepcrew.generation_jobs(id)")
    execute("CREATE UNIQUE INDEX lessons_claim_once ON prepcrew.lessons(claim_id) WHERE claim_id IS NOT NULL")
    execute("CREATE UNIQUE INDEX retest_claim_once ON prepcrew.retest_queue(claim_id) WHERE claim_id IS NOT NULL")
    execute("CREATE UNIQUE INDEX memories_claim_once ON prepcrew.memories(source_claim_id) WHERE source_claim_id IS NOT NULL")


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
