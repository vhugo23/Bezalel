import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { api, type Event, type Model } from '../api/client';
import { schemas } from '../api/schemas';
import { Button, ErrorNotice, Modal } from './ui';

type QuitPlan=Model<'QuitPlan'>;
type QuitResult=Model<'QuitResult'>;
type Reason=Model<'QuitInput'>['reason'];
type Action=NonNullable<Model<'QuitStep'>['action']>;

// Same order and wording as backend/app/v2/exit_plan.py REASONS.
const reasons:Record<Reason,string>={lost:'I don’t know this material',unclear:'I don’t understand what is being asked',time:'I’m out of time',technical:'Voice or the app is not working',wrong_track:'This isn’t what I need to practice',other:'Something else'};
const actions:Record<Action,string>={grade:'Review my answers',restart:'Start again',plan:'Open my plan',intake:'Edit my intake',history:'Open history'};

export function savedQuitPlan(events:Event[]):QuitPlan|null {
  for(const event of events){
    if(event.kind!=='note'||!event.payload.quit)continue;
    const plan=schemas.QuitPlan.safeParse(event.payload.quit);
    if(plan.success)return plan.data as QuitPlan;
  }
  return null;
}

export function QuitLesson({sid,trackId,open,saved,onClose,onResult}:{sid:string;trackId:string;open:boolean;saved:QuitPlan|null;onClose:()=>void;onResult:(result:QuitResult)=>void}) {
  const nav=useNavigate();
  const [reason,setReason]=useState<Reason|null>(null),[note,setNote]=useState('');
  const quit=useMutation({mutationFn:(body:Model<'QuitInput'>)=>api.quit(sid,body),onSuccess:onResult});
  const go=useMutation({mutationFn:async(action:Action)=>{
    if(action==='grade'){await api.end(sid);nav(`/fleet/${sid}`);}
    else if(action==='restart')nav(`/session/${(await api.start(trackId)).id}`);
    else nav(`/${action}`);
  }});
  const plan=saved??quit.data?.plan??null;
  const close=()=>{if(quit.data?.outcome==='moved_on'){quit.reset();setReason(null);setNote('');}onClose();};

  if(plan)return <Modal open={open} onClose={close} title={plan.headline} description={plan.summary}>
    <p className="fine quit-reason">You said: {plan.reason_label}{plan.note?` · “${plan.note}”`:''}</p>
    <ol className="quit-steps">{plan.next_steps.map(step=><li key={step.title}>
      <div><b>{step.title}</b><p>{step.detail}</p></div>
      {step.action&&<Button size="sm" variant="outline" disabled={go.isPending} onClick={()=>go.mutate(step.action as Action)}>{actions[step.action]}</Button>}
    </li>)}</ol>
    <ErrorNotice error={go.error}/>
    <p className="fine">These steps are written from your saved session. They are not AI generated and not a score.</p>
  </Modal>;

  if(quit.data)return <Modal open={open} onClose={close} title="Moving on" description={quit.data.message}>
    <div className="row quit-actions"><Button size="sm" onClick={close}>Got it</Button></div>
  </Modal>;

  return <Modal open={open} onClose={close} title="Stuck on this step?" description="Tell us what is going on. We will skip you to the next step, or end the lesson and work with what you have said so far.">
    <form onSubmit={e=>{e.preventDefault();if(reason)quit.mutate({reason,note});}}>
      <fieldset className="quit-reasons"><legend className="fine">What is stopping you?</legend>
        {(Object.keys(reasons) as Reason[]).map(key=><label key={key} className={reason===key?'on':''}><input type="radio" name="quit-reason" checked={reason===key} onChange={()=>setReason(key)}/>{reasons[key]}</label>)}
      </fieldset>
      <textarea className="quit-note" aria-label="Anything to add (optional)" placeholder="Anything to add? (optional)" rows={2} maxLength={300} value={note} onChange={e=>setNote(e.target.value)}/>
      <ErrorNotice error={quit.error}/>
      <div className="row quit-actions"><Button type="button" variant="ghost" size="sm" onClick={close}>Keep trying</Button><Button size="sm" disabled={!reason||quit.isPending}>{quit.isPending?'Working…':'Continue'}</Button></div>
    </form>
  </Modal>;
}
