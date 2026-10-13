"""Small native transports; every response is validated by the caller's rubric schema."""
import base64
import json
import httpx
from . import providers

class ProviderFailure(Exception):
    def __init__(self,code):
        self.code=code
        super().__init__(f'Model provider HTTP {code}')

def claude_schema(node):
    """Match the documented SDK transformation while retaining local validation.

    https://platform.claude.com/docs/en/build-with-claude/structured-outputs
    """
    if isinstance(node,list):return [claude_schema(value) for value in node]
    if not isinstance(node,dict):return node
    unsupported={'minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf','minLength','maxLength','maxItems','uniqueItems'}
    if node.get('minItems',0)>1:unsupported.add('minItems')
    result={key:claude_schema(value) for key,value in node.items() if key not in unsupported}
    constraints={key:node[key] for key in unsupported if key in node}
    if constraints:result['description']=(result.get('description','')+' Constraints: '+json.dumps(constraints)).strip()
    if result.get('type')=='object':result['additionalProperties']=False
    return result

async def generate(settings,keys,model,prompt,schema,image=None,timeout=40):
    encoded=base64.b64encode(image).decode() if image else None
    headers={'Content-Type':'application/json'}
    if settings.llm=='openai':
        url='https://api.openai.com/v1/responses'
        headers['Authorization']='Bearer '+keys['llm_key']
        content=[{'type':'input_text','text':prompt}]
        if encoded:content.append({'type':'input_image','image_url':'data:image/png;base64,'+encoded})
        body={'model':model,'store':False,'input':[{'role':'user','content':content}],
              'text':{'format':{'type':'json_schema','name':'prepcrew_response','schema':schema,'strict':False}}}
    elif settings.llm=='anthropic':
        url='https://api.anthropic.com/v1/messages'
        headers.update({'x-api-key':keys['llm_key'],'anthropic-version':'2023-06-01'})
        content=[{'type':'text','text':prompt}]
        if encoded:content.append({'type':'image','source':{'type':'base64','media_type':'image/png','data':encoded}})
        body={'model':model,'max_tokens':8192,'messages':[{'role':'user','content':content}],
              'output_config':{'format':{'type':'json_schema','schema':claude_schema(schema)}}}
    elif settings.llm=='compatible':
        url=providers.validate_url(settings.base_url)+'/chat/completions'
        if keys.get('llm_key'):headers['Authorization']='Bearer '+keys['llm_key']
        content=[{'type':'text','text':prompt}]
        if encoded:content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+encoded}})
        body={'model':model,'messages':[{'role':'system','content':'Return only JSON matching this schema: '+json.dumps(schema)},
                                      {'role':'user','content':content}],
              'response_format':{'type':'json_object'}}
    elif settings.llm=='gemini':
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=keys['llm_key'],http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)))
        content=[prompt]
        if image:content.append(types.Part.from_bytes(data=image,mime_type='image/png'))
        async with client.aio as ai:
            result=await ai.models.generate_content(model=model,contents=content,
                config=types.GenerateContentConfig(response_mime_type='application/json',response_json_schema=schema))
        usage=getattr(result,'usage_metadata',None)
        return result.text,getattr(usage,'prompt_token_count',None),getattr(usage,'candidates_token_count',None)
    else:raise ValueError('Open Connections and choose an interviewer model.')
    async with httpx.AsyncClient(timeout=timeout,follow_redirects=False,trust_env=False,transport=providers._transport) as client:
        response=await client.post(url,headers=headers,json=body)
    if not response.is_success:raise ProviderFailure(response.status_code)
    data=response.json();usage=data.get('usage',{})
    if settings.llm=='openai':
        text=''.join(part.get('text','') for item in data.get('output',[]) if item.get('type')=='message'
                     for part in item.get('content',[]) if part.get('type')=='output_text')
        return text,usage.get('input_tokens'),usage.get('output_tokens')
    if settings.llm=='anthropic':
        return ''.join(part.get('text','') for part in data.get('content',[]) if part.get('type')=='text'),usage.get('input_tokens'),usage.get('output_tokens')
    return data['choices'][0]['message']['content'],usage.get('prompt_tokens'),usage.get('completion_tokens')
