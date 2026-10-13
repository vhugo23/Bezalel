import asyncio
import json
import hashlib
import os
import time
from uuid import uuid4
from pydantic import BaseModel, ValidationError
from app import config
from . import db
from .work_context import work_item_id

DEMO = os.getenv('DEMO_MODE', 'false').lower() == 'true'

def provider_schema(schema):
    wire=schema.model_json_schema()
    if schema.__name__ not in ('RubricEvaluation','AtsDraft'):return wire
    # Nested bounded claim/quote arrays exceed the provider's schema complexity
    # budget. Keep the full limits in Pydantic; relax only the decoding schema.
    # Every response is still validated against the original model below.
    def relax(node):
        if isinstance(node,dict):return {k:relax(v) for k,v in node.items() if k!='maxItems'}
        if isinstance(node,list):return [relax(v) for v in node]
        return node
    return relax(wire)

async def generate(kind: str, subject: str, prompt: str, schema: type[BaseModel], cached=None, image: bytes | None = None, prefer_cache: bool = False, *, subject_type: str = 'session', user_id: str | None = None, parent_job_id: str | None = None):
    """Each attempt has its own audit row, including cached/demo calls and failures."""
    recorded = DEMO or prefer_cache
    if recorded and cached is None:
        raise ValueError('No recorded response for this input; enable live mode to continue')
    selected=None
    if not recorded:
        from . import providers
        selected=await providers.for_subject(subject,subject_type,user_id) if config.DATABASE_URL else None
        if (selected and selected[0].llm=='none') or (not selected and os.getenv('PREPCREW_BYOB_ONLY')=='true'):
            raise ValueError('Open Connections and connect an interviewer model before starting live practice.')
    correction=''
    for attempt in range(1, 3):
        jid, start = str(uuid4()), time.perf_counter()
        model = ({'evaluator':config.EVALUATOR_MODEL, 'evidence_check':config.EVALUATOR_MODEL, 'lesson':config.EVALUATOR_MODEL, 'lesson_check':config.EVALUATOR_MODEL, 'plan_check':config.EVALUATOR_MODEL, 'job_scan':config.EVALUATOR_MODEL, 'ats_review':config.EVALUATOR_MODEL, 'whiteboard_critique':config.WHITEBOARD_MODEL}.get(kind,config.INTERVIEWER_MODEL)) or config.GEMINI_MODEL
        if selected:
            model=(selected[0].evaluator_model if kind not in ('interviewer','whiteboard_critique') else '') or selected[0].model
        version=kind+'-v1'
        fingerprint=hashlib.sha256(json.dumps({'kind':kind,'version':version,'model':model,
            'provider':selected[0].llm if selected else 'gemini',
            'base_url':selected[0].base_url if selected and selected[0].llm=='compatible' else None,
            'prompt':prompt+correction,'schema':schema.model_json_schema(),'user_id':user_id,
            'image':hashlib.sha256(image).hexdigest() if image else None},sort_keys=True).encode()).hexdigest()
        await db.execute("INSERT INTO generation_jobs(id,kind,subject_type,subject_id,status,stage,model,request,is_seed,attempt,user_id,parent_job_id,work_item_id,prompt_version,cache_key) VALUES($1,$2,$8,$3,'running','Validating structured output',$4,$5,$6,$7,$9,$10,$11,$12,$13)",
                         jid,kind,subject,'recorded' if recorded else model,{'prompt':prompt+correction,'schema':schema.__name__},recorded,attempt,subject_type,user_id,parent_job_id,work_item_id.get(),version,fingerprint)
        tokens_in=tokens_out=0 if recorded else None
        try:
            if recorded:
                result = schema.model_validate(cached)
            elif selected:
                from . import model_transport
                text,tokens_in,tokens_out=await asyncio.wait_for(model_transport.generate(
                    selected[0],selected[1],model,prompt+correction,provider_schema(schema),image,
                    timeout=12 if kind=='interviewer' else 40),timeout=15 if kind=='interviewer' else 45)
                result=schema.model_validate_json(text)
            else:
                from google import genai
                from google.genai import types
                # Own retries here so every provider attempt gets a distinct audit row.
                client = genai.Client(api_key=config.GEMINI_API_KEY,
                    http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)))
                contents = [prompt+correction]
                if image:
                    contents.append(types.Part.from_bytes(data=image, mime_type='image/png'))
                async with client.aio as ai:
                    answer = await asyncio.wait_for(ai.models.generate_content(
                        model=model,
                        contents=contents,
                        # Send JSON Schema on the JSON Schema wire field. The legacy
                        # response_schema field cannot encode extra='forbid'.
                        config=types.GenerateContentConfig(response_mime_type='application/json', response_json_schema=provider_schema(schema))),
                        timeout=12 if kind=='interviewer' else 30 if kind=='whiteboard_critique' else 40)
                usage=getattr(answer,'usage_metadata',None)
                if usage:
                    tokens_in=usage.prompt_token_count
                    output_tokens=usage.candidates_token_count
                    thinking_tokens=usage.thoughts_token_count
                    tokens_out=(output_tokens or 0)+(thinking_tokens or 0) if output_tokens is not None or thinking_tokens is not None else None
                result = schema.model_validate_json(answer.text)
            ms = round((time.perf_counter()-start)*1000)
            await db.execute("UPDATE generation_jobs SET status=$2,response=$3,schema_ok=true,latency_ms=$4,tokens_in=$5,tokens_out=$6,finished_at=now(),stage='Complete' WHERE id=$1",
                             jid,'cached' if recorded else 'succeeded',result.model_dump(),ms,tokens_in,tokens_out)
            if subject_type=='session':
                await db.execute('INSERT INTO metrics(session_id,name,value) SELECT id,$2,$3 FROM sessions WHERE id=$1',subject,kind+'_ms',float(ms))
            return result, jid, 'recorded' if recorded else selected[0].llm if selected else 'gemini'
        except asyncio.CancelledError:
            await asyncio.shield(db.execute("UPDATE generation_jobs SET status='failed',error='Generation interrupted',stage='Cancelled',finished_at=now() WHERE id=$1 AND status='running'",jid))
            raise
        except Exception as exc:
            # Keep useful, non-sensitive diagnostics without storing provider bodies
            # (which may echo request content or credentials).
            code = getattr(exc, 'code', None)
            diagnostic = type(exc).__name__ + (f' (HTTP {code})' if isinstance(code, int) else '')
            if isinstance(exc,ValidationError):
                details='; '.join('.'.join(str(x) for x in e['loc'])+': '+e['type'] for e in exc.errors(include_input=False))[:500]
                diagnostic+=' ('+details+')'
                correction='\nYour previous output failed local validation: '+details+'. Correct these errors; obey the original schema limits.'
            await db.execute("UPDATE generation_jobs SET status='failed',error=$2,tokens_in=$3,tokens_out=$4,finished_at=now() WHERE id=$1",jid,diagnostic,tokens_in,tokens_out)
            if attempt == 1 and (isinstance(exc, (ValidationError,TimeoutError)) or code in (500,502,503,504)):
                continue
            if code == 429:
                raise ValueError('Your provider’s rate or quota limit blocked this request. Your work is saved. Retry after the limit resets.') from exc
            raise ValueError('Model unavailable or returned invalid output. Your work is saved; retry shortly.') from exc
