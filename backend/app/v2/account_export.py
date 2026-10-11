"""A private, read-only snapshot of one account's locally stored practice data."""
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from . import db

MAX_ROWS = 10_000
MAX_BYTES = 25 * 1024 * 1024

# Every collection has an ownership predicate; shared catalog and cached prompts
# are deliberately absent. Table/column names below are application constants.
COLLECTIONS = {
    **{name: 'r.user_id=$1' for name in (
        'profiles', 'source_documents', 'failed_questions', 'plans', 'tracks',
        'lessons', 'retest_queue', 'skill_assessments', 'user_skills', 'star_stories',
        'applications', 'generation_jobs', 'work_items')},
    'memories': 'r.owner_id=$1',
    'sessions': 'r.user_id=$1',
    'scenarios': 'EXISTS (SELECT 1 FROM tracks t WHERE t.id=r.track_id AND t.user_id=$1)',
    'scenario_steps': 'EXISTS (SELECT 1 FROM scenarios sc JOIN tracks t ON t.id=sc.track_id WHERE sc.id=r.scenario_id AND t.user_id=$1)',
    'track_skills': 'EXISTS (SELECT 1 FROM tracks t WHERE t.id=r.track_id AND t.user_id=$1)',
    **{name: 'EXISTS (SELECT 1 FROM sessions s WHERE s.id=r.session_id AND s.user_id=$1)'
       for name in ('session_events', 'artifacts', 'board_annotations', 'session_reports',
                    'claims', 'evaluator_runs', 'metrics')},
    'session_stories': 'EXISTS (SELECT 1 FROM sessions s WHERE s.id=r.session_id AND s.user_id=$1) AND EXISTS (SELECT 1 FROM star_stories st WHERE st.id=r.story_id AND st.user_id=$1)',
}
AUDIT_FIELDS = {
    'generation_jobs': ('id,user_id,kind,subject_type,subject_id,status,parent_job_id,stage,'
                        'model,prompt_version,is_seed,schema_ok,attempt,tokens_in,tokens_out,'
                        'latency_ms,created_at,finished_at,work_item_id'),
    'work_items': 'id,user_id,kind,subject_id,status,stage,attempts,created_at,updated_at,finished_at',
}
OMIT_KEYS = {
    'password_hash', 'password', 'token', 'token_hash', 'access_token', 'refresh_token',
    'api_key', 'secret', 'authorization', 'cookie', 'resume_hash', 'resume_token',
    'pair_code', 'pair_token', 'blob_key', 'annotated_blob_key', 'external_id',
    'assistant_id', 'device_id', 'connection_id', 'dataURL', 'data_url', 'file_path',
    'server_path', 'embedding', 'error',
}


def _public(value):
    if isinstance(value, dict):
        return {k: _public(v) for k, v in value.items() if k not in OMIT_KEYS}
    if isinstance(value, (list, tuple)):
        return [_public(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def export_account(user_id: str) -> dict:
    """Return an all-or-error snapshot; never silently truncate a collection."""
    async with (await db.pool()).acquire() as connection:
        async with connection.transaction(isolation='repeatable_read', readonly=True):
            user = await connection.fetchrow(
                'SELECT u.id,u.display_name,a.email,u.created_at FROM users u JOIN accounts a ON a.user_id=u.id WHERE u.id=$1 AND u.deleted_at IS NULL', user_id)
            if not user:
                raise HTTPException(404, 'Account not found')
            account = _public(dict(user))
            data = {}
            size = len(json.dumps(account).encode())
            for table, ownership in COLLECTIONS.items():
                if table in AUDIT_FIELDS:
                    fields = ','.join('r.' + field for field in AUDIT_FIELDS[table].split(','))
                    selection = f'(SELECT row_to_json(a) FROM (SELECT {fields}) a)'
                else:
                    selection = 'to_jsonb(r)'
                rows = await connection.fetch(
                    f'SELECT {selection} AS record FROM {table} r WHERE {ownership} LIMIT $2',
                    user_id, MAX_ROWS + 1)
                if len(rows) > MAX_ROWS:
                    raise HTTPException(413, 'Account export exceeds the collection limit; contact support for a complete export.')
                records = [_public(json.loads(row['record']) if isinstance(row['record'], str) else row['record']) for row in rows]
                size += len(json.dumps(records).encode())
                if size > MAX_BYTES:
                    raise HTTPException(413, 'Account export exceeds 25 MiB; contact support for a complete export.')
                data[table] = records
    return {
        'format_version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
        'account': account, 'data': data,
        'manifest': {
            'included': ['account identity'] + list(COLLECTIONS),
            'artifacts': 'Metadata and stored vector payloads; filesystem PNG/audio/upload binaries and embedded data URLs are excluded.',
            'audit_scope': 'Generation jobs and work items include lifecycle metadata only; prompts, payloads, responses and error details are excluded.',
            'excluded': ['authentication credentials and sessions', 'pairing/device capabilities',
                         'server file paths and blob keys', 'external memory identifiers and provider-only data',
                         'shared catalog, shared lessons, other users records', 'binary attachments'],
            'limits': {'rows_per_collection': MAX_ROWS, 'data_bytes': MAX_BYTES, 'truncated': False},
        },
    }
