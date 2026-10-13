"""Per-account BYOB configuration; credentials are encrypted outside audit data."""
from alembic import op
revision='012_provider_settings'
down_revision='011_socket_tickets'
branch_labels=None
depends_on=None

def upgrade():
    schema=op.get_context().config.attributes['schema']
    op.execute(f'''CREATE TABLE {schema}.provider_settings (
        user_id TEXT PRIMARY KEY REFERENCES {schema}.users(id) ON DELETE CASCADE,
        settings JSONB NOT NULL DEFAULT '{{}}',
        credentials TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )''')

def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
