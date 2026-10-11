import type { Annotation, Stroke } from '../api/client';
export const WIDTH=900, HEIGHT=540;
export function bounds(stroke:Stroke){
 if(!stroke.points.length||stroke.points.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<0||p.x>WIDTH||p.y<0||p.y>HEIGHT)) throw new Error('Invalid stroke geometry');
 const xs=stroke.points.map(p=>p.x),ys=stroke.points.map(p=>p.y);const x=Math.max(0,Math.min(...xs)-12),y=Math.max(0,Math.min(...ys)-12),right=Math.min(WIDTH,Math.max(...xs)+12),bottom=Math.min(HEIGHT,Math.max(...ys)+12);
 return {x,y,w:right-x,h:bottom-y,cx:(x+right)/2,cy:(y+bottom)/2,rx:(right-x)/2,ry:(bottom-y)/2};
}
export function validateMarks(marks:Annotation[],strokes:Stroke[]){
 if(marks.length>4||new Set(strokes.map(s=>s.id)).size!==strokes.length)throw new Error('Invalid annotation batch');
 return marks.map(mark=>{const target=strokes.find(s=>s.id===mark.target);if(!target)throw new Error('Annotation refers to an unknown stroke');return {...mark,geometry:bounds(target)};});
}
export function drawStrokes(ctx:CanvasRenderingContext2D,strokes:Stroke[]){
 ctx.clearRect(0,0,WIDTH,HEIGHT);ctx.fillStyle='#ffffff';ctx.fillRect(0,0,WIDTH,HEIGHT);
 ctx.fillStyle='#f0f1f6';for(let x=30;x<WIDTH;x+=30)for(let y=30;y<HEIGHT;y+=30){ctx.beginPath();ctx.arc(x,y,.8,0,Math.PI*2);ctx.fill();}
 ctx.lineCap='round';ctx.lineJoin='round';
 for(const s of strokes){const first=s.points[0],last=s.points[s.points.length-1];if(!first)continue;ctx.strokeStyle=s.id==='limiter'?'#4f46e5':'#343641';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=2;
  if(s.kind==='rect'){ctx.beginPath();ctx.roundRect(first.x,first.y,last.x-first.x,last.y-first.y,9);ctx.stroke();ctx.font='14px system-ui';ctx.textAlign='center';ctx.fillText(s.label||'',(first.x+last.x)/2,(first.y+last.y)/2+5);}
  else if(s.kind==='text'){ctx.font='12px system-ui';ctx.textAlign='left';ctx.fillText(s.label||'',first.x,first.y);}
  else{ctx.beginPath();ctx.moveTo(first.x,first.y);for(const p of s.points){ctx.lineTo(p.x,p.y);}if(s.points.length===1)ctx.lineTo(first.x+.1,first.y+.1);ctx.stroke();if(s.kind==='arrow'){const a=Math.atan2(last.y-first.y,last.x-first.x);ctx.beginPath();ctx.moveTo(last.x-10*Math.cos(a-.5),last.y-10*Math.sin(a-.5));ctx.lineTo(last.x,last.y);ctx.lineTo(last.x-10*Math.cos(a+.5),last.y-10*Math.sin(a+.5));ctx.stroke();}}
 }
}
export function drawMarks(ctx:CanvasRenderingContext2D,marks:Annotation[],active=-1,progress=1){
 ctx.clearRect(0,0,WIDTH,HEIGHT);ctx.lineCap='round';ctx.lineWidth=3;
 marks.forEach((m,index)=>{const p=index===active?progress:1;const {x,y,w,h,cx,cy,rx,ry}=m.geometry;ctx.strokeStyle=m.severity==='problem'?'#dc2626':'#0d9488';ctx.fillStyle=ctx.strokeStyle;ctx.globalAlpha=1;ctx.beginPath();
  if(m.kind==='circle'){ctx.ellipse(cx,cy,Math.max(rx,3),Math.max(ry,3),0,-Math.PI/2,-Math.PI/2+Math.PI*2*p);ctx.stroke();}
  else if(m.kind==='highlight'){ctx.globalAlpha=.16*p;ctx.fillRect(x,y,w,h);ctx.globalAlpha=1;}
  else if(m.kind==='sticky'){ctx.globalAlpha=p;ctx.fillStyle='#ccfbf1';ctx.fillRect(x,y,Math.min(w+80,WIDTH-x),Math.max(h,45));ctx.fillStyle='#115e59';ctx.font='12px system-ui';ctx.textAlign='left';ctx.fillText(m.speech.slice(0,42),x+6,y+20);ctx.globalAlpha=1;}
  else if(m.kind==='cross'){ctx.moveTo(x,y);ctx.lineTo(x+w*p,y+h*p);ctx.moveTo(x+w,y);ctx.lineTo(x+w-w*p,y+h*p);ctx.stroke();}
  else if(m.kind==='check'){ctx.moveTo(x,cy);ctx.lineTo(cx,cy+h*.3*p);ctx.lineTo(x+w*p,y);ctx.stroke();}
  else{const yy=m.kind==='underline'?y+h:cy;ctx.moveTo(x,yy);ctx.lineTo(x+w*p,yy);ctx.stroke();if(m.kind==='arrow'&&p===1){ctx.beginPath();ctx.moveTo(x+w-10,yy-7);ctx.lineTo(x+w,yy);ctx.lineTo(x+w-10,yy+7);ctx.stroke();}}
  if(index===active){const px=Math.max(0,Math.min(840,cx+rx*Math.cos(Math.PI*2*p))),py=Math.max(0,Math.min(495,cy+ry*Math.sin(Math.PI*2*p)));ctx.fillStyle='#0d9488';ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(px+4,py+20);ctx.lineTo(px+10,py+13);ctx.lineTo(px+18,py+13);ctx.fill();ctx.fillRect(px+15,py+21,43,19);ctx.fillStyle='white';ctx.font='11px system-ui';ctx.textAlign='left';ctx.fillText('Dana',px+20,py+34);}
 });
}
