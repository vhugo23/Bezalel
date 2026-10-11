"""Approved v2.3 schema and catalog, isolated from the legacy app."""
from pathlib import Path
from alembic import op

revision = '001_v23'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    sql = (Path(__file__).parents[1] / 'sql' / '001_v23.sql').read_text(encoding='utf-8')
    op.get_bind().connection.run_async(lambda driver: driver.execute('SET LOCAL search_path TO prepcrew, public;\n' + sql))

def downgrade():
    raise RuntimeError('Destructive downgrade disabled. Restore a reviewed backup instead.')
