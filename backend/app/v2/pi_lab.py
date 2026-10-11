"""Authored, bounded Linux fault simulator. Never invokes a shell or touches files.

Numbers are fixture values, not machine telemetry. Only the supported nginx
server-block grammar is validated; this is not an installed nginx instance.
"""
import copy
import re
import shlex
from . import rubrics

VERSION = 'pi-linux-1'
CONFIG_PATH = '/etc/nginx/sites-enabled/site'
LOG_PATH = '/var/log/site/access.log'
WEB_PATH = '/var/www/site'
CONFIG = 'server {\n    listen 80;\n    location / {\n        proxy_pass http://127.0.0.1:3001;\n    }\n    location /assets/ {\n        root /var/www/site;\n    }\n}\n'
TITLES = ['Read the error','Fix the proxy','Fix the deploy','Free the disk','Check the hardware']
TASKS = [
    'Reproduce the failure. Compare the proxy error log with a direct request to the app, and explain which layer failed.',
    'Repair the upstream configuration. Validate the saved config before reloading, then verify the response.',
    'Investigate the missing stylesheet. Repair access with the least permissions needed and verify it.',
    'The contact form fails. Identify what is consuming disk space, recover it safely, and test the form.',
    'The site works but is slow. Investigate power and throttling, change a suitable part, and check again.',
]
HINTS = [
    ['Try curl -I localhost, tail /var/log/nginx/error.log, and systemctl status site.','Compare the upstream address with a direct request to the port shown in the site service status.'],
    ['Open the editor. Saving is separate from loading the running configuration.','Try sudo nginx -t, then sudo systemctl reload nginx, then curl -I localhost.'],
    ['Try curl -I localhost/assets/app.css and ls -l /var/www/site/assets.','nginx runs as www-data. Avoid making files writable by everyone.'],
    ['Try df -h and du -sh /var/log/*.','An unlinked log can still consume space while a process holds it open. Truncation preserves the path.'],
    ['Try vcgencmd get_throttled and dmesg.','Current bits and historical bits differ. measure_volts core is not the USB supply voltage.'],
]


def initial(variant=0):
    app_port = 3000 if variant == 0 else 4000
    return {'version':VERSION,'variant':variant,'revision':0,'config':CONFIG,
            'app_port':app_port,'active_port':3001,'config_revision':0,'tested_revision':None,
            'owner':'root','mode':0o600,'dir_owner':'root','dir_mode':0o755,'log_exists':True,'allocated':True,'log_open':True,
            'supply':'weak','history':True,'seen':{},'verified':{},'risky':[]}


def readable(s):
    return bool(s['mode'] & (0o400 if s['owner']=='www-data' else 0o004)) and bool(s['dir_mode'] & (0o100 if s['dir_owner']=='www-data' else 0o001))


def website(s, path='/', method='GET'):
    if s['active_port']!=s['app_port']:return 502
    if path.startswith('/assets/'):return 200 if readable(s) else 403
    if method=='POST':return 500 if s['allocated'] else 200
    return 200


def throttled(s):
    return (0x50000 if s['history'] else 0) | (0x5 if s['supply']=='weak' else 0)


def goal(s, step):
    seen=s['seen'];verified=s['verified']
    return [
        bool(seen.get('proxy_error') and seen.get('upstream')),
        s['active_port']==s['app_port'] and bool(verified.get('proxy')),
        readable(s) and not (s['mode'] & 0o002 or s['dir_mode'] & 0o002) and bool(verified.get('css')),
        not s['allocated'] and bool(seen.get('disk') and seen.get('large_log') and verified.get('form')),
        s['supply']=='good' and bool(seen.get('power') and verified.get('power')),
    ][step] if 0<=step<5 else False


def public(s, step):
    # Do not return the hidden fault state or reference solution to a client/model.
    return {'version':VERSION,'revision':s['revision'],'file_path':CONFIG_PATH,'config':s['config'],
            'goal_ready':goal(s,step),'label':'Deterministic simulation · synthetic readings',
            'browser':{'status':website(s),'css_status':website(s,'/assets/app.css'),
                       'form_status':website(s,'/contact','POST'),
                       'latency_ms':2900 if s['supply']=='weak' else 184},
            'supply':'Unbranded USB-C supply' if s['supply']=='weak' else '5 V / 3 A USB-C supply + short cable',
            'temperature_c':48.2}


def parse_config(text):
    # Restricted grammar: reject unsupported directives instead of pretending to compile them.
    found=re.search(r'proxy_pass\s+http://127\.0\.0\.1:(\d{1,5})\s*;',text)
    if not found:return None
    canonical=re.sub(r'proxy_pass\s+http://127\.0\.0\.1:\d{1,5}\s*;','proxy_pass http://127.0.0.1:PORT;',text)
    expected=re.sub(r':3001;',':PORT;',CONFIG)
    if re.sub(r'\s+','',canonical)!=re.sub(r'\s+','',expected):return None
    port=int(found[1])
    return port if 1<=port<=65535 else None


HELP = '''Supported simulation commands (one command at a time):
help, whoami, hostname, pwd, uptime
curl [-I] [-X POST] localhost[:PORT][/PATH]
cat /etc/nginx/sites-enabled/site
tail /var/log/nginx/error.log
systemctl status nginx|site; sudo nginx -t; sudo systemctl reload nginx
ls -l /var/www/site/assets
sudo chown [-R] www-data:www-data /var/www/site[/assets]
sudo chmod [-R] 644|755|777|a+rX /var/www/site[/assets]
df -h; du -sh /var/log/*; sudo truncate -s 0 /var/log/site/access.log
sudo rm /var/log/site/access.log; lsof +L1; sudo systemctl restart site
vcgencmd get_throttled|measure_temp|measure_volts; dmesg; sudo reboot
Use Editor to save config and Pi to swap power. No commands execute on a real machine.'''


def command(s, text):
    try:parts=shlex.split(text)
    except ValueError:return 'Unclosed quote. Nothing changed.'
    if not parts:return 'Enter a command, or help.'
    if any(token in text for token in (';','|','&','`','$(','>','<','\n')):
        return 'This simulator accepts one supported command at a time; no shell expansion or pipelines.'
    sudo=parts[0]=='sudo'
    p=parts[1:] if sudo else parts
    if not p:return 'Enter a command after sudo.'
    if p==['help']:return HELP
    if p==['whoami']:return 'root' if sudo else 'pi'
    if p==['hostname']:return 'raspberrypi (simulated)'
    if p==['pwd']:return '/home/pi'
    if p==['uptime']:return 'up 2 hours, load average: 0.42, 0.31, 0.25 (synthetic)'
    if p==['cat',CONFIG_PATH]:return s['config']
    if p[0] in ('tail','cat','less') and p[-1]=='/var/log/nginx/error.log':
        s['seen']['proxy_error']=True
        if website(s)==502:return f"connect() failed (111: Connection refused) while connecting to upstream, upstream: http://127.0.0.1:{s['active_port']}/"
        if not readable(s):return 'open() /var/www/site/assets/app.css failed (13: Permission denied)'
        return 'No new nginx errors. Historical upstream and permission errors remain in the log.'
    if p[:2]==['systemctl','status'] and len(p)==3 and p[2] in ('site','nginx'):
        return f"{p[2]}.service: active (running)\n"+(f"Node listening on 127.0.0.1:{s['app_port']}" if p[2]=='site' else 'nginx worker user: www-data')
    if p==['nginx','-t']:
        if not sudo:return 'Permission denied: use sudo for the simulated nginx configuration check.'
        if parse_config(s['config']) is None:return 'nginx: restricted simulator configuration check failed; no changes loaded.'
        s['tested_revision']=s['config_revision']
        return 'nginx: supported configuration syntax is ok\nnginx: simulated configuration test is successful'
    if p in (['systemctl','reload','nginx'],['systemctl','restart','nginx'],['nginx','-s','reload']):
        if not sudo:return 'Permission denied: use sudo.'
        port=parse_config(s['config'])
        if port is None:return 'Reload rejected: invalid or unsupported configuration. Previous workers remain active.'
        if s['tested_revision']!=s['config_revision']:s['risky'].append('reload_without_current_test')
        s['active_port']=port;s['verified'].pop('proxy',None)
        return 'nginx reloaded with the saved configuration. Verify the response.'
    if p[0]=='curl':
        if p[-1].startswith('https://'):return 'TLS is outside this simulator. Use an http:// URL or localhost.'
        url=p[-1].removeprefix('http://').removeprefix('https://')
        match=re.fullmatch(r'(localhost|127\.0\.0\.1)(?::(\d+))?(/[^\s]*)?',url)
        options=p[1:-1]
        if not match or options not in ([],['-I'],['-i'],['-X','POST'],['-I','-X','POST']):return 'Supported curl: curl [-I] [-X POST] localhost[:PORT][/PATH]'
        port=int(match[2] or 80);path=match[3] or '/';method='POST' if 'POST' in options else 'GET'
        if port==s['app_port']:
            s['seen']['upstream']=True;return 'HTTP/1.1 200 OK\nNode app reachable directly (simulated)'
        if port!=80:return f'curl: (7) Failed to connect to localhost port {port}'
        code=website(s,path,method)
        if code==200:
            s['verified']['css' if path.startswith('/assets/') else 'form' if method=='POST' else 'proxy']=True
        return f"HTTP/1.1 {code} { {200:'OK',403:'Forbidden',500:'Internal Server Error',502:'Bad Gateway'}[code]}\n"+('write failed: No space left on device' if code==500 else 'Simulated response')
    if p[:2]==['ls','-l'] and len(p)==3 and p[2] in (WEB_PATH,WEB_PATH+'/assets',WEB_PATH+'/assets/app.css'):
        s['seen']['permissions']=True
        mode=oct(s['mode'])[2:];bits=''.join(('r' if s['mode'] & (4<<shift) else '-')+('w' if s['mode'] & (2<<shift) else '-')+('x' if s['mode'] & (1<<shift) else '-') for shift in (6,3,0))
        return f"-{bits} {s['owner']} {s['owner']} 2048 app.css (mode {mode}, simulated)\nParent directories: {s['dir_owner']}, mode {s['dir_mode']:o}"
    if p[0] in ('chown','chmod'):
        if not sudo:return 'Permission denied: use sudo.'
        args=[arg for arg in p[1:] if arg!='-R']
        if len(args)!=2 or args[1] not in (WEB_PATH,WEB_PATH+'/assets',WEB_PATH+'/assets/app.css'):return 'This lab only permits scoped permission changes under /var/www/site.'
        file_target=args[1].endswith('/app.css')
        affects_file=file_target or '-R' in p
        if p[0]=='chown':
            if args[0]!='www-data:www-data':return 'Supported owner: www-data:www-data.'
            if affects_file:s['owner']='www-data'
            if not file_target:s['dir_owner']='www-data'
        else:
            if args[0] not in ('600','644','755','777','a+rX'):return 'Supported modes: 600, 644, 755, 777, a+rX.'
            if affects_file:s['mode']=(s['mode']|0o444|(0o111 if s['mode']&0o111 else 0)) if args[0]=='a+rX' else int(args[0],8)
            if not file_target:s['dir_mode']=(s['dir_mode']|0o555) if args[0]=='a+rX' else int(args[0],8)
            if s['mode'] & 0o002 or s['dir_mode'] & 0o002:s['risky'].append('world_writable')
        s['verified'].pop('css',None)
        return 'Scoped permissions updated (simulated). Verify the stylesheet.'
    if p==['df','-h']:
        s['seen']['disk']=True
        return 'Filesystem      Size  Used Avail Use% Mounted on\n/dev/mmcblk0p2   20G   '+('20G     0 100%' if s['allocated'] else '2G   18G  10%')+' / (synthetic)'
    if p==['du','-sh','/var/log/*'] or p==['du','-sh','/var/log/site'] or p==['du','-sh',LOG_PATH]:
        s['seen']['large_log']=True
        return ('18G' if s['allocated'] and s['log_exists'] else '0')+' /var/log/site/access.log\n12K /var/log/nginx (synthetic)'
    if p==['truncate','-s','0',LOG_PATH]:
        if not sudo:return 'Permission denied: use sudo.'
        if not s['log_exists']:return 'No such file. The old unlinked log may still be open: try lsof +L1.'
        s['allocated']=False;s['verified'].pop('form',None)
        return 'Log truncated in place. Disk allocation released; verify the form.'
    if p==['rm',LOG_PATH]:
        if not sudo:return 'Permission denied: use sudo.'
        s['log_exists']=False
        if not s['log_open']:s['allocated']=False
        return 'Log path removed. An open descriptor keeps its blocks allocated until closed.'
    if p==['lsof','+L1']:return 'node 412 site 5w REG 18G /var/log/site/access.log (deleted)' if not s['log_exists'] and s['allocated'] else 'No deleted open files (simulated).'
    if p==['systemctl','restart','site']:
        if not sudo:return 'Permission denied: use sudo.'
        if not s['log_exists']:s['allocated']=False;s['log_exists']=True
        return 'Site restarted; old descriptors closed and a new access log opened.'
    if p==['vcgencmd','get_throttled']:
        s['seen']['power']=True
        if s['supply']=='good':s['verified']['power']=True
        return f'throttled=0x{throttled(s):x}\nSynthetic: low bits are current flags; high bits are historical flags.'
    if p==['vcgencmd','measure_temp']:return "temp=48.2'C (synthetic)"
    if p in (['vcgencmd','measure_volts'],['vcgencmd','measure_volts','core']):return 'volt=1.2000V (synthetic VC4 core voltage; NOT USB input voltage)'
    if p==['dmesg']:
        return 'Under-voltage detected! (historical synthetic kernel message)' if s['history'] else 'No under-voltage message since simulated reboot.'
    if p==['reboot']:
        if not sudo:return 'Permission denied: use sudo.'
        s['history']=s['supply']=='weak'
        if not s['log_exists']:s['allocated']=False;s['log_exists']=True
        return 'Simulated reboot complete. Persistent configuration and permissions retained.'
    return 'Not implemented in this bounded simulator. Type help for supported commands. Nothing executed.'


def apply(state, kind, text):
    s=copy.deepcopy(state)
    if kind=='command':output=command(s,text)
    elif kind=='edit':
        s['config']=text;s['config_revision']+=1;s['tested_revision']=None
        output='Configuration saved. Running workers still use the previous configuration.'
    elif kind=='part':
        if text not in ('good','weak'):raise ValueError('Unknown power part')
        s['supply']=text;s['verified'].pop('power',None)
        if text=='weak':s['history']=True
        output='Swapped the simulated USB-C supply and cable. Check current throttling flags again.'
    elif kind=='browser':
        if text not in ('refresh','contact'):raise ValueError('Unknown browser action')
        method='POST' if text=='contact' else 'GET'
        code=website(s,'/contact' if text=='contact' else '/',method)
        if code==200:s['verified']['form' if text=='contact' else 'proxy']=True
        output=f'Simulated browser {method}: HTTP {code}.'
    else:raise ValueError('Unknown simulator action')
    s['revision']+=1
    return s,output


def definition(variant=0):
    steps=[{'idx':i,'title':title,'surface':'terminal','task':TASKS[i],
            'hints':HINTS[i],'config':{'simulator':VERSION},'success':{'min_turns':1,'tool_goal':True}}
           for i,title in enumerate(TITLES)]
    criteria=[rubrics.Criterion('proxy','infra.reverse_proxy','Explains the proxy/upstream distinction and verifies a scoped configuration repair.',('quoted_turn','tool_action'),steps=(0,1)),
              rubrics.Criterion('permissions','infra.permissions','Explains and verifies nginx read access without granting world-write permissions.',('quoted_turn','tool_action'),steps=(2,)),
              rubrics.Criterion('disk','infra.disk_logs','Diagnoses disk allocation and verifies safe log recovery; distinguishes unlinking an open log from releasing its blocks.',('quoted_turn','tool_action'),steps=(3,)),
              rubrics.Criterion('power','infra.power_thermals','Distinguishes current from historical throttle flags and verifies suitable power; does not treat VC4 core voltage as USB input.',('quoted_turn','tool_action'),steps=(4,))]
    policy=rubrics.Policy('pi-linux-practice-v1',{'Linux and power':criteria,
        'Debug process':[rubrics.Criterion('method','infra.debug_method','Explains a hypothesis, uses a targeted diagnostic, makes a scoped change and verifies the observed result. Command count alone is not ability.',('quoted_turn','tool_action'),steps=tuple(range(5)))]})
    return {'spec':{'prompt':'A portfolio site on a Raspberry Pi 4 returns 502. Investigate the terminal and explain your reasoning as you work. All commands and readings are simulated.',
                    'steps':steps,'simulator':VERSION,'synthetic':True},
            'params':{'variant':variant},'rubric':rubrics.dump(policy),'validity_report':validate(variant)}


def validate(variant=0):
    s=initial(variant)
    assert website(s)==502 and website(s,'/assets/app.css')==502
    def run(kind,text):
        nonlocal s
        s,_=apply(s,kind,text)
    run('command','tail /var/log/nginx/error.log')
    run('command',f"curl -I localhost:{s['app_port']}")
    assert goal(s,0)
    run('edit',s['config'].replace(':3001;',f":{s['app_port']};"))
    run('command','sudo nginx -t');run('command','sudo systemctl reload nginx');run('command','curl -I localhost')
    assert goal(s,1) and website(s,'/assets/app.css')==403
    run('command','sudo chmod 644 /var/www/site/assets/app.css');run('command','curl -I localhost/assets/app.css')
    assert goal(s,2) and website(s,'/contact','POST')==500
    run('command','df -h');run('command','du -sh /var/log/*');run('command',f'sudo truncate -s 0 {LOG_PATH}');run('browser','contact')
    assert goal(s,3) and throttled(s)&0xf
    run('command','vcgencmd get_throttled');run('part','good');run('command','vcgencmd get_throttled')
    assert goal(s,4) and throttled(s)==0x50000 and not s['risky']
    return {'kind':'deterministic_reference_run','engine':VERSION,'semantic_guarantee':False,
            'checks':['broken_symptoms_reproduced','five_reference_goals_pass','historical_power_flags_retained'],
            'label':'Hand-built simulator checked by a reference run; authored rubric, human calibration pending'}
