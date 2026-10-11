"""External-memory outbox survives local deletion and worker interruption."""
from alembic import op

revision = '007_memory_sync'
down_revision = '006_source_documents'
branch_labels = None
depends_on = None


def upgrade():
    s = op.get_context().config.attributes['schema']
    op.execute(f'''CREATE TABLE {s}.memory_accounts (
        user_id TEXT PRIMARY KEY REFERENCES {s}.users(id) ON DELETE CASCADE,
        assistant_id TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )''')
    # No FK here: deletion must retain the minimum external references until the
    # provider confirms erasure, even after local memory/user records are gone.
    op.execute(f'''CREATE TABLE {s}.memory_sync (
        memory_id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        operation TEXT NOT NULL CHECK(operation IN ('upsert','delete')),
        revision INT NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed')),
        assistant_id TEXT,
        external_id TEXT,
        attempts SMALLINT NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
        next_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        latency_ms INT,
        error TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )''')
    op.execute(f"CREATE INDEX memory_sync_pending ON {s}.memory_sync(next_at) WHERE status IN ('queued','running')")
    op.execute(f'''CREATE FUNCTION {s}.queue_memory_sync() RETURNS trigger LANGUAGE plpgsql
        SET search_path TO {s},public AS $$
        DECLARE m memories; operation_name TEXT;
        BEGIN
            IF TG_OP='DELETE' THEN m:=OLD; operation_name:='delete';
            ELSE
                m:=NEW;
                IF m.source_claim_id IS NULL OR m.source_session_id IS NULL OR m.salience=0
                    OR m.data @> jsonb_build_object('resolved',true) THEN operation_name:='delete';
                ELSE operation_name:='upsert'; END IF;
            END IF;
            INSERT INTO memory_sync(memory_id,owner_id,operation,external_id,assistant_id)
                VALUES(m.id,m.owner_id,operation_name,m.external_id,
                    (SELECT assistant_id FROM memory_accounts WHERE user_id=m.owner_id))
            ON CONFLICT(memory_id) DO UPDATE SET operation=excluded.operation,
                revision=memory_sync.revision+1,status='queued',attempts=0,next_at=now(),
                external_id=coalesce(excluded.external_id,memory_sync.external_id),
                assistant_id=coalesce(excluded.assistant_id,memory_sync.assistant_id),error=NULL,updated_at=now();
            RETURN NULL;
        END $$''')
    op.execute(f'''CREATE TRIGGER memory_sync_change AFTER INSERT OR DELETE OR UPDATE OF
        text,data,source_claim_id,source_session_id,salience ON {s}.memories
        FOR EACH ROW EXECUTE FUNCTION {s}.queue_memory_sync()''')
    op.execute(f'''INSERT INTO {s}.memory_sync(memory_id,owner_id,operation,external_id)
        SELECT id,owner_id,'upsert',external_id FROM {s}.memories WHERE source_claim_id IS NOT NULL''')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')
