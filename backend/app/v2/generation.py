import asyncio
import json
import os
import time
from uuid import uuid4
from pydantic import BaseModel, ValidationError
from app import config
from . import db

DEMO = os.getenv('DEMO_MODE', 'false').lower() == 'true'

def provider_schema(schema):
    wire=schema.model_json_schema()
    if schema.__name__!='RubricEvaluation':return wire
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
    correction=''
    for attempt in range(1, 3):
        jid, start = str(uuid4()), time.perf_counter()
        model = ({'evaluator':config.EVALUATOR_MODEL, 'evidence_check':config.EVALUATOR_MODEL, 'lesson':config.EVALUATOR_MODEL, 'lesson_check':config.EVALUATOR_MODEL, 'whiteboard_critique':config.WHITEBOARD_MODEL}.get(kind,config.INTERVIEWER_MODEL)) or config.GEMINI_MODEL
        await db.execute("INSERT INTO generation_jobs(id,kind,subject_type,subject_id,status,stage,model,request,is_seed,attempt,user_id,parent_job_id) VALUES($1,$2,$8,$3,'running','Validating structured output',$4,$5,$6,$7,$9,$10)",
                         jid,kind,subject,'recorded' if recorded else model,{'prompt':prompt+correction,'schema':schema.__name__},recorded,attempt,subject_type,user_id,parent_job_id)
        try:
            if recorded:
                result = schema.model_validate(cached)
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
                result = schema.model_validate_json(answer.text)
            ms = round((time.perf_counter()-start)*1000)
            await db.execute("UPDATE generation_jobs SET status=$2,response=$3,schema_ok=true,latency_ms=$4,finished_at=now(),stage='Complete' WHERE id=$1",
                             jid,'cached' if recorded else 'succeeded',result.model_dump(),ms)
            if subject_type=='session':
                await db.execute('INSERT INTO metrics(session_id,name,value) SELECT id,$2,$3 FROM sessions WHERE id=$1',subject,kind+'_ms',float(ms))
            return result, jid, 'recorded' if recorded else 'gemini'
        except asyncio.CancelledError:
            await asyncio.shield(db.execute("UPDATE generation_jobs SET status='failed',error='Interrupted by candidate',stage='Cancelled',finished_at=now() WHERE id=$1 AND status='running'",jid))
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
            await db.execute("UPDATE generation_jobs SET status='failed',error=$2,finished_at=now() WHERE id=$1",jid,diagnostic)
            if attempt == 1 and (isinstance(exc, (ValidationError,TimeoutError)) or code in (500,502,503,504)):
                continue
            if code == 429:
                raise ValueError('Gemini’s rate or quota limit blocked this request. Your work is saved. Retry after the limit resets.') from exc
            raise ValueError('Model unavailable or returned invalid output. Your work is saved; retry shortly.') from exc
