import { useState } from 'react';
import { Button } from './ui';
import './PiWorkspace.css';

type BrowserState={status:number;css_status:number;form_status:number;latency_ms:number};
export function PiBrowser({browser,disabled,pending,onAction,contactAttempted=false}:{browser:BrowserState;disabled:boolean;pending:boolean;contactAttempted?:boolean;onAction:(action:string)=>void}){
 const [submitted,setSubmitted]=useState(false);
 const styled=browser.css_status===200;
 return <div className="lab-browser prototype-browser">
  <div className="pi-browser-chrome"><div className="pi-browser-dots" aria-hidden="true"><i/><i/><i/></div><div className="pi-browser-url"><span aria-hidden="true">◉</span>http://pi.local</div><Button size="sm" variant="outline" disabled={disabled} onClick={()=>onAction('refresh')}>Reload</Button></div>
  <div className={`pi-browser-loading ${pending?'loading':''}`} aria-hidden="true"><i/></div>
  <div className="pi-browser-viewport">
   {browser.status!==200?<div className="pi-nginx-error"><h1>{browser.status} Bad Gateway</h1><hr/><p>nginx/1.22.1</p></div>:<div className={`pi-demo-site ${styled?'site-styled':'site-unstyled'}`}>
    <header className="site-nav"><b>Alex Rivera</b><nav><a href="#pi-work">Work</a><a href="#pi-about">About</a><a href="#pi-contact">Contact</a></nav></header>
    <section className="site-hero" id="pi-about"><h1>Embedded engineer.<br/>Small things that run on small computers.</h1><p>Firmware, Linux, and the occasional website on a Raspberry Pi.</p></section>
    <section className="site-projects" id="pi-work"><article><h3>esp32-thermo</h3><p>Temperature logger over I²C.</p></article><article><h3>pi-site</h3><p>This site, served from a Pi in my hallway.</p></article><article><h3>motor-ctl</h3><p>Closed-loop motor controller.</p></article></section>
    <section className="site-contact" id="pi-contact"><h2>Say hello</h2><form onSubmit={e=>{e.preventDefault();setSubmitted(true);onAction('contact');}}><input aria-label="Demo contact email" placeholder="Your email" type="email" disabled={disabled}/><textarea aria-label="Demo contact message" placeholder="Message" disabled={disabled}/><button disabled={disabled}>Send message</button></form>{(submitted||contactAttempted)&&<p role="status" className={browser.form_status===200?'site-response-ok':'site-response-error'}>{pending?'Sending...':browser.form_status===200?'Message sent. Thanks!':'500 Internal Server Error: ENOSPC, no space left on device'}</p>}</section>
   </div>}
  </div>
  <footer className="pi-browser-status"><span>{pending?'Loading...':browser.status!==200?`${browser.status} Bad Gateway`:styled?'200 OK':`200 OK · stylesheet blocked (${browser.css_status})`}</span><span>{browser.status===200?`${browser.latency_ms} ms`:''}</span></footer>
 </div>;
}
