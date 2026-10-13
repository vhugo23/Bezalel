import { useState, type ReactNode } from 'react';
import { Button } from './ui';
import './PiWorkspace.css';

const keywords=/\b(server|listen|server_name|root|location|try_files|expires|proxy_pass|proxy_set_header)\b/g;
function highlight(text:string){return text.split(keywords).map((part,i)=>i%2?<span className="nginx-keyword" key={i}>{part}</span>:part);}
export function NginxEditor({value,saved,path,disabled,onChange,onSave}:{value:string;saved:string;path:string;disabled:boolean;onChange:(value:string)=>void;onSave:()=>void}){
 const [full,setFull]=useState(false);
 const dirty=value!==saved;
 const lines=value.split('\n');
 let offset=0;
 return <div className="lab-editor nginx-editor">
  <header className="nginx-toolbar"><code>{path}</code><Button size="sm" disabled={disabled||!dirty} onClick={onSave}>Save config</Button></header>
  {full?<textarea className="nginx-full" aria-label="nginx configuration" spellCheck={false} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}/>:<div className="nginx-code" aria-label="nginx configuration">
   {lines.map((line,index)=>{
    const start=offset;offset+=line.length+1;
    const match=/\bproxy_pass\s+https?:\/\/[^\s;:]+:(\d*)/.exec(line);
    let content:ReactNode=highlight(line);
    if(match){const at=match.index+match[0].length-match[1].length;content=<>{highlight(line.slice(0,at))}<input aria-label="Upstream port" inputMode="numeric" maxLength={5} disabled={disabled} value={match[1]} onChange={e=>onChange(value.slice(0,start+at)+e.target.value.replace(/\D/g,'')+value.slice(start+at+match[1].length))}/>{highlight(line.slice(at+match[1].length))}</>;}
    return <div className={`nginx-line ${match?'upstream-line':''}`} key={index}><span className="nginx-line-number" aria-hidden="true">{index+1}</span><span>{content||' '}</span></div>;
   })}
  </div>}
  <footer className="nginx-status"><span role="status">{dirty?'Unsaved changes':'Not modified'}{!dirty&&value!==''?' · Test before reloading nginx':''}</span><button type="button" onClick={()=>setFull(!full)}>{full?'Guided editor':'Edit full file'}</button></footer>
 </div>;
}
