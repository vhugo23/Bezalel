"""Offer the versioned, reference-checked Pi engine to existing plans."""
import json
from pathlib import Path
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision='009_pi_linux'
down_revision='008_device_resume'
branch_labels=None
depends_on=None


def upgrade():
    schema=op.get_context().config.attributes['schema']
    conn=op.get_bind()
    # Immutable migration fixture, not a call to the evolving application engine.
    data=json.loads((Path(__file__).resolve().parents[1]/'data/009_pi_linux.json').read_text(encoding='utf-8'))
    tracks=conn.execute(sa.text(f"SELECT id FROM {schema}.tracks t WHERE template_id='infra.pi_site' AND status='proposed' AND NOT EXISTS(SELECT 1 FROM {schema}.scenarios sc WHERE sc.track_id=t.id AND sc.is_active)"))
    for track in tracks:
        sid=str(uuid4())
        conn.execute(sa.text(f"INSERT INTO {schema}.scenarios(id,track_id,engine_id,engine_version,spec,params,rubric,validity,validity_report) VALUES(:sid,:tid,'linux_fault','pi-linux-1',CAST(:spec AS jsonb),CAST(:params AS jsonb),CAST(:rubric AS jsonb),'passed',CAST(:report AS jsonb))"),
            {'sid':sid,'tid':track[0],'spec':json.dumps(data['spec']),'params':json.dumps(data['params']),
             'rubric':json.dumps(data['rubric']),'report':json.dumps(data['validity_report'])})
        for step in data['spec']['steps']:
            conn.execute(sa.text(f"INSERT INTO {schema}.scenario_steps(scenario_id,idx,title,surface,task,config,hints,success) VALUES(:sid,:idx,:title,:surface,:task,CAST(:config AS jsonb),ARRAY(SELECT jsonb_array_elements_text(CAST(:hints AS jsonb))),CAST(:success AS jsonb))"),
                {'sid':sid,**{k:step[k] for k in ('idx','title','surface','task')},
                 **{k:json.dumps(step[k]) for k in ('config','hints','success')}})
        conn.execute(sa.text(f"UPDATE {schema}.tracks SET status='ready' WHERE id=:tid"),{'tid':track[0]})


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
