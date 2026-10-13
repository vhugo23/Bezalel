"""Approved v2.3 schema and catalog, isolated from the legacy app."""
from pathlib import Path
from alembic import op

revision = '001_v23'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    sql = (Path(__file__).parents[1] / 'sql' / '001_v23.sql').read_text(encoding='utf-8')
    if not op.get_context().config.attributes.get('timescale', False):
        from app.postgres_schema import portable_schema
        sql = portable_schema(sql)
    schema = op.get_context().config.attributes['schema']
    op.get_bind().connection.run_async(lambda driver: driver.execute(f'SET LOCAL search_path TO "{schema}", public;\n' + sql))

def downgrade():
    raise RuntimeError('Destructive downgrade disabled. Restore a reviewed backup instead.')
