// @ts-nocheck
// Story intro director, ported from prototype.html: the in-scene monitor (ScreenSim),
// synthesized sound effects, a flat fallback without WebGL, and the timed intro script.
let fast=false;
const wait=ms=>new Promise(r=>setTimeout(r,ms));

const ScreenSim=(()=>{
  const W=1280,H=720;
  function create(){
    const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;const x=canvas.getContext('2d');
    const tmp=document.createElement('canvas');tmp.width=W;tmp.height=H;const tx=tmp.getContext('2d');
    const sim={canvas,tint:[.3,.8,1],typing:false,dirty:true,mode:'rej',t0:performance.now(),cursor:{x:900,y:560,show:false,down:0},corrupt:0,btn:{x:0,y:0,w:0,h:0},btnHover:0,toastAt:null,openAt:null,_tok:0,bootAt:0,glitchAmt:0};
    const FONT='-apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,"Segoe UI",system-ui,sans-serif',MONO='ui-monospace,SFMono-Regular,Menlo,Consolas,monospace';
    const rr=(c,a,b,w,h,r)=>{c.beginPath();c.moveTo(a+r,b);c.arcTo(a+w,b,a+w,b+h,r);c.arcTo(a+w,b+h,a,b+h,r);c.arcTo(a,b+h,a,b,r);c.arcTo(a,b,a+w,b,r);c.closePath();};
    const wrap=(c,text,xx,yy,maxW,lh)=>{const words=text.split(' ');let line='';for(const w of words){const t=line+w+' ';if(c.measureText(t).width>maxW&&line){c.fillText(line,xx,yy);line=w+' ';yy+=lh;}else line=t;}c.fillText(line,xx,yy);return yy+lh;};
    const MAILS={
      rej:{from:'Northwind Talent',addr:'no-reply@northwind.io',subj:'[REJECTION] Embedded SWE',body:['Hi Alex,','Thank you for interviewing for the Embedded SWE role.','We have decided to move forward with other candidates.','Best of luck,','Northwind Talent'],btn:null},
      pc:{from:'PrepCrew',addr:'offers@prepcrew-mail.co',subj:'Tired of all the rejections?',body:['Hello,','Tired of all the rejections?','You are not alone. Thousands of engineers just like you are already getting ready with PrepCrew.','Click below to claim your FREE practice interview.','Limited spots. Act now!'],btn:'Get ready'},
      offer:{from:'Northwind Talent',addr:'no-reply@northwind.io',subj:'Offer: Embedded SWE',body:['Hi Alex,','Your walkthrough of the Pi outage was the clearest we saw all year. You checked each layer before you touched it.','We would love to have you on the team. Your offer letter is attached.','Northwind Talent'],btn:'View offer'}
    };
    const LIST=[['Helio Systems','[REJECTION] Firmware Eng','Mon'],['Cobalt Labs','[REJECTION] Robotics SWE','Fri'],['Arcline','[REJECTION] Systems Eng','Wed'],['Vantage','[REJECTION] SWE II','Oct 2'],['Orbit Robotics','[REJECTION] Embedded','Sep 28']];
    function drawMail(c,kind,opts){
      const m=MAILS[kind];const dark=true;
      c.fillStyle='#0f1114';c.fillRect(0,0,W,H);
      /* title bar */
      c.fillStyle='#16191d';c.fillRect(0,0,W,48);['#ef4444','#f59e0b','#22c55e'].forEach((col,i)=>{c.fillStyle=col;c.globalAlpha=.8;c.beginPath();c.arc(26+i*20,24,6,0,7);c.fill();});c.globalAlpha=1;
      c.fillStyle='#8b929a';c.font=`500 15px ${FONT}`;c.textAlign='center';c.fillText('Mail — Inbox',W/2,29);c.textAlign='left';
      /* sidebar */
      c.fillStyle='#12151a';c.fillRect(0,48,230,H-48);c.font=`500 16px ${FONT}`;
      [['Inbox',opts.unread],['Starred',''],['Sent',''],['Rejected','12'],['Drafts','']].forEach(([n,b],i)=>{const yy=96+i*40;if(i===0){c.fillStyle='#1d2127';rr(c,12,yy-24,206,34,8);c.fill();}c.fillStyle=i===0?'#f4f4f5':'#9aa1a9';c.fillText(n,30,yy);if(b){c.textAlign='right';c.fillStyle=n==='Rejected'?'#f87171':'#9aa1a9';c.fillText(b,206,yy);c.textAlign='left';}});
      /* list */
      c.fillStyle='#14171b';c.fillRect(230,48,360,H-48);c.fillStyle='#1d2127';c.fillRect(589,48,1,H-48);
      const slide=opts.slide||0;let yy=48+(opts.newItem?(1-slide)*-92+0:0);
      const items=(opts.newItem?[['PrepCrew','Tired of all the rejections?','now',true]]:[]).concat(kind==='rej'?[['Northwind Talent','[REJECTION] Embedded SWE','now',true]]:[['Northwind Talent','[REJECTION] Embedded SWE','1m']]).concat(LIST.map(l=>[l[0],l[1],l[2]]));
      c.save();c.beginPath();c.rect(230,48,360,H-48);c.clip();
      items.forEach((it,i)=>{const iy=48+i*92+(opts.newItem?(slide-1)*92:0);const sel=(opts.newItem?i===0&&opts.selectNew:i===0);if(sel){c.fillStyle='#1d2430';c.fillRect(231,iy,358,92);}
        c.fillStyle=it[0]==='PrepCrew'?'#fff':(sel?'#f4f4f5':'#cfd3d8');c.font=`600 16px ${FONT}`;c.fillText(it[0],254,iy+32);c.fillStyle='#707880';c.font=`500 13px ${FONT}`;c.textAlign='right';c.fillText(it[2],570,iy+32);c.textAlign='left';
        c.fillStyle=sel?'#e5e7eb':'#8b929a';c.font=`500 14.5px ${FONT}`;c.fillText(it[1].length>34?it[1].slice(0,33)+'…':it[1],254,iy+56);c.fillStyle='#4b525a';c.fillRect(254,iy+91,316,1);
        if(it[3]&&!sel){c.fillStyle='#60a5fa';c.beginPath();c.arc(240,iy+28,3.5,0,7);c.fill();}});
      c.restore();
      /* reading pane */
      const rx=618;c.fillStyle='#0f1114';c.fillRect(590,48,W-590,H-48);
      c.fillStyle=kind==='pc'?'#fff':(kind==='offer'?'#22c55e':'#3b3f46');c.beginPath();c.arc(rx+22,106,22,0,7);c.fill();c.fillStyle=kind==='pc'?'#09090b':'#fff';c.font=`700 18px ${FONT}`;c.textAlign='center';c.fillText(m.from[0],rx+22,112);c.textAlign='left';
      c.fillStyle='#f4f4f5';c.font=`600 17px ${FONT}`;c.fillText(m.from,rx+58,100);c.fillStyle='#707880';c.font=`500 13.5px ${FONT}`;c.fillText(m.addr+'  ·  to me',rx+58,121);
      c.fillStyle='#f4f4f5';c.font=`700 25px ${FONT}`;const sy=wrap(c,m.subj,rx,182,W-rx-50,32);
      c.font=`400 17.5px ${FONT}`;c.fillStyle='#c5cad0';let by=sy+14;
      m.body.forEach((p,i)=>{c.fillStyle=i===0?'#e5e7eb':'#b4bac2';by=wrap(c,p,rx,by,W-rx-60,27)+10;});
      if(m.btn){const bw=186,bh=50,bx=rx,byy=by+14;const hv=opts.hover||0;c.save();if(hv>0){c.shadowColor='rgba(255,255,255,.35)';c.shadowBlur=22*hv;}c.fillStyle=kind==='offer'?'#22c55e':(hv>0?'#fff':'#f4f4f5');rr(c,bx,byy+(opts.down?1.5:0),bw,bh,12);c.fill();c.restore();c.fillStyle='#09090b';c.font=`600 17px ${FONT}`;c.textAlign='center';c.fillText(m.btn+'  →',bx+bw/2,byy+31+(opts.down?1.5:0));c.textAlign='left';sim.btn={x:bx,y:byy,w:bw,h:bh};}
    }
    function toast(c,t){/* t 0..1 slide-in */const e=1-Math.pow(1-t,3);const w=420,h=86,xx=W-w-24,yy=64+(-110)*(1-e);c.save();c.shadowColor='rgba(0,0,0,.5)';c.shadowBlur=24;c.fillStyle='#1c2026';rr(c,xx,yy,w,h,14);c.fill();c.restore();c.strokeStyle='#2a3038';c.lineWidth=1;rr(c,xx,yy,w,h,14);c.stroke();c.fillStyle='#fff';rr(c,xx+16,yy+18,40,40,10);c.fill();c.fillStyle='#09090b';c.font=`700 21px ${FONT}`;c.textAlign='center';c.fillText('P',xx+36,yy+46);c.textAlign='left';c.fillStyle='#f4f4f5';c.font=`600 16px ${FONT}`;c.fillText('PrepCrew',xx+72,yy+34);c.fillStyle='#9aa1a9';c.font=`500 14.5px ${FONT}`;c.fillText('Tired of all the rejections?',xx+72,yy+58);}
    function cursor(c,cu){if(!cu.show)return;const {x:px,y:py}=cu;if(cu.down>0){c.strokeStyle=`rgba(255,255,255,${cu.down*.6})`;c.lineWidth=2;c.beginPath();c.arc(px,py,34*(1-cu.down)+6,0,7);c.stroke();}c.save();c.translate(px,py);c.shadowColor='rgba(0,0,0,.55)';c.shadowBlur=6;c.shadowOffsetY=2;c.fillStyle='#fff';c.strokeStyle='#000';c.lineWidth=1.4;c.beginPath();c.moveTo(0,0);c.lineTo(0,22);c.lineTo(5.5,17);c.lineTo(9.5,26);c.lineTo(13,24.5);c.lineTo(9,16);c.lineTo(16,16);c.closePath();c.fill();c.stroke();c.restore();}
    const JUNK=['0xDEADBEEF','segfault','ERR_RETRY','NaN','rm -rf doubt','null','kernel panic','404','0x00','overflow','while(!ready)','#!/bin/sh','undefined','ECONNRESET'];
    function corrupt(c,src,k){/* src canvas -> c with progressive damage, k 0..1 */
      c.drawImage(src,0,0);const n=Math.floor(4+k*38);
      for(let i=0;i<n;i++){const sy=Math.random()*H,sh=3+Math.random()*(10+k*90),dx=(Math.random()-.5)*(30+k*420);c.drawImage(src,0,sy,W,sh,dx,sy,W,sh);}
      c.globalCompositeOperation='screen';c.globalAlpha=.35+k*.4;c.drawImage(src,-6-k*22,0);c.globalCompositeOperation='lighter';c.globalAlpha=.25+k*.3;c.drawImage(src,8+k*26,2);c.globalAlpha=1;c.globalCompositeOperation='source-over';
      /* noise blocks */
      for(let i=0;i<Math.floor(k*60);i++){c.fillStyle=Math.random()<.5?'#000':(Math.random()<.5?'#00ffb3':'#ff1f5a');c.globalAlpha=Math.random()*.7;const bw=10+Math.random()*180,bh=4+Math.random()*30;c.fillRect(Math.random()*W,Math.random()*H,bw,bh);}c.globalAlpha=1;
      /* junk text */
      c.font=`600 ${14+Math.floor(k*14)}px ${MONO}`;for(let i=0;i<Math.floor(k*26);i++){c.fillStyle=Math.random()<.5?'#00ffb3':'#ff3b6b';c.fillText(JUNK[Math.floor(Math.random()*JUNK.length)],Math.random()*W,Math.random()*H);}
      /* scanlines */
      c.fillStyle='rgba(0,0,0,.16)';for(let y=0;y<H;y+=3)c.fillRect(0,y,W,1);
      /* fade to black at the end */
      if(k>.82){c.fillStyle=`rgba(0,0,0,${Math.min(1,(k-.82)/.18)})`;c.fillRect(0,0,W,H);}
    }
    function boot(c,t,hov,down){
      c.fillStyle='#000';c.fillRect(0,0,W,H);
      const lines=['> hello, Alex.','> starting PrepCrew ...'];c.font=`500 22px ${MONO}`;
      const fadeT=Math.max(0,Math.min(1,(t-1.5)/.7));
      lines.forEach((l,i)=>{const st=.15+i*.5;const n=Math.max(0,Math.min(l.length,Math.floor((t-st)*46)));if(n>0){c.globalAlpha=1-fadeT;c.fillStyle='#7dffc4';c.fillText(l.slice(0,n)+(n<l.length&&Math.floor(t*10)%2?'▌':''),90,200+i*38);c.globalAlpha=1;}});
      if(fadeT>0){const e=1-Math.pow(1-fadeT,3);c.save();c.globalAlpha=e;
        const g=c.createRadialGradient(W/2,290,10,W/2,290,460);g.addColorStop(0,'rgba(255,255,255,.16)');g.addColorStop(1,'rgba(255,255,255,0)');c.fillStyle=g;c.fillRect(0,0,W,H);
        c.font=`700 96px ${FONT}`;const tw=c.measureText('PrepCrew').width;const total=92+30+tw,mx=(W-total)/2,my=222;
        /* the PrepCrew monogram (public/prepcrew.svg), 64-unit artboard scaled to 92px */
        c.save();c.translate(mx,my);c.scale(92/64,92/64);c.shadowColor='rgba(99,102,241,.55)';c.shadowBlur=18;c.fillStyle='#5b54ee';c.fill(new Path2D('M12 54V18a10 10 0 0 1 10-10h15c12.15 0 22 9.85 22 22s-9.85 22-22 22H29V40h8a10 10 0 1 0 0-20H24v34H12Z'),'evenodd');c.restore();
        c.fillStyle='#fff';c.textAlign='left';c.fillText('PrepCrew',mx+122,my+73);
        c.fillStyle='#9aa1a9';c.font=`500 26px ${FONT}`;c.textAlign='center';c.fillText('Find where you stalled. Fix it.',W/2,420);c.textAlign='left';c.restore();}
      const bt=Math.max(0,Math.min(1,(t-2.4)/.5));
      if(bt>0){const bw=200,bh=60,bx=W/2-bw/2,by=482+(1-bt)*10+(down?2:0);c.save();c.globalAlpha=bt;if(hov){c.shadowColor='rgba(255,255,255,.5)';c.shadowBlur=30;}c.fillStyle=hov?'#fff':'#ececef';rr(c,bx,by,bw,bh,14);c.fill();c.restore();c.save();c.globalAlpha=bt;c.fillStyle='#09090b';c.font=`600 22px ${FONT}`;c.textAlign='center';c.fillText('Enter  ↵',bx+bw/2,by+38);c.restore();sim.btn={x:bx,y:482,w:bw,h:bh};}
    }
    function drawHome(c){
      c.fillStyle='#fafafa';c.fillRect(0,0,W,H);c.fillStyle='#fff';c.fillRect(0,0,W,64);c.fillStyle='#e4e4e7';c.fillRect(0,64,W,1);
      c.fillStyle='#18181b';rr(c,36,20,26,26,7);c.fill();c.strokeStyle='#fff';c.lineWidth=3;c.beginPath();c.moveTo(43,33);c.lineTo(48,38);c.lineTo(56,29);c.stroke();
      c.fillStyle='#09090b';c.font=`600 22px ${FONT}`;c.fillText('PrepCrew',74,40);
      c.font=`600 40px ${FONT}`;c.fillText('Welcome back, Alex',120,170);c.fillStyle='#71717a';c.font=`400 20px ${FONT}`;c.fillText('Pick up where you stalled.',120,208);
      [[120,260,'Fix the site on the Pi','Embedded & Hardware'],[560,260,'Skill map','Your gaps, ranked'],[1000-60,260,'Last session','—']].forEach(([cx,cy,t1,t2],i)=>{c.fillStyle='#fff';rr(c,cx,cy,i===2?160:400,200,16);c.fill();c.strokeStyle='#e4e4e7';c.lineWidth=1.5;rr(c,cx,cy,i===2?160:400,200,16);c.stroke();c.fillStyle='#09090b';c.font=`600 22px ${FONT}`;c.fillText(t1,cx+26,cy+50);c.fillStyle='#71717a';c.font=`400 16px ${FONT}`;c.fillText(t2,cx+26,cy+78);});
      c.fillStyle='#18181b';rr(c,146,420,150,10,5);c.fill();c.fillStyle='#e4e4e7';rr(c,146,440,230,10,5);c.fill();
    }
    sim.set=(mode,extra)=>{sim.mode=mode;sim.t0=performance.now();Object.assign(sim,extra||{});};
    sim.moveCursor=(tx,ty,ms=900)=>{const tok=++sim._tok;const sx=sim.cursor.x,sy=sim.cursor.y,t0=performance.now();sim.cursor.show=true;return new Promise(res=>{const st=()=>{if(tok!==sim._tok)return res();const k=Math.min(1,(performance.now()-t0)/ms);const e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;const wob=Math.sin(k*Math.PI)*14;sim.cursor.x=sx+(tx-sx)*e;sim.cursor.y=sy+(ty-sy)*e-wob;if(k<1)setTimeout(st,16);else res();};st();});};
    sim.click=()=>{sim.cursor.down=1;const t0=performance.now();const f=()=>{const k=(performance.now()-t0)/420;sim.cursor.down=Math.max(0,1-k);if(k<1)setTimeout(f,16);};f();};
    sim.reset=()=>{sim._tok++;sim.mode='rej';sim.t0=performance.now();sim.cursor={x:1000,y:600,show:false,down:0};sim.corrupt=0;sim.toastAt=null;sim.btnHover=0;sim.holdDown=false;sim.typing=false;};
    sim.draw=()=>{
      const now=performance.now(),t=(now-sim.t0)/1000;
      const hov=sim.btn.w&&sim.cursor.show&&sim.cursor.x>=sim.btn.x&&sim.cursor.x<=sim.btn.x+sim.btn.w&&sim.cursor.y>=sim.btn.y&&sim.cursor.y<=sim.btn.y+sim.btn.h?1:0;
      const m=sim.mode;
      if(m==='rej'){drawMail(x,'rej',{unread:'47'});sim.tint=[.55,.7,.85];}
      else if(m==='pcnew'||m==='pc'){const sl=Math.min(1,(now-(sim.toastAt||now))/700);const sel=sim.openAt&&now-sim.openAt>0;
        if(sel||m==='pc'){drawMail(x,'pc',{unread:'48',newItem:true,slide:1,selectNew:true,hover:hov,down:sim.cursor.down>.4});}else{drawMail(x,'rej',{unread:'48',newItem:true,slide:Math.min(1,Math.max(0,(now-(sim.toastAt||now)-500)/600)),selectNew:false});}
        if(sim.toastAt&&!sel){const tt=(now-sim.toastAt)/1000;const k=tt<.5?tt/.5:(tt<2.6?1:Math.max(0,1-(tt-2.6)/.4));toast(x,k);}
        sim.tint=[.75,.9,1];}
      else if(m==='corrupt'){const k=Math.min(1,t/sim.corruptMs*1000);sim.corrupt=k;drawMail(tx,'pc',{unread:'48',newItem:true,slide:1,selectNew:true,hover:1,down:true});corrupt(x,tmp,k);sim.tint=[.3+k*.6,.9-k*.5,.8-k*.3];}
      else if(m==='boot'){boot(x,t,hov,sim.cursor.down>.4);const u=Math.max(0,Math.min(1,(t-1.5)/.8));sim.tint=[.4+u*.5,.7+u*.25,.7+u*.3];}
      else if(m==='offer'){drawMail(x,'offer',{unread:'49',hover:hov,down:false});sim.tint=[.7,1,.85];}
      if(m==='corrupt'){/* drawMail wrote to tx? ensure copy */}
      cursor(x,sim.cursor);
      if(m==='corrupt'){x.globalAlpha=1;}
    };
    /* corrupt mode needs to draw into tmp first, then corrupt() onto x: handle by wrapping */
    const _draw=sim.draw;sim.draw=()=>{if(sim.mode==='corrupt'){const now=performance.now(),t=(now-sim.t0)/1000;const k=Math.min(1,t/(sim.corruptMs/1000));sim.corrupt=k;tx.clearRect(0,0,W,H);drawMail(tx,'pc',{unread:'48',newItem:true,slide:1,selectNew:true,hover:1,down:false});cursor(tx,{...sim.cursor,show:k<.5});x.clearRect(0,0,W,H);corrupt(x,tmp,k);sim.tint=[.3+k*.6,.9-k*.5,.8-k*.3];}else _draw();sim.dirty=true;};
    sim.drawHome=drawHome;
    return sim;
  }
  return {create,W,H};
})();

const sfx=(()=>{let ac=null;const ctx=()=>{try{ac=ac||new (window.AudioContext||window.webkitAudioContext)();if(ac.state==='suspended')ac.resume();return ac;}catch(e){return null;}};
 const ok=()=>!fast;
 function tone(f,d,type,v,when,f2){const a=ctx();if(!a||!ok())return;const o=a.createOscillator(),g=a.createGain(),t=a.currentTime+(when||0);o.type=type||'sine';o.frequency.setValueAtTime(f,t);if(f2)o.frequency.exponentialRampToValueAtTime(f2,t+d);g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(v,t+.01);g.gain.exponentialRampToValueAtTime(.0001,t+d);o.connect(g).connect(a.destination);o.start(t);o.stop(t+d+.05);}
 function noise(d,v,fq){const a=ctx();if(!a||!ok())return;const n=a.sampleRate*d,b=a.createBuffer(1,n,a.sampleRate),ch=b.getChannelData(0);for(let i=0;i<n;i++){ch[i]=(Math.random()*2-1)*(Math.random()<.18?0:1);}const s=a.createBufferSource();s.buffer=b;const f=a.createBiquadFilter();f.type='bandpass';f.frequency.value=fq||1800;f.Q.value=.7;const g=a.createGain();g.gain.setValueAtTime(v,a.currentTime);g.gain.exponentialRampToValueAtTime(.0001,a.currentTime+d);s.connect(f).connect(g).connect(a.destination);s.start();}
 return{ping(){tone(880,.5,'sine',.05);tone(1320,.6,'sine',.035,.1);},click(){tone(1500,.05,'square',.02);noise(.04,.05,3000);},glitch(ms){noise(ms/1000,.12,1400);tone(90,ms/1000,'sawtooth',.05,0,28);},thud(){tone(60,.9,'sine',.12,0,30);},rise(){tone(300,1.6,'triangle',.03,0,1400);},resume(){ctx();}};})();

function createFlat(host,sim){
  host.innerHTML='<div class="flat"><div class="flatmon"></div></div>';const mon=host.querySelector('.flatmon');const cv=sim.canvas;cv.style.cssText='width:100%;height:auto;display:block;border-radius:8px';mon.appendChild(cv);
  let raf=0,on=false,shakeV=0,glitchV=0;
  const loop=()=>{raf=requestAnimationFrame(loop);if(!on)return;sim.draw();const sh=shakeV*900;mon.style.translate=`${(Math.random()-.5)*sh}px ${(Math.random()-.5)*sh}px`;mon.style.filter=glitchV>.05?`hue-rotate(${(Math.random()-.5)*glitchV*90}deg) contrast(${1+glitchV*.5}) saturate(${1+glitchV*1.5})`:'';};loop();
  const SC={lowwide:.62,wide:.7,over:.82,push:.98,screen:1.5,endwide:.7,endmed:.95};
  return{flat:true,reset(){mon.style.transition='none';mon.style.transform='scale(.62)';host.style.background='#04070a';shakeV=0;glitchV=0;},setActive(b){on=b;},setPose:()=>Promise.resolve(),
    shot(n,ms){mon.style.transition=`transform ${ms}ms cubic-bezier(.4,0,.2,1)`;mon.style.transform=`scale(${SC[n]||.8})`;return Promise.resolve();},
    look(n,ms){host.style.transition=`background ${ms}ms`;host.style.background=n==='night'?'#04070a':'#dfe7ec';return Promise.resolve();},
    setGlitch:v=>{glitchV=v;},setShake:v=>{shakeV=v;},setDrift(){},tween(ms,fn){return new Promise(res=>{const t0=performance.now();const f=()=>{const k=Math.min(1,(performance.now()-t0)/ms);fn(k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2,k);if(k<1)requestAnimationFrame(f);else res();};f();});},dispose(){cancelAnimationFrame(raf);}};
}

/** Plays the intro into the given elements. Returns controls; onDone fires once (finished or skipped). */
export function startIntro({stage:host,caption,fade,flash,onDone}){
  let alive=true,done=false,st=null;
  const cap=t=>{if(!t){caption.style.opacity=0;return;}caption.textContent=t;caption.style.opacity=1;};
  const finish=()=>{if(done)return;done=true;alive=false;st?.setActive(false);onDone();};
  const run=async()=>{
    sfx.resume();cap('');
    fade.style.transition='none';fade.style.opacity=1;flash.style.transition='none';flash.style.opacity=0;
    const sim=ScreenSim.create();
    try{const {createStage}=await import('./stage.js');st=await createStage(host,{mode:'start',sim});}catch(e){console.warn('3D intro unavailable; using the flat version.',e);}
    if(!alive)return;
    if(!st){host.innerHTML='';st=createFlat(host,sim);}
    st.reset();sim.reset();sim.set('rej');st.setActive(true);
    await wait(250);if(!alive)return;
    fade.style.transition='opacity 1.8s ease';fade.style.opacity=0;st.shot('wide',9000);
    await wait(2000);if(!alive)return;cap('Another rejection.');
    await wait(1900);st.setPose('slump',1600);await wait(1200);if(!alive)return;cap('That makes twelve.');
    await wait(2300);cap('');st.shot('over',3000);st.setPose('face',1500);
    await wait(3600);if(!alive)return;
    sfx.ping();sim.set('pcnew',{toastAt:performance.now(),openAt:null});st.setPose('lift',1000);
    await wait(900);cap('Then, an email.');await wait(2200);if(!alive)return;
    sim.openAt=performance.now();cap('');st.shot('push',2400);st.setPose('lean',1300);await wait(2500);if(!alive)return;
    sim.set('pc',{openAt:sim.openAt});await wait(120);
    await sim.moveCursor(sim.btn.x+sim.btn.w*.5,sim.btn.y+sim.btn.h*.5,1400);if(!alive)return;
    await wait(650);if(!alive)return;sim.click();sfx.click();await wait(380);if(!alive)return;
    sim.set('corrupt',{corruptMs:2600});sfx.glitch(2600);st.shot('screen',3200);
    st.tween(2600,e=>{st.setGlitch(e);st.setShake(e*.06);});await wait(2700);if(!alive)return;
    sim.set('boot');sim.cursor.show=false;st.setGlitch(.25);st.setShake(.01);sfx.thud();await wait(300);st.setGlitch(0);st.setShake(0);
    await wait(3000);if(!alive)return;
    sim.cursor.show=true;await sim.moveCursor(sim.btn.x+sim.btn.w*.5+6,sim.btn.y+sim.btn.h*.5+6,1000);if(!alive)return;
    await wait(450);sim.click();sfx.click();await wait(350);if(!alive)return;sfx.rise();
    flash.style.transition='opacity .5s ease';flash.style.opacity=1;await wait(560);if(!alive)return;
    finish();
  };
  void run();
  return {skip:finish,dispose(){alive=false;st?.setActive(false);st?.dispose?.();}};
}
