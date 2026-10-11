"""Durable orchestration, separate from per-model-call generation audit."""
from alembic import op

revision = '005_work_items'
down_revision = '004_session_steps'
branch_labels = None
depends_on = None


def upgrade():
    schema = op.get_context().config.attributes['schema']
    op.execute(f'''CREATE TABLE {schema}.work_items (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES {schema}.users(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        cache_key TEXT NOT NULL,
        payload JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
        stage TEXT NOT NULL DEFAULT 'Queued',
        result JSONB,
        error TEXT,
        attempts SMALLINT NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at TIMESTAMPTZ,
        UNIQUE(user_id,kind,cache_key)
    )''')
    op.execute(f"CREATE INDEX work_items_queue ON {schema}.work_items(created_at) WHERE status IN ('queued','running')")
    op.execute(f'ALTER TABLE {schema}.generation_jobs ADD COLUMN work_item_id TEXT REFERENCES {schema}.work_items(id) ON DELETE SET NULL')
    op.execute(f'CREATE INDEX generation_jobs_work_item ON {schema}.generation_jobs(work_item_id) WHERE work_item_id IS NOT NULL')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
