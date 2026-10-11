"""Persist the existing authored and retest step definitions."""
from alembic import op

revision='004_session_steps'
down_revision='003_learning_loop'
branch_labels=None
depends_on=None


def upgrade():
    schema=op.get_context().config.attributes['schema']
    op.execute(f'''UPDATE {schema}.scenarios SET spec=jsonb_set(spec,'{{requirements}}',
      jsonb_build_object('requests_per_second',10000,'identity','API key','bursts',true,
        'availability','preferred','accuracy','slight approximation acceptable'))
      WHERE engine_id='conceptual' AND variant_of IS NULL
        AND spec->>'prompt'='Design a rate limiter for a public API. Before you draw anything, ask me what you need to know.'
        AND NOT spec ? 'requirements' ''')
    op.execute(f'''INSERT INTO {schema}.scenario_steps(scenario_id,idx,title,surface,task,config,success)
      SELECT s.id,i,(s.spec->'steps'->>i),
        CASE WHEN i=1 THEN 'whiteboard' ELSE 'voice' END,
        CASE i WHEN 0 THEN 'Ask Dana about workload, constraints and success conditions.'
          WHEN 1 THEN 'Explain your drawing and ask Dana to review it.'
          ELSE 'Explain a decision, its consequences and a failure case.' END,
        CASE WHEN i=1 THEN jsonb_build_object('look','on_done') ELSE '{{}}'::jsonb END,
        CASE WHEN i=1 THEN jsonb_build_object('min_turns',1,'board_review',true) ELSE jsonb_build_object('min_turns',2) END
      FROM {schema}.scenarios s CROSS JOIN generate_series(0,2) i
      WHERE jsonb_typeof(s.spec->'steps')='array' AND jsonb_array_length(s.spec->'steps')=3
        AND jsonb_typeof(s.spec->'steps'->0)='string'
      ON CONFLICT DO NOTHING''')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
