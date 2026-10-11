"""Single-use scoped tickets for direct cross-host WebSocket upgrades."""
from alembic import op

revision = '011_socket_tickets'
down_revision = '010_accounts'
branch_labels = None
depends_on = None


def upgrade():
    schema = op.get_context().config.attributes['schema']
    op.execute(f'''CREATE TABLE {schema}.socket_tickets (
        token_hash TEXT PRIMARY KEY,
        auth_token_hash TEXT NOT NULL REFERENCES {schema}.auth_sessions(token_hash) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES {schema}.sessions(id) ON DELETE CASCADE,
        channel TEXT NOT NULL CHECK(channel IN ('events','voice')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute(f'CREATE INDEX socket_tickets_auth_expiry ON {schema}.socket_tickets(auth_token_hash,expires_at)')
    op.execute(f'CREATE INDEX socket_tickets_expiry ON {schema}.socket_tickets(expires_at)')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
