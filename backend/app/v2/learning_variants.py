"""Engine-owned retest constraints. Models cannot change executable semantics."""
from fastapi import HTTPException
from . import pi_lab


def prepare(original):
    if original['engine_id']=='conceptual':
        return {'spec':original['spec'],'params':{},'engine_id':'conceptual','engine_version':original.get('engine_version','1'),
                'layer':3,'validity':{},
                'instructions':'Create a changed rate-limiter system-design prompt testing the SAME skill. Keep the clarify requirements / draw and explain / defend trade-offs flow. State changed workload and availability requirements in the prompt.',
                'review':'The retest must remain a rate-limiter conceptual system-design interview compatible with clarify requirements / draw and explain / defend trade-offs. The prompt must change a substantive constraint.'}
    if original['engine_id']=='linux_fault':
        old=original.get('params',{}).get('variant',0)
        if old not in (0,1):raise ValueError('Unsupported Pi retest variant')
        data=pi_lab.definition(1-old)
        assert pi_lab.initial(old)['app_port']!=pi_lab.initial(1-old)['app_port']
        return {'spec':data['spec'],'params':data['params'],'engine_id':'linux_fault','engine_version':pi_lab.VERSION,
                'layer':2,'validity':data['validity_report'],
                'instructions':'Create coaching for the SAME Linux/Pi skill and a new deployment investigation. The checked retest changes the app listening port, directory access, log-file lifecycle and current-versus-historical power state. The candidate discovers the endpoint with systemctl status site. Do not reveal the port or fault solutions in the retest prompt. Keep the five existing terminal/editor/browser/power stages, files and supported commands. Hardware need not be changed if the current readings show no active fault. Do not invent services, hardware or tasks outside this simulator. Explain the relevant concept in the lesson, without announcing the retest solution.',
                'review':'The retest must fit the supplied Pi simulator tasks and command subset, with no new services, files or unsupported requirements. The engine changes the listening port; the prompt must not reveal its value. The lesson must distinguish simulation from real hardware and current throttle flags from history when relevant.'}
    raise HTTPException(409,'This engine does not support checked retests yet.')


def publication(original, prepared, draft, skill_id, check_id, reason, recorded=False):
    spec={**prepared['spec'],'prompt':draft.retest_prompt,'focus_skill':skill_id,'expectations':draft.expectations}
    if prepared['engine_id']=='conceptual':spec.pop('requirements',None)
    validity={**prepared['validity'],'check_job_id':check_id,'reason':reason,
              'semantic_guarantee':False,'recorded_review':recorded}
    if prepared['engine_id']=='linux_fault':
        validity.update(kind='reference_run_and_model_review',
            label='Reference-tested simulator with '+('recorded coaching review' if recorded else 'independently model-reviewed coaching')+'; human calibration pending')
    else:
        validity.update(kind='second_model_review',label='Recorded conceptual review fixture' if recorded else 'Model-reviewed conceptual exercise; no deterministic correctness guarantee')
    return {**prepared,'spec':spec,'rubric':original['rubric'],'validity':validity}
