"""Deduplicate intake documents without mixing them with session evidence."""
from alembic import op

revision = '006_source_documents'
down_revision = '005_work_items'
branch_labels = None
depends_on = None


def upgrade():
    schema = op.get_context().config.attributes['schema']
    op.execute(f'ALTER TABLE {schema}.source_documents ADD COLUMN content_hash TEXT')
    op.execute(f'CREATE UNIQUE INDEX source_documents_content_once ON {schema}.source_documents(user_id,kind,content_hash) WHERE content_hash IS NOT NULL')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
