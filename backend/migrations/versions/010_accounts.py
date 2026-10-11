"""Password accounts, revocable sessions and bounded authentication attempts."""
from alembic import op

revision='010_accounts'
down_revision='009_pi_linux'
branch_labels=None
depends_on=None


def upgrade():
    schema=op.get_context().config.attributes['schema']
    op.execute(f'''CREATE TABLE {schema}.accounts (
        user_id TEXT PRIMARY KEY REFERENCES {schema}.users(id) ON DELETE CASCADE,
        email TEXT NOT NULL UNIQUE CHECK(email=lower(email)),
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )''')
    op.execute(f'''CREATE TABLE {schema}.auth_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES {schema}.accounts(user_id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute(f'CREATE INDEX auth_sessions_user ON {schema}.auth_sessions(user_id)')
    op.execute(f'CREATE INDEX auth_sessions_expiry ON {schema}.auth_sessions(expires_at)')
    op.execute(f'''CREATE TABLE {schema}.auth_attempts (
        key TEXT PRIMARY KEY,
        attempts INTEGER NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute(f'CREATE INDEX auth_attempts_expiry ON {schema}.auth_attempts(expires_at)')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
