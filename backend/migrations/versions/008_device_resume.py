"""A consumed pair code resumes only with a separate device capability."""
from alembic import op

revision='008_device_resume'
down_revision='007_memory_sync'
branch_labels=None
depends_on=None

def upgrade():
    s=op.get_context().config.attributes['schema']
    op.execute(f'ALTER TABLE {s}.session_devices ADD COLUMN resume_hash TEXT, ADD COLUMN resume_expires_at TIMESTAMPTZ, ADD COLUMN connection_id TEXT')

def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
