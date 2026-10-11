import copy
import pytest
from app.v2 import pi_lab as pi, labs, rubrics, engine
from app.v2.integrity import verify
from app.v2.models import ClaimDraft, LabAction, RubricEvaluation
from app.v2.assessment import checked_claims


def run(s,text):return pi.apply(s,'command',text)


@pytest.mark.parametrize('variant',[0,1])
def test_broken_scenario_and_full_reference_solution_are_checked(variant):
    data=pi.definition(variant)
    assert data['validity_report']['checks']==['broken_symptoms_reproduced' if variant==0 else 'changed_variant_conditions_reproduced','five_reference_goals_pass','historical_power_flags_retained']
    assert len(engine.parse_steps(data['spec']))==5
    assert rubrics.load(data['rubric'],'linux_fault').version.startswith('pi-linux-practice-v1:')
    assert pi.website(pi.initial(variant))==502


def test_edited_configuration_is_not_active_until_valid_reload():
    s=pi.initial();s,_=pi.apply(s,'edit',s['config'].replace('3001','3000'))
    assert pi.website(s)==502 and s['tested_revision'] is None
    s,output=run(s,'sudo nginx -t');assert 'successful' in output
    s,_=run(s,'sudo systemctl reload nginx');assert pi.website(s)==200
    assert not s['risky'] and not pi.goal(s,1)
    s,_=run(s,'curl -I localhost');assert pi.goal(s,1)


@pytest.mark.parametrize('bad',['server {','server { listen 80; proxy_pass http://127.0.0.1:3000; }',pi.CONFIG+'include /etc/passwd;',pi.CONFIG.replace('3001','99999')])
def test_invalid_or_unsupported_config_does_not_replace_running_workers(bad):
    s=pi.initial();s,_=pi.apply(s,'edit',bad);s,output=run(s,'sudo systemctl reload nginx')
    assert s['active_port']==3001 and 'rejected' in output


def test_valid_reload_without_test_is_allowed_but_observable_process_risk():
    s=pi.initial();s,_=pi.apply(s,'edit',s['config'].replace('3001','3000'))
    s,_=run(s,'sudo systemctl reload nginx');assert s['risky']==['reload_without_current_test']
    s,_=run(s,'sudo nginx -t');s,_=pi.apply(s,'edit',s['config']+' ')
    assert s['tested_revision'] is None


def test_directory_traversal_and_world_write_are_not_taught_as_safe_repairs():
    s=pi.initial();s['active_port']=3000
    s,_=run(s,'sudo chmod -R 644 /var/www/site');assert not pi.readable(s)
    s,_=run(s,'sudo chmod -R 777 /var/www/site');assert pi.readable(s)
    s,_=run(s,'curl -I localhost/assets/app.css');assert not pi.goal(s,2)
    s,_=run(s,'sudo chmod -R 755 /var/www/site')
    assert not pi.goal(s,2) # changed permissions require a new verification
    s,_=run(s,'curl -I localhost/assets/app.css');assert pi.goal(s,2)
    assert 'world_writable' in s['risky']


def test_scoped_file_read_permission_is_sufficient_without_changing_owner():
    s=pi.initial();s['active_port']=3000
    s,_=run(s,'sudo chmod 644 /var/www/site/assets/app.css')
    assert pi.readable(s) and s['owner']=='root' and s['dir_mode']==0o755


def test_chown_directory_without_recursion_does_not_change_file_owner():
    s=pi.initial();s,_=run(s,'sudo chown www-data:www-data /var/www/site')
    assert s['owner']=='root' and not pi.readable(s)
    s,_=run(s,'sudo chown -R www-data:www-data /var/www/site');assert pi.readable(s)


def test_asset_directory_repair_does_not_change_its_nontraversable_parent():
    s=pi.initial(1);s['active_port']=4000
    s,_=run(s,'sudo chmod -R 755 /var/www/site/assets');assert not pi.readable(s)
    s,_=run(s,'sudo chmod 755 /var/www/site');assert pi.readable(s)


def test_retest_changes_permissions_log_lifecycle_and_power_interpretation():
    parent=pi.initial(0);s=pi.initial(1)
    assert s['app_port']!=parent['app_port'] and s['dir_mode']!=parent['dir_mode']
    assert parent['log_exists'] and not s['log_exists']
    s,output=run(s,'du -sh /var/log/*');assert 'absent' in output and not s['seen'].get('large_log')
    s,output=run(s,'lsof +L1');assert '(deleted)' in output and s['seen']['large_log']
    assert pi.throttled(parent)&0xf and not pi.throttled(s)&0xf
    assert not pi.goal(s,4)
    s,_=run(s,'vcgencmd get_throttled');assert pi.goal(s,4)


def test_unlinking_open_log_keeps_disk_allocated_until_descriptor_closes():
    s=pi.initial();s,_=run(s,'sudo rm /var/log/site/access.log')
    assert s['allocated'] and not s['log_exists']
    _,output=run(s,'df -h');assert '100%' in output
    _,output=run(s,'lsof +L1');assert '(deleted)' in output
    s,output=run(s,'sudo truncate -s 0 /var/log/site/access.log');assert s['allocated'] and 'No such file' in output
    s,_=run(s,'sudo systemctl restart site');assert not s['allocated'] and s['log_exists']


def test_truncation_releases_blocks_and_keeps_open_log_path():
    s=pi.initial();s,_=run(s,'sudo truncate -s 0 /var/log/site/access.log')
    assert not s['allocated'] and s['log_exists'] and s['log_open']


def test_power_fix_preserves_historical_flags_and_requires_a_fresh_probe():
    s=pi.initial();s,_=run(s,'vcgencmd get_throttled')
    assert pi.throttled(s)==0x50005 and not pi.goal(s,4)
    s,_=pi.apply(s,'part','good');assert pi.throttled(s)==0x50000 and not pi.goal(s,4)
    s,_=run(s,'vcgencmd get_throttled');assert pi.goal(s,4)
    s,_=run(s,'sudo reboot');assert pi.throttled(s)==0
    _,output=run(s,'vcgencmd measure_volts');assert 'NOT USB input' in output


@pytest.mark.parametrize('command',['cat /etc/passwd','sudo rm -rf /','curl https://example.com','curl localhost; whoami','echo $(env)','sudo chmod -R 777 /','python -c print(1)','echo hi > /etc/nginx/sites-enabled/site'])
def test_arbitrary_commands_never_execute_or_mutate_fault_state(command):
    original=pi.initial();s,output=run(original,command)
    expected=copy.deepcopy(original);expected['revision']=1
    assert s==expected and output


def test_public_session_state_does_not_leak_reference_fault_or_private_data():
    definition={'engine_id':'linux_fault','step':0,'params':{'variant':1},'engine_state':{'_lab':pi.initial(1),'_private':'secret','paused':False}}
    exposed=labs.public_state(definition)
    assert set(exposed)=={'paused','lab'}
    assert 'app_port' not in exposed['lab'] and 'verified' not in exposed['lab'] and not exposed['lab']['goal_ready']
    assert exposed['lab']['browser']['status']==502


def tool_event(seq=4,**changes):
    return {'session_id':'s','seq':seq,'actor':'candidate','kind':'command','step':1,
            'payload':{'source':'validated_simulator','engine_version':pi.VERSION,'revision':3,
                       'text':'command: curl -I localhost\nHTTP/1.1 200 OK'},**changes}


def test_tool_evidence_requires_exact_result_and_server_tool_provenance():
    event=tool_event();claim=ClaimDraft(text='You verified the proxy response.',polarity='strength',
        evidence_seq=[4],quotes=['HTTP/1.1 200 OK'],skill_id='infra.reverse_proxy',rule='tool_action')
    assert verify(claim,[event],'s')[0]=='verified'
    for invalid in [tool_event(actor='interviewer'),tool_event(session_id='other'),tool_event(kind='turn'),
                    tool_event(payload={**event['payload'],'source':'client'}),tool_event(payload={**event['payload'],'text':'HTTP/1.1 502 Bad Gateway'})]:
        assert verify(claim,[invalid],'s')[0]=='rejected'
    assert verify(claim.model_copy(update={'evidence_seq':[]} ),[event],'s')[0]=='rejected'
    policy=rubrics.load(pi.definition()['rubric'],'linux_fault')
    output=RubricEvaluation(criteria=[{'id':c.id,'score':3 if c.id=='proxy' else None,'claims':[claim] if c.id=='proxy' else []} for c in policy.evaluators['Linux and power']])
    checked=checked_claims('Linux and power',output,[event],'s',policy)
    assert checked[0]['status']=='verified'
    assert checked_claims('Linux and power',output,[tool_event(step=4)],'s',policy)[0]['status']=='rejected'


def test_actions_are_typed_and_bounded():
    with pytest.raises(ValueError):LabAction(request_id='x',revision=0,step=0,kind='command',text='help')
    with pytest.raises(ValueError):LabAction(request_id='x'*16,revision=-1,step=0,kind='shell',text='help')
    with pytest.raises(ValueError):LabAction(request_id='x'*16,revision=0,step=0,kind='command',text='x'*501)
