"""Engine-owned retest constraints. Models cannot change executable semantics."""
from fastapi import HTTPException
from . import pi_lab
from .models import LessonDraft


PI_COACHING = {
    'infra.reverse_proxy': (
        'Separate the proxy from the application',
        'A gateway error does not prove that the application has stopped. Compare the proxy error with the service listening endpoint and a direct application request. A saved configuration is not yet the running configuration: validate syntax before reload, then verify the public response. Change only the layer supported by the observations.',
        'Describe which observation would distinguish an unavailable app from a proxy pointing at the wrong endpoint. In the simulated lab, inspect the service and proxy, make one scoped change, and verify the response.',
        'Explains the proxy versus application distinction and verifies a validated configuration repair.'),
    'infra.permissions': (
        'Read Linux permissions by user class',
        'The three octal permission digits describe owner, group and others. Read is 4, write is 2, and execute is 1. Mode 644 gives the owner read and write, while group and others get read only; it does not grant everyone write access. Serving a file requires file read access and search (execute) access through every parent directory. Give the web-server user only the access needed, then verify the asset response.',
        'Translate 600, 640 and 644 into owner/group/other permissions. Explain why a readable file can remain inaccessible inside a non-searchable directory. Use the simulated asset response to verify your least-privilege repair.',
        'Explains file read and directory search permissions without granting unnecessary write access.'),
    'infra.disk_logs': (
        'Distinguish a log path from allocated blocks',
        'Removing an open log name does not necessarily free its disk blocks: a running process can retain the open file descriptor. Compare filesystem usage, visible log sizes and deleted open files. For an existing log, truncation can release data while preserving the path. For an already unlinked log, safely closing the owning process descriptor may be necessary. Verify recovered space and the application response, then plan log rotation.',
        'Explain why deleting a large open log can leave filesystem usage unchanged. Compare recovery for an existing log with recovery for an already unlinked log, and verify the simulated contact form after a scoped repair.',
        'Distinguishes unlinking an open log from releasing its blocks and verifies safe recovery.'),
    'infra.power_thermals': (
        'Separate current throttle flags from history',
        'Raspberry Pi throttle readings include current low bits and historical high bits. Historical flags can remain set after a suitable supply removes the current fault. Compare the current flags before and after any change, and interpret kernel messages in context. A core-voltage measurement is not the USB supply voltage. A historical warning alone does not justify replacing a working supply. These lab readings are simulated, not physical telemetry.',
        'Explain the difference between a current under-voltage flag and a historical flag. In the simulator, compare observations before deciding whether a hardware change is justified; verify current state afterward.',
        'Distinguishes current from historical throttle flags and avoids treating core voltage as USB supply voltage.'),
    'infra.debug_method': (
        'Use a hypothesis, a scoped change and verification',
        'Start with an observed symptom and a hypothesis that a targeted check can disprove. Separate proxy, application, permissions, storage and power failures instead of changing everything together. Make the smallest justified change, then test the original symptom again. Explain how the result changes your hypothesis; command count alone does not demonstrate understanding. Lab commands and hardware readings are simulated.',
        'For each simulated failure, state a hypothesis, select a discriminating observation, make one scoped change and verify the original symptom. Explain what you would investigate if the check contradicted your hypothesis.',
        'Explains a hypothesis, targeted diagnostic, scoped change and verification of the observed result.'),
}


def authored_pi_lesson(skill_id, variant):
    if skill_id not in PI_COACHING or variant not in (0, 1):
        raise HTTPException(409, 'Authored coaching is not available for this Pi skill or variant.')
    title, explanation, practice, expectation = PI_COACHING[skill_id]
    narrative = (
        'A second simulated Raspberry Pi portfolio deployment reports a gateway error after a maintenance handoff. Investigate the service, explain the evidence for each decision, and verify the complete site before calling the incident resolved.',
        'A simulated Raspberry Pi portfolio has been redeployed by another operator and visitors report a gateway error. Investigate this new deployment from its observed symptoms, explain your decisions, and verify the complete site before handing it back.',
    )[variant]
    return LessonDraft(title=title, explanation=explanation, practice=practice,
        retest_prompt=narrative+' All commands and readings are simulated.', expectations=[expectation])


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
                'layer':2,'validity':data['validity_report']}
    raise HTTPException(409,'This engine does not support checked retests yet.')


def publication(original, prepared, draft, skill_id, check_id, reason, recorded=False, *, authored=False):
    if authored and (prepared['engine_id'] != 'linux_fault' or skill_id not in PI_COACHING):
        raise ValueError('Authored publication requires a supported Pi skill')
    if authored and draft != authored_pi_lesson(skill_id, prepared['params']['variant']):
        raise ValueError('Authored publication must use the engine-owned coaching unchanged')
    spec={**prepared['spec'],'prompt':draft.retest_prompt,'focus_skill':skill_id,'expectations':draft.expectations}
    if prepared['engine_id']=='conceptual':spec.pop('requirements',None)
    validity={**prepared['validity'],'check_job_id':check_id,'reason':reason,
              'semantic_guarantee':False,'recorded_review':recorded}
    if prepared['engine_id']=='linux_fault':
        validity.update(kind='reference_run_and_authored_coaching' if authored else 'reference_run_and_model_review',
            label='Reference-tested simulator with '+('recorded coaching review' if recorded else 'independently model-reviewed coaching')+'; human calibration pending')
        if authored:
            validity.update(label='Authored coaching with a reference-tested simulator; human calibration pending',
                            authored_coaching=True, recorded_review=False)
    else:
        validity.update(kind='second_model_review',label='Recorded conceptual review fixture' if recorded else 'Model-reviewed conceptual exercise; no deterministic correctness guarantee')
    return {**prepared,'spec':spec,'rubric':original['rubric'],'validity':validity}
