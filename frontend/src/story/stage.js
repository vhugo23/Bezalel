// @ts-nocheck
// Story intro stage, ported from prototype.html (dark room, desk, monitor, Mixamo Xbot).
// Kept as plain JavaScript: it is a scripted animation, not app logic.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const easeOut=t=>1-Math.pow(1-t,3);
const lerp=(a,b,t)=>a+(b-a)*t;
const clamp01=v=>Math.max(0,Math.min(1,v));
const rnd=(a,b)=>a+Math.random()*(b-a);

class Tweens{
  constructor(){this.l=[];}
  add(ms,fn,e=ease){return new Promise(res=>{this.l.push({t0:performance.now(),ms,fn,e,res});});}
  step(now){for(let i=this.l.length-1;i>=0;i--){const t=this.l[i];const k=clamp01((now-t.t0)/t.ms);t.fn(t.e(k),k);if(k>=1){this.l.splice(i,1);t.res();}}}
  clear(){this.l.length=0;}
}
function canvasTex(w,h,draw,opts={}){
  const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');draw(x,w,h);
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;if(opts.repeat){t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(...opts.repeat);}
  t.userData.canvas=c;return t;
}
function makeRenderer(host,{alpha=false,maxDpr=2,onSize}={}){
  const r=new THREE.WebGLRenderer({antialias:true,alpha,powerPreference:'high-performance'});
  r.setPixelRatio(Math.min(devicePixelRatio||1,maxDpr));
  r.outputColorSpace=THREE.SRGBColorSpace;r.toneMapping=THREE.ACESFilmicToneMapping;r.toneMappingExposure=1;
  r.shadowMap.enabled=true;r.shadowMap.type=THREE.PCFSoftShadowMap;
  const cv=r.domElement;cv.style.cssText='position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none';
  host.appendChild(cv);
  const size={w:0,h:0};
  const fit=()=>{const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;if(w===size.w&&h===size.h)return;size.w=w;size.h=h;r.setSize(w,h,false);onSize&&onSize(w,h);};
  const ro=new ResizeObserver(fit);ro.observe(host);fit();
  return {renderer:r,size,fit,dispose(){ro.disconnect();r.dispose();cv.remove();}};
}
const mk=(geo,mat,x=0,y=0,z=0,parent=null,cast=true)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=cast;m.receiveShadow=true;parent&&parent.add(m);return m;};
const rbox=(w,h,d,r=.03)=>new RoundedBoxGeometry(w,h,d,3,Math.min(r,w/2-.001,h/2-.001,d/2-.001));
const M=(color,rough=.5,metal=0,extra={})=>new THREE.MeshStandardMaterial({color,roughness:rough,metalness:metal,...extra});


/* ================= Mr.-Robot-style room + Mixamo character ================= */
const XBOT_URLS=['/story/Xbot.glb','https://cdn.jsdelivr.net/gh/mrdoob/three.js@r160/examples/models/gltf/Xbot.glb','https://raw.githubusercontent.com/mrdoob/three.js/r160/examples/models/gltf/Xbot.glb'];
async function loadXbot(){
  for(const u of XBOT_URLS){try{return await new Promise((res,rej)=>new GLTFLoader().load(u,res,undefined,rej));}catch(e){}}
  return null;
}
const BONE_ORDER=['Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','LeftArm','LeftForeArm','LeftHand','RightShoulder','RightArm','RightForeArm','RightHand','LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase','RightUpLeg','RightLeg','RightFoot','RightToeBase'];
class Rig{
  constructor(model,holder){this.model=model;this.holder=holder;this.b={};this.bind={};
    model.traverse(o=>{if(o.isBone){const n=o.name.replace(/^mixamorig:?/,'');this.b[n]=o;this.bind[n]={q:o.quaternion.clone(),p:o.position.clone()};}});
    this.hq=new THREE.Quaternion();this.pq=new THREE.Quaternion();this.dq=new THREE.Quaternion();this.ax=[new THREE.Vector3(1,0,0),new THREE.Vector3(0,1,0),new THREE.Vector3(0,0,1)];this.tmp=new THREE.Vector3();}
  apply(pose){
    for(const n in this.b){this.b[n].quaternion.copy(this.bind[n].q);this.b[n].position.copy(this.bind[n].p);}
    this.model.updateMatrixWorld(true);this.holder.getWorldQuaternion(this.hq);
    const hips=this.b.Hips;if(pose.hip){const s=hips.parent.getWorldScale(this.tmp).x||1;hips.position.set(this.bind.Hips.p.x+pose.hip[0]/s,this.bind.Hips.p.y+pose.hip[1]/s,this.bind.Hips.p.z+pose.hip[2]/s);}
    for(const n of BONE_ORDER){const r=pose[n];const bone=this.b[n];if(!bone)continue;
      if(r){for(const i of [2,1,0]){if(!r[i])continue;bone.updateMatrixWorld(true);bone.parent.getWorldQuaternion(this.pq);
        const axw=this.ax[i].clone().applyQuaternion(this.hq);this.dq.setFromAxisAngle(axw,r[i]*Math.PI/180);
        bone.quaternion.premultiply(this.pq.clone().invert().multiply(this.dq).multiply(this.pq));}}
      bone.updateMatrixWorld(true);}
  }
}
function poseMix(a,b,t){const o={};for(const k of new Set([...Object.keys(a),...Object.keys(b)])){const x=a[k]||[0,0,0],y=b[k]||[0,0,0];o[k]=[lerp(x[0],y[0],t),lerp(x[1],y[1],t),lerp(x[2],y[2],t)];}return o;}
const poseAdd=(p,add)=>{const o={};for(const k in p)o[k]=[...p[k]];for(const k in add){const a=o[k]||[0,0,0];o[k]=[a[0]+add[k][0],a[1]+add[k][1],a[2]+add[k][2]];}return o;};

/* seated base: character space (+Z forward, +X left, +Y up). Units: degrees; hip: meters */
const SIT={hip:[0,-.44,-.1],UpLeg:[0,0,0],LeftUpLeg:[-90,0,4],RightUpLeg:[-90,0,-4],LeftLeg:[88,0,0],RightLeg:[88,0,0],LeftFoot:[-8,0,0],RightFoot:[-8,0,0]};
const mixP=(...ps)=>Object.assign({},...ps);
const POSES={
  /* typing, upright but tired */
  work:mixP(SIT,{Spine:[10,0,0],Spine1:[8,0,0],Spine2:[6,0,0],Neck:[6,0,0],Head:[8,0,0],LeftShoulder:[0,0,4],RightShoulder:[0,0,-4],
    LeftArm:[-38,0,-72],RightArm:[-38,0,72],LeftForeArm:[-60,0,0],RightForeArm:[-60,0,0],LeftHand:[10,0,0],RightHand:[10,0,0]}),
  slump:mixP(SIT,{Spine:[22,0,0],Spine1:[16,0,0],Spine2:[12,0,0],Neck:[18,0,0],Head:[26,0,0],LeftShoulder:[0,0,8],RightShoulder:[0,0,-8],LeftArm:[-14,0,-55],RightArm:[-6,0,72],LeftForeArm:[-78,0,0],RightForeArm:[-26,0,0]}),
  face:mixP(SIT,{Spine:[28,0,0],Spine1:[20,0,0],Spine2:[12,0,0],Neck:[20,0,0],Head:[30,0,0],LeftShoulder:[0,0,10],RightShoulder:[0,0,-10],LeftArm:[-18,0,-52],RightArm:[-18,0,52],LeftForeArm:[-82,0,0],RightForeArm:[-82,0,0]}),
  /* hears the ping: head lifts */
  lift:mixP(SIT,{Spine:[14,0,0],Spine1:[10,0,0],Spine2:[6,0,0],Neck:[0,0,0],Head:[0,0,0],LeftShoulder:[0,0,6],RightShoulder:[0,0,-6],
    LeftArm:[-36,0,-70],RightArm:[-36,0,70],LeftForeArm:[-66,0,0],RightForeArm:[-66,0,0]}),
  /* leans in to the screen */
  lean:mixP(SIT,{Spine:[16,0,0],Spine1:[14,0,0],Spine2:[10,0,0],Neck:[4,0,0],Head:[-4,0,0],LeftShoulder:[0,0,3],RightShoulder:[0,0,-3],
    LeftArm:[-42,0,-70],RightArm:[-40,0,70],LeftForeArm:[-52,0,0],RightForeArm:[-52,0,0]}),
  /* the closer: sitting tall */
  tall:mixP(SIT,{Spine:[-2,0,0],Spine1:[-2,0,0],Spine2:[-2,0,0],Neck:[-4,0,0],Head:[-4,0,0],
    LeftArm:[-30,0,-72],RightArm:[-30,0,72],LeftForeArm:[-68,0,0],RightForeArm:[-68,0,0]}),
  back:mixP(SIT,{Spine:[-12,0,0],Spine1:[-8,0,0],Spine2:[-6,0,0],Neck:[-6,0,0],Head:[-8,0,0],LeftArm:[-8,0,-76],RightArm:[-8,0,76],LeftForeArm:[-20,0,0],RightForeArm:[-20,0,0]}),
  cheer:mixP(SIT,{Spine:[-8,0,0],Spine1:[-4,0,0],Neck:[-8,0,0],Head:[-10,0,0],LeftArm:[-10,0,105],RightArm:[-30,0,72],LeftForeArm:[-25,0,0],RightForeArm:[-62,0,0]})
};

/* ---- little texture factories ---- */
function noiseTex(base,spots,size=512,repeat){return canvasTex(size,size,(x,w,h)=>{x.fillStyle=base;x.fillRect(0,0,w,h);for(let i=0;i<9000;i++){const v=Math.random()*40-20;x.fillStyle=`rgba(${v>0?255:0},${v>0?255:0},${v>0?255:0},${Math.abs(v)/900})`;x.fillRect(Math.random()*w,Math.random()*h,2,2);}for(let i=0;i<spots;i++){const g=x.createRadialGradient(0,0,0,0,0,1);const px=Math.random()*w,py=Math.random()*h,r=30+Math.random()*120;const gg=x.createRadialGradient(px,py,0,px,py,r);gg.addColorStop(0,'rgba(0,0,0,.08)');gg.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=gg;x.fillRect(px-r,py-r,r*2,r*2);}},{repeat});}
function letterTex(seed){return canvasTex(256,330,(x,w,h)=>{x.fillStyle='#e8e8e4';x.fillRect(0,0,w,h);x.fillStyle='#3f3f46';x.font='700 15px Helvetica,Arial';x.fillText(['Northwind','Helio Systems','Cobalt Labs','Arcline','Vantage','Orbit Robotics','Tessel'][seed%7],18,32);x.fillStyle='#a1a1aa';for(let i=0;i<14;i++)x.fillRect(18,54+i*14,(.5+((i*37+seed*13)%50)/100)*(w-36),4);x.fillStyle='#b91c1c';x.font='700 19px Helvetica,Arial';x.save();x.translate(150,248);x.rotate(-.18);x.strokeStyle='#b91c1c';x.lineWidth=3;x.strokeRect(-70,-24,140,38);x.fillText('REGRET',-52,2);x.restore();});}
function cityTex(day){return canvasTex(1024,512,(x,w,h)=>{const g=x.createLinearGradient(0,0,0,h);if(day){g.addColorStop(0,'#bcd9f5');g.addColorStop(1,'#fbe9c8');}else{g.addColorStop(0,'#05080d');g.addColorStop(1,'#16212c');}x.fillStyle=g;x.fillRect(0,0,w,h);
  let px=0;while(px<w){const bw=40+Math.random()*90,bh=120+Math.random()*260;x.fillStyle=day?'#8fa6bf':'#0b1118';x.fillRect(px,h-bh,bw,bh);for(let yy=h-bh+10;yy<h-10;yy+=16)for(let xx=px+6;xx<px+bw-8;xx+=14)if(Math.random()<(day?.12:.28)){x.fillStyle=day?'rgba(255,255,255,.7)':(Math.random()<.2?'#9ae7ff':'#ffd58a');x.globalAlpha=day?.6:.55+Math.random()*.4;x.fillRect(xx,yy,6,8);x.globalAlpha=1;}px+=bw+Math.random()*8;}
  if(!day){x.fillStyle='rgba(120,200,255,.06)';x.fillRect(0,0,w,h);} });}

/* ================= the stage ================= */
export async function createStage(host,cfg){
  const mode=cfg.mode||'start',sim=cfg.sim;
  if(getComputedStyle(host).position==='static')host.style.position='relative';host.style.overflow='hidden';host.style.background='#04070a';
  const tw=new Tweens();
  const cam=new THREE.PerspectiveCamera(36,16/9,.05,60);
  const gl=document.createElement('canvas');gl.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none;opacity:0';host.appendChild(gl);const gx=gl.getContext('2d');
  const R=makeRenderer(host,{maxDpr:1.5,onSize:(w,h)=>{cam.aspect=w/h;cam.updateProjectionMatrix();gl.width=Math.round(w/1.4);gl.height=Math.round(h/1.4);}});
  const renderer=R.renderer;renderer.toneMappingExposure=1.05;
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x04070a);scene.fog=new THREE.FogExp2(0x050a0e,.055);

  /* lights */
  const hemi=new THREE.HemisphereLight(0x6f93a8,0x0a0d10,.5);scene.add(hemi);
  const street=new THREE.SpotLight(0x9fd0ff,420,24,.62,.45,1.2);street.position.set(-2.3,2.15,-5.2);street.target.position.set(.9,.2,1.2);street.castShadow=true;
  street.shadow.mapSize.set(2048,2048);street.shadow.bias=-.0004;street.shadow.camera.near=1;street.shadow.camera.far=24;scene.add(street,street.target);
  const monL=new THREE.PointLight(0x8fdcff,3.2,7,1.6);monL.position.set(1.15,1.2,-1.9);scene.add(monL);
  const lampL=new THREE.SpotLight(0xffc27a,0,9,.6,.6,1.6);lampL.position.set(2.7,1.3,-2.35);lampL.target.position.set(2.3,.75,-2.2);scene.add(lampL,lampL.target);
  const rim=new THREE.DirectionalLight(0x4a90c0,1.1);rim.position.set(-4,3,4);scene.add(rim);

  /* room shell */
  const wallT=noiseTex('#56626b',14,512,[3,2]),floorT=noiseTex('#2c3237',30,512,[4,4]);
  const wallM=new THREE.MeshStandardMaterial({map:wallT,roughness:.95,color:0xd2dce2}),floorM=new THREE.MeshStandardMaterial({map:floorT,roughness:.85,color:0x8f979c}),darkM=M(0x0e1114,.9);
  const box=(w,h,d,mat,x,y,z,cast=true)=>{const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=cast;m.receiveShadow=true;scene.add(m);return m;};
  box(10,.1,12,floorM,0,-.05,1,false);box(10,.1,12,darkM,0,3.25,1,false);
  box(.2,3.3,12,wallM,-4.1,1.6,1);box(.2,3.3,12,wallM,4.1,1.6,1);box(10,3.3,.2,wallM,0,1.6,5.1,false);
  /* back wall with window opening x[-3.5,-1.1] y[1.0,2.6] */
  box(1,3.3,.2,wallM,-4,1.6,-3.1);box(5.6,3.3,.2,wallM,1.7,1.6,-3.1);box(2.4,1,.2,wallM,-2.3,.5,-3.1);box(2.4,.7,.2,wallM,-2.3,2.95,-3.1);
  const cityM=new THREE.MeshBasicMaterial({map:cityTex(false),fog:false,toneMapped:false});const city=new THREE.Mesh(new THREE.PlaneGeometry(9,4.5),cityM);city.position.set(-2.3,1.8,-6.5);scene.add(city);
  /* blinds */
  const slats=[];const slatM=M(0x353a40,.6,.2);
  for(let i=0;i<17;i++){const s=new THREE.Mesh(new THREE.BoxGeometry(2.5,.012,.13),slatM);s.position.set(-2.3,1.0+i*.1,-2.95);s.rotation.x=.95;s.castShadow=true;s.receiveShadow=true;scene.add(s);slats.push(s);}
  box(2.6,.05,.1,M(0x23272b,.6),-2.3,2.63,-2.95,false);box(.04,1.7,.1,M(0x23272b,.6),-3.54,1.8,-3.0,false);box(.04,1.7,.1,M(0x23272b,.6),-1.06,1.8,-3.0,false);

  /* desk + furniture */
  const deskM=M(0x1b1a19,.7,.05),metalM=M(0x2a2f35,.5,.7);
  box(3.2,.05,1.2,deskM,1.6,.745,-2.4);[[0.08,-1.9],[3.12,-1.9],[.08,-2.92],[3.12,-2.92]].forEach(([x,z])=>box(.05,.72,.05,metalM,x,.36,z));
  box(3.0,.03,.9,M(0x121316,.9),1.6,.4,-2.45,false);
  /* monitor */
  const MON=new THREE.Group();MON.position.set(1.4,.77,-2.6);MON.rotation.y=-.3;scene.add(MON);
  mk(new THREE.CylinderGeometry(.14,.16,.02,24),metalM,0,.01,0,MON);mk(new THREE.BoxGeometry(.04,.36,.03),metalM,0,.2,-.03,MON);mk(rbox(1.24,.74,.04,.02),M(0x0d0f12,.4),0,.62,0,MON);
  const screenTex=new THREE.CanvasTexture(sim.canvas);screenTex.colorSpace=THREE.SRGBColorSpace;screenTex.anisotropy=8;
  const screenM=new THREE.MeshBasicMaterial({map:screenTex,toneMapped:false});const screen=new THREE.Mesh(new THREE.PlaneGeometry(1.18,.68),screenM);screen.position.set(0,.62,.022);MON.add(screen);
  mk(rbox(.46,.018,.15,.01),M(0x0d0f12,.5),1.35-1.4+ .0,0,.35,MON).position.set(-.05,.01,.62);mk(rbox(.06,.025,.1,.02),M(0x0d0f12,.5),.32,.012,.62,MON);
  /* props */
  const mug=mk(new THREE.CylinderGeometry(.045,.04,.1,16),M(0xd9dadd,.4),2.15,.82,-2.3,scene);
  mk(new THREE.CylinderGeometry(.04,.04,.01,16),M(0x2b1b12,.3),2.15,.865,-2.3,scene,false);
  const lamp=new THREE.Group();lamp.position.set(2.75,.77,-2.55);scene.add(lamp);mk(new THREE.CylinderGeometry(.09,.1,.02,16),metalM,0,.01,0,lamp);const a1=mk(new THREE.BoxGeometry(.02,.42,.02),metalM,0,.22,0,lamp);a1.rotation.z=.25;const a2=mk(new THREE.BoxGeometry(.02,.4,.02),metalM,-.1,.5,0,lamp);a2.rotation.z=-1.1;mk(new THREE.ConeGeometry(.09,.14,16,1,true),new THREE.MeshStandardMaterial({color:0x1a1c1f,side:THREE.DoubleSide,roughness:.6,metalness:.5}),-.28,.55,0,lamp).rotation.z=Math.PI/2-.35;
  const bulb=mk(new THREE.SphereGeometry(.03,10,10),new THREE.MeshBasicMaterial({color:0x222222}),-.3,.53,0,lamp,false);
  for(let i=0;i<4;i++){const p=new THREE.Mesh(new THREE.PlaneGeometry(.3,.4),new THREE.MeshStandardMaterial({color:0xcfcfca,roughness:.9}));p.rotation.set(-Math.PI/2,0,rnd(-.6,.6));p.position.set(.5+i*.05,.772+i*.002,-2.1+i*.02);p.receiveShadow=true;scene.add(p);}
  for(let i=0;i<3;i++){const c=mk(new THREE.CylinderGeometry(.04,.035,.11,12),M([0x7f1d1d,0x1e3a5f,0x3f3f46][i],.5),.15+i*.17,.8,-2.7,scene);}
  /* rejection letters on back wall */
  const letters=new THREE.Group();scene.add(letters);
  [[2.45,1.55,.08],[2.8,1.85,-.12],[3.15,1.5,.15],[3.5,1.9,-.05],[2.5,2.2,.1],[2.95,2.3,-.1],[3.35,2.25,.07],[3.6,1.45,-.14],[2.2,1.95,.0]].forEach(([x,y,r],i)=>{const m=new THREE.Mesh(new THREE.PlaneGeometry(.26,.34),new THREE.MeshStandardMaterial({map:letterTex(i),roughness:.9}));m.position.set(x,y,-2.985);m.rotation.z=r;m.castShadow=true;m.receiveShadow=true;letters.add(m);const pin=mk(new THREE.SphereGeometry(.012,8,8),new THREE.MeshBasicMaterial({color:0xb91c1c}),x,y+.14,-2.975,letters,false);});
  /* chair */
  const chair=new THREE.Group();chair.position.set(1.4,0,-1.45);chair.rotation.y=Math.PI+.5;scene.add(chair);
  const fab=M(0x14171b,.9);mk(rbox(.5,.08,.5,.03),fab,0,.41,0,chair);mk(rbox(.46,.6,.07,.03),fab,0,.78,-.27,chair).rotation.x=-.08;mk(new THREE.CylinderGeometry(.03,.03,.3,10),metalM,0,.22,0,chair);
  for(let i=0;i<5;i++){const l=mk(new THREE.BoxGeometry(.04,.03,.3),metalM,0,.07,0,chair);l.geometry.translate(0,0,.15);l.rotation.y=i/5*Math.PI*2;mk(new THREE.SphereGeometry(.03,8,8),darkM,Math.sin(i/5*Math.PI*2)*.3,.04,Math.cos(i/5*Math.PI*2)*.3,chair);}
  mk(rbox(.05,.04,.3,.01),fab,.27,.58,-.02,chair);mk(rbox(.05,.04,.3,.01),fab,-.27,.58,-.02,chair);
  /* bed + clutter + shelf */
  mk(rbox(1.1,.32,2.1,.05),M(0x2b3138,.95),-3.35,.2,.2,scene);mk(rbox(1.15,.1,1.4,.05),M(0x39424a,.95),-3.35,.4,.55,scene);mk(rbox(.6,.12,.35,.06),M(0x4a525a,.95),-3.4,.45,-.65,scene);
  mk(rbox(.55,.05,.55,.01),M(0xb48a54,.8),-.2,.03,-.9,scene).rotation.y=.4;mk(new THREE.CylinderGeometry(.04,.035,.14,10),M(0xdddddd,.4),-.15,.1,-.5,scene);
  [[-1.6,.0,-2.2,.5],[-1.2,0,-2.6,.4],[-.8,0,-2.3,.35]].forEach(([x,y,z,s],i)=>mk(rbox(s,s,s,.02),M(0x5d5143,.9),x,s/2,z,scene).rotation.y=i);
  const rug=new THREE.Mesh(new THREE.PlaneGeometry(2.6,1.9),new THREE.MeshStandardMaterial({color:0x1e2326,roughness:1}));rug.rotation.x=-Math.PI/2;rug.position.set(1.2,.004,-.7);rug.receiveShadow=true;scene.add(rug);
  /* dust */
  const dustG=new THREE.BufferGeometry();const N=260;const dp=new Float32Array(N*3);for(let i=0;i<N;i++){dp[i*3]=rnd(-3,2.5);dp[i*3+1]=rnd(.3,2.4);dp[i*3+2]=rnd(-2.6,2.2);}dustG.setAttribute('position',new THREE.BufferAttribute(dp,3));
  const dust=new THREE.Points(dustG,new THREE.PointsMaterial({color:0xcfe8ff,size:.008,transparent:true,opacity:.35,depthWrite:false,sizeAttenuation:true}));scene.add(dust);

  /* character */
  const holder=new THREE.Group();holder.position.copy(chair.position);holder.rotation.y=Math.PI+.5;scene.add(holder);
  let rig=null,curPose=POSES.work,pending=null;const clothM=new THREE.MeshStandardMaterial({color:0x22262b,roughness:.88,metalness:0});const clothM2=new THREE.MeshStandardMaterial({color:0x171a1e,roughness:.8});
  const gltf=await loadXbot();
  if(gltf){const model=gltf.scene;holder.add(model);model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;o.material=o.name==='Beta_Joints'?clothM2:clothM;}});
    rig=new Rig(model,holder);
    /* hood + headphones on the head bone */
    const hb=rig.b.Head;const hood=new THREE.Group();hb.add(hood);hood.position.set(0,.085,.0);
    const hoodM=new THREE.MeshStandardMaterial({color:0x1b1f24,roughness:.92,side:THREE.DoubleSide});
    const shell=new THREE.Mesh(new THREE.SphereGeometry(.128,28,20,0,Math.PI*2,0,Math.PI*.78),hoodM);shell.scale.set(1.05,1.1,1.18);shell.position.set(0,.045,-.012);shell.rotation.x=-.18;shell.castShadow=true;hood.add(shell);
    const cowl=new THREE.Mesh(new THREE.CylinderGeometry(.115,.16,.17,24,1,true),hoodM);cowl.position.set(0,-.115,-.02);cowl.castShadow=true;hood.add(cowl);
    const back=new THREE.Mesh(new THREE.SphereGeometry(.12,20,14),hoodM);back.position.set(0,-.01,-.052);back.scale.set(1.04,1.1,1.04);hood.add(back);
    const nb=rig.b.Neck;const cans=new THREE.Group();nb.add(cans);cans.position.set(0,.03,.018);
    const band=new THREE.Mesh(new THREE.TorusGeometry(.12,.012,8,28,Math.PI*1.25),M(0x0b0c0e,.5,.4));band.rotation.set(Math.PI/2,0,-Math.PI*.12);cans.add(band);
    [-1,1].forEach(s=>{const c=new THREE.Mesh(new THREE.CylinderGeometry(.052,.052,.04,16),M(0x0b0c0e,.5,.3));c.rotation.z=Math.PI/2;c.position.set(s*.115,-.05,.05);cans.add(c);});
    rig.apply(POSES.work);
  }
  let poseMixA=POSES.work,poseMixB=POSES.work,poseK=1;
  function setPose(name,ms=900){if(!rig)return Promise.resolve();const from=currentPoseVal();poseMixA=from;poseMixB=POSES[name]||POSES.work;poseK=0;return tw.add(ms,e=>{poseK=e;});}
  function currentPoseVal(){return poseMix(poseMixA,poseMixB,poseK);}

  /* camera shots */
  const SHOTS={
    wide:{p:[-1.6,1.55,3.1],l:[1.0,1.0,-2.0],f:38},
    over:{p:[-.6,1.4,1.5],l:[1.35,1.1,-2.4],f:30},
    lowwide:{p:[-2.6,.7,2.6],l:[1.2,1.0,-2.0],f:40},
    push:{p:[-.45,1.3,.9],l:[1.35,1.12,-2.55],f:21},
    screen:{p:[-.4,1.42,.5],l:[1.4,1.39,-2.6],f:11.5},
    side:{p:[-2.6,1.0,-1.45],l:[1.4,.85,-1.45],f:26},
    endwide:{p:[-1.4,1.45,3.2],l:[1.2,1.05,-1.9],f:36},
    endmed:{p:[.1,1.35,.9],l:[1.4,1.15,-1.6],f:34}
  };
  const cs={p:new THREE.Vector3(),l:new THREE.Vector3(),f:36};
  const shotStart=SHOTS[mode==='end'?'endwide':'lowwide'];cs.p.fromArray(shotStart.p);cs.l.fromArray(shotStart.l);cs.f=shotStart.f;
  let shake=0,glitch=0,drift=1;
  function shot(name,ms=2000){const s=SHOTS[name];const p0=cs.p.clone(),l0=cs.l.clone(),f0=cs.f;const p1=new THREE.Vector3().fromArray(s.p),l1=new THREE.Vector3().fromArray(s.l);return tw.add(ms,e=>{cs.p.lerpVectors(p0,p1,e);cs.l.lerpVectors(l0,l1,e);cs.f=lerp(f0,s.f,e);});}
  /* looks */
  function look(name,ms=1500){
    const T={night:{hemi:.5,street:420,mon:3.2,fog:.055,exp:1.05,bg:0x04070a,fogc:0x050a0e,lamp:0,city:false,streetC:0x9fd0ff,hemiC:0x6f93a8,hemiG:0x0a0d10},
      flood:{hemi:1.1,street:120,mon:14,fog:.03,exp:1.25,bg:0x9fb6c4,fogc:0x7c909c,lamp:0,city:false,streetC:0xb7e1ff,hemiC:0xd8e8f2,hemiG:0x9fb0b8},
      day:{hemi:4.4,street:1500,mon:2.4,fog:.01,exp:1.4,bg:0xcfe2f1,fogc:0xd6e2ea,lamp:4,city:true,streetC:0xffdca8,hemiC:0xffefd9,hemiG:0xb4b8bb}}[name];
    const f={hemi:hemi.intensity,street:street.intensity,mon:monL.intensity,fog:scene.fog.density,exp:renderer.toneMappingExposure,lamp:lampL.intensity};
    const bg0=scene.background.clone(),fc0=scene.fog.color.clone(),sc0=street.color.clone(),hc0=hemi.color.clone(),hg0=hemi.groundColor.clone();
    if(name==='day'){cityM.map=cityTex(true);cityM.needsUpdate=true;slats.forEach((s,i)=>{s.rotation.x=.25;});}
    return tw.add(ms,e=>{hemi.intensity=lerp(f.hemi,T.hemi,e);street.intensity=lerp(f.street,T.street,e);monL.intensity=lerp(f.mon,T.mon,e);scene.fog.density=lerp(f.fog,T.fog,e);renderer.toneMappingExposure=lerp(f.exp,T.exp,e);lampL.intensity=lerp(f.lamp,T.lamp,e);
      scene.background.copy(bg0).lerp(new THREE.Color(T.bg),e);scene.fog.color.copy(fc0).lerp(new THREE.Color(T.fogc),e);street.color.copy(sc0).lerp(new THREE.Color(T.streetC),e);hemi.color.copy(hc0).lerp(new THREE.Color(T.hemiC),e);hemi.groundColor.copy(hg0).lerp(new THREE.Color(T.hemiG),e);});
  }
  if(mode==='end'){hemi.intensity=4.4;hemi.groundColor.set(0xb4b8bb);street.intensity=1500;street.color.set(0xffdca8);hemi.color.set(0xffefd9);scene.background.set(0xcfe2f1);scene.fog.color.set(0xd6e2ea);scene.fog.density=.012;renderer.toneMappingExposure=1.4;lampL.intensity=4;cityM.map=cityTex(true);slats.forEach(s=>s.rotation.x=.25);monL.intensity=2.4;letters.visible=false;}
  if(rig)rig.apply(POSES[mode==='end'?'tall':'work']);if(mode==='end'){poseMixA=poseMixB=POSES.tall;}

  /* loop */
  let dead=false,raf=0,t0=performance.now(),lastT=t0,active=false,warm=5;
  const px=new THREE.Vector3();
  function frame(now){
    if(dead)return;raf=requestAnimationFrame(frame);R.fit();if(!R.size.w)return;if(!active){if(warm<=0)return;warm--;}
    const dt=Math.min(.05,(now-lastT)/1000);lastT=now;const t=(now-t0)/1000;tw.step(now);
    /* camera with drift + shake */
    const dr=drift*.06;cam.position.set(cs.p.x+Math.sin(t*.31)*dr+(Math.random()-.5)*shake,cs.p.y+Math.sin(t*.23)*dr*.5+(Math.random()-.5)*shake,cs.p.z+Math.cos(t*.27)*dr);cam.lookAt(cs.l.x+(Math.random()-.5)*shake*.6,cs.l.y,cs.l.z);cam.fov=cs.f;cam.updateProjectionMatrix();
    /* character */
    if(rig){let p=currentPoseVal();const br=Math.sin(t*1.5);p=poseAdd(p,{Spine2:[br*.9,0,0],Head:[Math.sin(t*.7)*1.2,Math.sin(t*.45)*3,0],Neck:[0,Math.sin(t*.45)*1.5,0]});if(sim.typing){const k=Math.sin(t*14)*3.5,k2=Math.sin(t*11+1)*3.2;p=poseAdd(p,{LeftForeArm:[k,0,0],RightForeArm:[k2,0,0],LeftHand:[k2,0,0],RightHand:[k,0,0]});}rig.apply(p);}
    /* screen */
    if(sim.draw)sim.draw();screenTex.needsUpdate=true;
    monL.color.setRGB(.42+sim.tint[0]*.3,.82+sim.tint[1]*.12,1-sim.tint[2]*.2);monL.intensity=monL.intensity;
    /* blinds flicker, dust drift */
    const pa=dust.geometry.attributes.position;for(let i=0;i<N;i++){pa.array[i*3+1]+=Math.sin(t*.4+i)*.0006;pa.array[i*3]+=.0004;if(pa.array[i*3]>2.6)pa.array[i*3]=-3;}pa.needsUpdate=true;
    lampL.visible=lampL.intensity>.01;
    renderer.render(scene,cam);
    /* glitch overlay */
    if(glitch>0.01&&gl.width>0){gl.style.opacity=1;const w=gl.width,h=gl.height;gx.globalCompositeOperation='source-over';gx.clearRect(0,0,w,h);
      const src=renderer.domElement;const off=glitch*w*.025;
      gx.globalAlpha=1;gx.drawImage(src,0,0,w,h);
      gx.globalCompositeOperation='screen';gx.globalAlpha=.5*glitch;gx.drawImage(src,-off,0,w,h);gx.globalCompositeOperation='lighter';gx.globalAlpha=.3*glitch;gx.drawImage(src,off,off*.2,w,h);gx.globalCompositeOperation='source-over';gx.globalAlpha=1;
      const n=Math.floor(glitch*14);for(let i=0;i<n;i++){const sy=Math.random()*h,sh=4+Math.random()*h*.07,dx=(Math.random()-.5)*w*.18*glitch;gx.drawImage(src,0,sy*(renderer.domElement.height/h),renderer.domElement.width,sh*(renderer.domElement.height/h),dx,sy,w,sh);}
      if(Math.random()<glitch*.5){gx.fillStyle=Math.random()<.5?'rgba(0,255,200,.12)':'rgba(255,0,60,.10)';gx.fillRect(0,Math.random()*h,w,Math.random()*h*.12);}
    }else gl.style.opacity=0;
  }
  raf=requestAnimationFrame(frame);
  function reset(){tw.clear();const k=mode==='end'?'tall':'work';poseMixA=poseMixB=POSES[k];poseK=1;const s=SHOTS[mode==='end'?'endwide':'lowwide'];cs.p.fromArray(s.p);cs.l.fromArray(s.l);cs.f=s.f;shake=0;glitch=0;drift=1;look(mode==='end'?'day':'night',1);}
  return {reset,setActive:b=>{active=b;if(b)lastT=performance.now();},setPose,shot,look,setGlitch:v=>{glitch=v;},setShake:v=>{shake=v;},setDrift:v=>{drift=v;},hasChar:!!rig,lampOn(){return tw.add(600,e=>{lampL.intensity=4*e;});},
    dispose(){dead=true;cancelAnimationFrame(raf);R.dispose();gl.remove();},tween:(ms,fn,e)=>tw.add(ms,fn,e)};
}

