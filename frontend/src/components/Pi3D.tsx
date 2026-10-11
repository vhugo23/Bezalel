import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import type * as TT from 'three';

export type PiPartId = 'supply' | 'hat' | 'camera';
export type PiViewerHandle = { beginDrag: (id: PiPartId, e: {clientX:number;clientY:number}) => void; place: (id: PiPartId) => void; remove: (id: PiPartId) => void };
export type PiSupply = 'weak' | 'good';

export const PI_TRAY: {id: PiPartId; name: string; note: string; simulated: boolean; target: string}[] = [
 {id:'supply',name:'5 V / 3 A USB-C supply',note:'Changes the lab: power and throttling.',simulated:true,target:'USB-C port'},
 {id:'hat',name:'Sixfab AI HAT',note:'Reference only. Not simulated.',simulated:false,target:'40-pin header'},
 {id:'camera',name:'Camera ribbon cable',note:'Reference only. Not simulated.',simulated:false,target:'camera (CSI) port'},
];

export function webglAvailable(){
 try{const c=document.createElement('canvas');return Boolean(c.getContext('webgl2')||c.getContext('webgl'));}catch{return false;}
}

type Props = {handle:MutableRefObject<PiViewerHandle|null>; supply:PiSupply; disabled:boolean;
 onSupply:(kind:PiSupply)=>void; onAttach:(id:PiPartId,on:boolean)=>void; onNote:(msg:string|null)=>void};

const MODEL_DIRS = {supply:'pi_power_adapter',hat:'sixfab_ai_hat',camera:'pi_camera_cable'} as const;

export function Pi3D(props:Props){
 const host=useRef<HTMLDivElement>(null);
 const view=useRef<{setSupply:(k:PiSupply)=>void;setDisabled:(d:boolean)=>void}|null>(null);
 const cb=useRef(props);cb.current=props;
 const [status,setStatus]=useState<'loading'|'ready'|'failed'>('loading');
 useEffect(()=>{
  const el=host.current;if(!el)return;
  let disposed=false,cleanup=()=>{};
  (async()=>{
   try{
    const [THREE,{OrbitControls},{OBJLoader},{MTLLoader},{RoundedBoxGeometry},{RoomEnvironment}]=await Promise.all([
     import('three'),import('three/examples/jsm/controls/OrbitControls.js'),import('three/examples/jsm/loaders/OBJLoader.js'),
     import('three/examples/jsm/loaders/MTLLoader.js'),import('three/examples/jsm/geometries/RoundedBoxGeometry.js'),
     import('three/examples/jsm/environments/RoomEnvironment.js')]);
    if(disposed)return;
    const V3=THREE.Vector3,lerp=(a:number,b:number,t:number)=>a+(b-a)*t;
    const easeOut=(t:number)=>1-Math.pow(1-t,3),ease=(t:number)=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
    const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    const cv=renderer.domElement;cv.style.cssText='position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none;cursor:grab';el.appendChild(cv);
    const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(28,1,0.1,200);
    scene.environment=new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(),0.04).texture;
    const key=new THREE.DirectionalLight(0xffffff,2.1);key.position.set(5,12,7);key.castShadow=true;key.shadow.mapSize.set(2048,2048);
    Object.assign(key.shadow.camera,{left:-14,right:14,top:14,bottom:-14,near:1,far:45});key.shadow.bias=-0.0004;
    scene.add(key,new THREE.HemisphereLight(0xffffff,0xd8dce3,0.5));
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.ShadowMaterial({opacity:0.16}));ground.rotation.x=-Math.PI/2;ground.receiveShadow=true;scene.add(ground);
    const controls=new OrbitControls(cam,cv);controls.enableDamping=true;controls.target.set(-2.4,0.2,2.6);
    controls.minDistance=10;controls.maxDistance=60;controls.maxPolarAngle=Math.PI*0.48;controls.enablePan=false;
    cam.position.set(controls.target.x+37*Math.sin(-0.5)*Math.cos(0.85),controls.target.y+37*Math.sin(0.85),controls.target.z+37*Math.cos(-0.5)*Math.cos(0.85));

    /* ---------- tweens ---------- */
    const tweens:{t0:number;ms:number;fn:(e:number)=>void;e:(t:number)=>number;res:()=>void}[]=[];
    const tween=(ms:number,fn:(e:number)=>void,e=ease)=>new Promise<void>(res=>{tweens.push({t0:performance.now(),ms,fn,e,res});});

    /* ---------- Raspberry Pi 4 board (procedural, ported from prototype.html) ---------- */
    const mk=(geo:TT.BufferGeometry,mat:TT.Material,x=0,y=0,z=0,parent:TT.Object3D|null=null,cast=true)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=cast;m.receiveShadow=true;parent?.add(m);return m;};
    const rbox=(w:number,h:number,d:number,r=0.03)=>new RoundedBoxGeometry(w,h,d,3,Math.min(r,w/2-0.001,h/2-0.001,d/2-0.001));
    const M=(color:number,rough=0.5,metal=0)=>new THREE.MeshStandardMaterial({color,roughness:rough,metalness:metal});
    const mPCB=M(0x14683a,0.55,0.04),mSilver=M(0xc7cbd1,0.32,0.95),mBlack=M(0x15171a,0.55,0.1),mGold=M(0xd9b44a,0.3,1),mBrass=M(0xb08d3c,0.35,0.9);
    const ledR=new THREE.MeshStandardMaterial({color:0x330000,emissive:0xff2a1a,emissiveIntensity:2,roughness:0.4}),ledG=new THREE.MeshStandardMaterial({color:0x003300,emissive:0x2aff55,emissiveIntensity:1.6,roughness:0.4});
    const canvasTex=(w:number,h:number,draw:(x:CanvasRenderingContext2D,w:number,h:number)=>void)=>{const c=document.createElement('canvas');c.width=w;c.height=h;draw(c.getContext('2d')!,w,h);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;return t;};
    const BY=0.55,B=new THREE.Group();B.position.y=BY;scene.add(B);
    const hoverables:TT.Object3D[]=[],ownerOf=new WeakMap<TT.Object3D,TT.Object3D>();// WeakMap: userData is JSON-copied by clone(), so it must not hold cycles
    const part=(g:TT.Object3D,label:string,desc:string)=>{g.userData.part={label,desc};g.traverse(o=>{if((o as TT.Mesh).isMesh){ownerOf.set(o,g);hoverables.push(o);}});return g;};
    {const s=new THREE.Shape(),x0=-4.25,y0=-2.8,w=8.5,h=5.6,r=0.32;
     s.moveTo(x0+r,y0);s.lineTo(x0+w-r,y0);s.quadraticCurveTo(x0+w,y0,x0+w,y0+r);s.lineTo(x0+w,y0+h-r);s.quadraticCurveTo(x0+w,y0+h,x0+w-r,y0+h);s.lineTo(x0+r,y0+h);s.quadraticCurveTo(x0,y0+h,x0,y0+h-r);s.lineTo(x0,y0+r);s.quadraticCurveTo(x0,y0,x0+r,y0);
     const holes=[[-3.9,2.45],[1.9,2.45],[-3.9,-2.45],[1.9,-2.45]];
     holes.forEach(([hx,hz])=>{const p=new THREE.Path();p.absarc(hx,-hz,0.13,0,Math.PI*2,true);s.holes.push(p);});
     const g=new THREE.ExtrudeGeometry(s,{depth:0.16,bevelEnabled:false,curveSegments:10});g.rotateX(-Math.PI/2);g.translate(0,-0.16,0);mk(g,mPCB,0,0,0,B);
     holes.forEach(([hx,hz])=>{const ring=mk(new THREE.RingGeometry(0.14,0.27,24),mGold,hx,0.004,hz,B,false);ring.rotation.x=-Math.PI/2;mk(new THREE.CylinderGeometry(0.15,0.15,0.55,16),mBrass,hx,-0.16-0.275,hz,B);});
     const sil=canvasTex(1024,320,(x,w2,h2)=>{x.clearRect(0,0,w2,h2);x.fillStyle='rgba(255,255,255,.92)';x.font='600 54px Helvetica,Arial';x.fillText('Raspberry Pi 4 Model B',22,78);x.font='500 30px Helvetica,Arial';x.fillStyle='rgba(255,255,255,.7)';x.fillText('Simplified model',22,130);x.strokeStyle='rgba(255,255,255,.55)';x.lineWidth=3;x.strokeRect(14,16,w2-28,160);});
     const sp=new THREE.Mesh(new THREE.PlaneGeometry(3.6,1.125),new THREE.MeshBasicMaterial({map:sil,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}));sp.rotation.x=-Math.PI/2;sp.position.set(-0.6,0.003,1.2);B.add(sp);}
    {const avoid=[[-1.5,0.75,-0.6,0.9],[0.75,2.2,-0.55,0.65],[1.7,2.9,-2.0,-0.8],[-3.7,-2.4,1.9,2.9],[-3.7,1.7,-2.8,-2.1],[-0.9,1.4,1.2,2.4],[3.5,4.4,-2.9,2.9],[-2.1,-0.1,2.2,3],[0.5,1.8,2.0,3]];
     const im=new THREE.InstancedMesh(new THREE.BoxGeometry(0.14,0.07,0.08),M(0xb59a6a,0.5,0.2),70),d=new THREE.Object3D();let i=0,tries=0,seed=7;const rnd=(a:number,b:number)=>{seed=(seed*16807)%2147483647;return a+(seed/2147483647)*(b-a);};
     while(i<70&&tries++<800){const x=rnd(-4,3.5),z=rnd(-2.5,2.4);if(avoid.some(a=>x>a[0]-0.2&&x<a[1]+0.2&&z>a[2]-0.2&&z<a[3]+0.2))continue;d.position.set(x,0.035,z);d.rotation.y=rnd(0,1)<0.5?0:Math.PI/2;d.updateMatrix();im.setMatrixAt(i++,d.matrix);}
     im.count=i;im.castShadow=true;B.add(im);}
    const grp=(x:number,z:number)=>{const g=new THREE.Group();g.position.set(x,0,z);B.add(g);return g;};
    const SOC=grp(-0.6,0.1);mk(rbox(1.35,0.07,1.35,0.04),mBlack,0,0.035,0,SOC);mk(rbox(1.12,0.12,1.12,0.03),mSilver,0,0.13,0,SOC);part(SOC,'Broadcom BCM2711 (SoC)','The CPU, GPU and memory controller in one chip. Throttles when hot or under-volted.');
    const RAM=grp(1.5,0.1);mk(rbox(1.25,0.11,1,0.03),mBlack,0,0.055,0,RAM);part(RAM,'LPDDR4 RAM','Working memory next to the SoC.');
    const WIFI=grp(1.2,-1.5);mk(rbox(1.15,0.22,0.9,0.02),mSilver,0,0.11,0,WIFI);part(WIFI,'Wi-Fi / Bluetooth','Shielded radio module.');
    const USBC=grp(-3.13,2.6);mk(rbox(0.92,0.32,0.7,0.05),mSilver,0,0.16,0,USBC);mk(new THREE.BoxGeometry(0.62,0.1,0.05),mBlack,0,0.17,0.36,USBC,false);part(USBC,'USB-C power input','Needs 5.1 V at 3 A. The board throttles itself if the voltage sags.');
    const PMIC=grp(-2.1,2);mk(rbox(0.55,0.07,0.55,0.02),mBlack,0,0.035,0,PMIC);part(PMIC,'Power management IC','Converts the 5 V input into the voltages the SoC needs.');
    [-1.65,-0.35].forEach((x,i)=>{const g=grp(x,2.62);mk(rbox(0.66,0.2,0.6,0.03),mSilver,0,0.1,0,g);mk(new THREE.BoxGeometry(0.4,0.06,0.04),mBlack,0,0.1,0.31,g,false);part(g,'Micro-HDMI '+i,'Video output.');});
    const CSI=grp(0.45,2.68);mk(rbox(0.8,0.2,0.3,0.02),M(0xe9e9ec,0.6),0,0.1,0,CSI);mk(new THREE.BoxGeometry(0.66,0.05,0.06),mBlack,0,0.2,0.05,CSI,false);part(CSI,'Camera (CSI) port','Takes the flat ribbon cable from a camera module.');
    const AUD=grp(1.15,2.28);mk(rbox(0.7,0.55,1,0.05),mBlack,0,0.275,0,AUD);part(AUD,'3.5 mm audio / composite','Headphone jack and composite video.');
    const GPIO=grp(-1,-2.45);mk(new THREE.BoxGeometry(5.1,0.25,0.5),mBlack,0,0.125,0,GPIO);
    {const pins=new THREE.InstancedMesh(new THREE.BoxGeometry(0.06,0.5,0.06),mGold,40),d=new THREE.Object3D();let k=0;for(let r=0;r<2;r++)for(let c=0;c<20;c++){d.position.set(-2.4+c*0.254,0.5,(r-0.5)*0.254);d.updateMatrix();pins.setMatrixAt(k++,d.matrix);}pins.castShadow=true;GPIO.add(pins);}
    part(GPIO,'40-pin GPIO header','General-purpose I/O: I²C, SPI, UART. HATs stack here.');
    const ETH=grp(3.2,-1.7);mk(rbox(2.1,1.35,1.6,0.04),mSilver,0,0.675,0,ETH);mk(new THREE.BoxGeometry(0.05,0.75,1.2),mBlack,1.06,0.6,0,ETH,false);mk(new THREE.BoxGeometry(0.05,0.14,0.14),ledG,1.07,0.15,-0.5,ETH,false);mk(new THREE.BoxGeometry(0.05,0.14,0.14),M(0xf59e0b,0.4),1.07,0.15,0.5,ETH,false);part(ETH,'Gigabit Ethernet','Wired network. nginx traffic arrives here.');
    [0.55,2].forEach((z,i)=>{const g=grp(3.3,z);mk(rbox(1.75,1.55,1.4,0.04),mSilver,0,0.775,0,g);for(let r=0;r<2;r++)mk(new THREE.BoxGeometry(0.05,0.5,1),mBlack,0.9,0.4+r*0.78,0,g,false);mk(new THREE.BoxGeometry(0.05,0.1,0.9),M(0x2563eb,0.5),0.91,0.42,0,g,false);part(g,i?'USB 2.0 ×2':'USB 3.0 ×2','Peripherals.');});
    const ledPwr=mk(new THREE.BoxGeometry(0.12,0.05,0.08),ledR,-2.45,0.03,2.15,B,false),ledAct=mk(new THREE.BoxGeometry(0.12,0.05,0.08),ledG,-2.28,0.03,2.15,B,false);
    mk(rbox(1.5,0.12,1.3,0.02),mSilver,-3.6,-0.2,0,B);
    const SD=grp(-4.4,0);SD.position.y=-0.32;mk(rbox(1.5,0.09,1.08,0.02),M(0x23262d,0.5,0.1),0,0,0,SD);for(let i=0;i<8;i++)mk(new THREE.BoxGeometry(0.07,0.01,0.1),mGold,0.62,-0.05,-0.4+i*0.115,SD,false);part(SD,'microSD card','The boot drive. Holds the OS, nginx and every log file.');

    /* ---------- weak supply: generic phone charger on a cable (procedural) ---------- */
    const charger=(()=>{const g=new THREE.Group();mk(rbox(1.5,1.5,1.5,0.12),M(0xf1f1f3,0.35),0,0.75,0,g);
     const t=canvasTex(256,128,(x,w,h)=>{x.fillStyle='#f4f4f5';x.fillRect(0,0,w,h);x.fillStyle='#52525b';x.font='600 22px Helvetica';x.fillText('INPUT 100–240V',14,34);x.fillText('OUTPUT 5V ⎓ 1A',14,66);x.fillStyle='#a1a1aa';x.font='500 16px Helvetica';x.fillText('Unbranded USB charger',14,100);});
     const p=new THREE.Mesh(new THREE.PlaneGeometry(1.2,0.6),new THREE.MeshBasicMaterial({map:t}));p.position.set(0,0.9,0.755);g.add(p);
     const plug=new THREE.Group();mk(rbox(0.62,0.26,0.9,0.05),mBlack,0,0,0,plug);mk(new THREE.BoxGeometry(0.58,0.2,0.5),mSilver,0,0,-0.55,plug);
     const cable=new THREE.Mesh(new THREE.BufferGeometry(),M(0xe5e7eb,0.5));cable.castShadow=true;
     const all=new THREE.Group();all.add(g,plug,cable);part(all,'Unbranded USB charger','Rated 5 V / 1 A: too weak for a Pi 4 under load.');
     const place=(off:{x:number;y:number;z:number})=>{const bx=-6.5+off.x,bz=6.5+off.z,port=new V3(-3.13,BY+0.17,2.95);g.position.set(bx,off.y,bz);plug.position.copy(port).add(new V3(off.x*0.2,off.y,0.45));
      const a=plug.position.clone().add(new V3(0,0,0.45)),b=new V3(bx,0.4+off.y,bz-0.95);
      const cv2=new THREE.CatmullRomCurve3([a,new V3(lerp(a.x,b.x,0.3),0.06,a.z+1.2),new V3(lerp(a.x,b.x,0.7),0.06,lerp(a.z+1.2,b.z,0.7)),b]);cable.geometry.dispose();cable.geometry=new THREE.TubeGeometry(cv2,48,0.055,8,false);};
     return {obj:all,place};})();
    scene.add(charger.obj);charger.place({x:0,y:0,z:0});

    /* ---------- real models ---------- */
    type Fitted=TT.Group;
    const loadModel=async(id:PiPartId)=>{
     const dir=MODEL_DIRS[id],base=`${import.meta.env.BASE_URL}models/pi/${dir}/`;
     const mtl=await new MTLLoader().setPath(base).loadAsync(`${dir}.mtl`);mtl.preload();
     const obj=await new OBJLoader().setMaterials(mtl).setPath(base).loadAsync(`${dir}.obj`);
     if(id==='supply'){
      // The export is one rigid piece: cable lying flat, plug on its edge. Split off the brick and the plug, drop the baked cable,
      // and run a new cable between them so the plug can sit squarely in the port. Built in a "port frame": plug shell centre at the
      // origin, plug pointing -z, up = +y, ground at y = -(port height).
      const S=0.1,GROUND=-(BY+0.17);
      const splitMesh=(names:string[])=>{const out=new THREE.Group();
       obj.traverse(o=>{const m=o as TT.Mesh;if(!m.isMesh)return;
        if(!names.includes(m.name))return;const mesh=new THREE.Mesh(m.geometry,m.material);mesh.castShadow=true;mesh.receiveShadow=true;out.add(mesh);});
       return out;};
      const centroid=(name:string,keep:(x:number)=>boolean)=>{const sum=new V3();let n=0;obj.traverse(o=>{const m=o as TT.Mesh;if(!m.isMesh||m.name!==name)return;const pos=m.geometry.attributes.position;for(let i=0;i<pos.count;i++){if(keep(pos.getX(i))){sum.add(new V3().fromBufferAttribute(pos,i));n++;}}});return n?sum.divideScalar(n):sum;};
      const shell=centroid('usbc_shell',()=>true),rear=centroid('usbc_overmold',x=>x<134),exitB=centroid('strain_relief',x=>x>33);
      const a=shell.clone().sub(rear).setZ(0).normalize(),zm=new V3(0,0,1),c=new V3().crossVectors(a,zm);// plug axis, plug wide side (model z), their cross
      const R=new THREE.Matrix4().makeBasis(new V3(0,0,-1),new V3(1,0,0),new V3(0,-1,0)).multiply(new THREE.Matrix4().makeBasis(a,zm,c).invert());
      const q=new THREE.Quaternion().setFromRotationMatrix(R);
      const g=new THREE.Group();
      const plug=splitMesh(['usbc_overmold','usbc_shell']);plug.scale.setScalar(S);plug.quaternion.copy(q);plug.position.copy(shell.clone().multiplyScalar(S).applyQuaternion(q).negate());g.add(plug);
      const brick=splitMesh(['body','strain_relief']);brick.scale.setScalar(S);
      const bp=new V3(-6.2,0,4.6),face=Math.atan2(-(0-bp.z),0-bp.x);// brick sits front-left of the port, cable exit turned toward the plug
      brick.rotation.set(-Math.PI/2,0,0);const holder=new THREE.Group();holder.add(brick);holder.rotation.y=face;holder.position.copy(bp);g.add(holder);g.updateMatrixWorld(true);
      holder.position.y+=GROUND-new THREE.Box3().setFromObject(holder).min.y;g.updateMatrixWorld(true);
      const wExit=exitB.clone().applyMatrix4(brick.matrixWorld),wRear=rear.clone().applyMatrix4(plug.matrixWorld);
      const dirB=new V3(Math.cos(face),0,-Math.sin(face)),gy=GROUND+0.14;
      const pts=[wRear.clone(),wRear.clone().add(new V3(0,0,0.9)),new V3(lerp(wRear.x,wExit.x,0.35),gy,lerp(wRear.z+0.9,wExit.z,0.4)),new V3(lerp(wRear.x,wExit.x,0.7),gy,lerp(wRear.z+0.9,wExit.z,0.75)),wExit.clone().addScaledVector(dirB,-1.0).setY(gy),wExit.clone().setY(Math.max(wExit.y,gy))];
      const cableMat=M(0x15171a,0.5);const cable=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),80,0.13,10,false),cableMat);cable.castShadow=true;cable.receiveShadow=true;g.add(cable);
      g.userData.anchor=new V3(0,0,0);return g;
     }
     obj.scale.setScalar(0.1);if(id!=='camera')obj.rotation.x=-Math.PI/2;// 1 unit = 10 mm; these exports are Z-up
     obj.traverse(o=>{const m=o as TT.Mesh;if(m.isMesh){m.castShadow=true;m.receiveShadow=true;}});
     if(id==='camera'){
      // The exported ribbon is an S-fold standing on its end with the module hanging above it, so it cannot be seated flat.
      // Keep the module from the export, hide the baked ribbon, and sweep a new strip (the export's ribbon texture) from the CSI port to the module.
      obj.traverse(o=>{const m=o as TT.Mesh;if(m.isMesh)(Array.isArray(m.material)?m.material:[m.material]).forEach(x=>{if(x.name==='ribbon'||x.name==='ribbon_contacts')x.visible=false;});});
      obj.rotation.set(0,0,Math.PI);obj.position.set(1.3,-0.64,3.45);// lens up, ribbon edge of the board facing the port; local origin is the ribbon tip inside the connector
      const tex=await new THREE.TextureLoader().setPath(base).loadAsync('pi_camera_cable_ribbon.png');tex.colorSpace=THREE.SRGBColorSpace;
      const curve=new THREE.CatmullRomCurve3([new V3(0,0,-0.35),new V3(0,0,0.3),new V3(0,-0.12,1.2),new V3(0.03,-0.38,2.2),new V3(0.05,-0.55,3),new V3(0.05,-0.56,3.5)]);
      const N=48,W=0.7,pos:number[]=[],uv:number[]=[],idx:number[]=[];
      for(let i=0;i<=N;i++){const t=i/N,q=curve.getPoint(t);pos.push(q.x-W/2,q.y,q.z,q.x+W/2,q.y,q.z);uv.push(t,0,t,1);if(i<N){const a=i*2;idx.push(a,a+1,a+2,a+1,a+3,a+2);}}
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geo.setIndex(idx);geo.computeVertexNormals();
      const strip=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({map:tex,roughness:0.5,side:THREE.DoubleSide}));strip.castShadow=true;strip.receiveShadow=true;
      const g=new THREE.Group();g.add(obj,strip);g.userData.anchor=new V3(0,0,0);return g;
     }
     const g=new THREE.Group();g.add(obj);g.updateMatrixWorld(true);
     const names:Record<PiPartId,string[]>={supply:['metal_shell'],camera:[],hat:[]};
     const sum=new V3();let n=0;
     obj.traverse(o=>{const m=o as TT.Mesh;if(!m.isMesh)return;const multi=Array.isArray(m.material),mats=multi?(m.material as TT.Material[]):[m.material as TT.Material],pos=m.geometry.attributes.position;
      const ranges=multi&&m.geometry.groups.length?m.geometry.groups:[{start:0,count:pos.count,materialIndex:0}];
      for(const r of ranges){if(!names[id].includes(mats[r.materialIndex??0]?.name))continue;for(let i=r.start;i<r.start+r.count&&i<pos.count;i++){sum.add(m.localToWorld(new V3().fromBufferAttribute(pos,i)));n++;}}});
     const box=new THREE.Box3().setFromObject(obj),center=box.getCenter(new V3()),anchor=n?sum.divideScalar(n):center.clone();
     g.userData.anchor=anchor;
     return g;};
    const models={} as Record<PiPartId,Fitted>;
    await Promise.all((['supply','hat','camera'] as PiPartId[]).map(async id=>{models[id]=await loadModel(id);}));
    if(disposed){renderer.dispose();return;}
    part(models.supply,'5 V / 3 A USB-C supply','A suitable supply holds the voltage under load, so the Pi stops reporting under-voltage.');
    part(models.hat,'Sixfab AI HAT','An add-on board that sits on the 40-pin header. Not simulated in this lab.');
    part(models.camera,'Camera ribbon cable','Joins a camera module to the camera port. Not simulated in this lab.');
    const pose=(g:Fitted,target:TT.Vector3,dy=0)=>{g.position.set(0,0,0);g.updateMatrixWorld(true);const wa=g.localToWorld((g.userData.anchor as TT.Vector3).clone());g.position.copy(target).sub(wa);g.position.y+=dy;};
    const poseHat=(g:Fitted,x:number,minY:number,z:number)=>{g.position.set(0,0,0);g.updateMatrixWorld(true);const b=new THREE.Box3().setFromObject(g),c=b.getCenter(new V3());g.position.set(x-c.x,minY-b.min.y,z-c.z);};
    const SLOT={supply:new V3(-3.13,0,2.95),camera:new V3(0.45,0,2.9),hat:new V3(-1,0,-2.45)};
    const poseFinal=(id:PiPartId,dy=0)=>{const g=models[id];
     if(id==='hat')poseHat(g,-1,BY+0.02+dy,0);else pose(g,id==='supply'?new V3(-3.13,BY+0.17,2.9):new V3(0.45,BY+0.1,2.85),dy);};

    /* ---------- state ---------- */
    let supply:PiSupply='weak',disabled=cb.current.disabled,busy=false;
    const attached={hat:false,camera:false};
    const setSupply=async(k:PiSupply)=>{
     if(k===supply||busy)return;supply=k;busy=true;
     try{
      if(k==='good'){
       await tween(600,e=>charger.place({x:-e*14,y:0,z:e*10}),ease);charger.obj.visible=false;
       scene.add(models.supply);poseFinal('supply',5);await tween(900,e=>poseFinal('supply',(1-e)*5),easeOut);
      }else{
       await tween(600,e=>poseFinal('supply',e*5),ease);scene.remove(models.supply);
       charger.obj.visible=true;await tween(900,e=>charger.place({x:-(1-e)*14,y:0,z:(1-e)*10}),easeOut);
      }
     }finally{busy=false;}
    };
    const attach=async(id:'hat'|'camera',on:boolean)=>{
     if(attached[id]===on||busy)return;busy=true;attached[id]=on;
     try{
      if(on){scene.add(models[id]);poseFinal(id,5);await tween(900,e=>poseFinal(id,(1-e)*5),easeOut);}
      else{await tween(700,e=>poseFinal(id,e*5),ease);scene.remove(models[id]);}
     }finally{busy=false;}
     cb.current.onAttach(id,on);
    };
    const place=(id:PiPartId)=>{if(disabled||busy)return;cb.current.onNote(null);if(id==='supply'){if(supply!=='good')cb.current.onSupply('good');}else void attach(id,true);};
    const remove=(id:PiPartId)=>{if(disabled||busy)return;if(id==='supply'){if(supply!=='weak')cb.current.onSupply('weak');}else void attach(id,false);};

    /* ---------- drag from tray ---------- */
    const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),plane=new THREE.Plane(new V3(0,1,0),-1.2);
    const setMouse=(e:{clientX:number;clientY:number})=>{const r=cv.getBoundingClientRect();mouse.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);return r;};
    const rayPoint=(e:{clientX:number;clientY:number})=>{setMouse(e);ray.setFromCamera(mouse,cam);const p=new V3();return ray.ray.intersectPlane(plane,p)?p:null;};
    const ids:PiPartId[]=['supply','camera','hat'];
    const rings=ids.reduce((o,id)=>{const m=new THREE.Mesh(new THREE.RingGeometry(id==='hat'?1.9:0.69,id==='hat'?2:0.75,48),new THREE.MeshBasicMaterial({color:0x18181b,transparent:true,opacity:0,depthWrite:false,side:THREE.DoubleSide}));
     m.rotation.x=-Math.PI/2;m.position.set(id==='hat'?-1:SLOT[id].x,id==='hat'?BY+0.05:0.08,id==='hat'?0:SLOT[id].z);scene.add(m);o[id]=m;return o;},{} as Record<PiPartId,TT.Mesh>);
    const ringMat=(id:PiPartId)=>rings[id].material as TT.MeshBasicMaterial;
    // The drop point is where the pointer ray meets the board itself (so "over the board" matches what you see); otherwise the plane above it.
    const dropAt=(e:{clientX:number;clientY:number})=>{setMouse(e);ray.setFromCamera(mouse,cam);const h=ray.intersectObject(B,true)[0];if(h)return {p:h.point.clone(),onBoard:true};const p=rayPoint(e);return p?{p,onBoard:false}:null;};
    // A specific port beats "anywhere on the board" (the HAT) when the pointer is close to it.
    const nearest=(d:{p:TT.Vector3;onBoard:boolean})=>{let best:PiPartId|null=null,bd=1e9;(['supply','camera'] as PiPartId[]).forEach(id=>{const dist=Math.hypot(d.p.x-SLOT[id].x,d.p.z-SLOT[id].z);if(dist<bd){bd=dist;best=id;}});
     if(best&&bd<1.8)return {id:best as PiPartId,d:bd};if(d.onBoard)return {id:'hat' as PiPartId,d:0};return {id:(best??'supply') as PiPartId,d:bd};};
    let ghost:TT.Object3D|null=null;
    const makeGhost=(id:PiPartId)=>{const g=models[id].clone(true);g.userData.anchor=models[id].userData.anchor;g.traverse(o=>{const m=o as TT.Mesh;if(m.isMesh){const fade=(x:TT.Material)=>{const c=x.clone();c.transparent=true;c.opacity=0.9;return c;};m.material=Array.isArray(m.material)?m.material.map(fade):fade(m.material);m.castShadow=false;}});scene.add(g);return g;};
    const beginDrag=(id:PiPartId,ev:{clientX:number;clientY:number})=>{
     if(disabled||busy||ghost)return;
     const sx=ev.clientX,sy=ev.clientY;let moved=false;const g=makeGhost(id);g.visible=false;ghost=g;controls.enabled=false;
     const mv=(e:PointerEvent)=>{if(Math.hypot(e.clientX-sx,e.clientY-sy)>6)moved=true;if(!moved)return;const p=rayPoint(e),dp=dropAt(e);if(!p||!dp)return;g.visible=true;
      if(id==='hat')poseHat(g,p.x,p.y,p.z);else pose(g,p);
      ids.forEach(k=>{ringMat(k).opacity=0.25;ringMat(k).color.set(0x18181b);});const n=nearest(dp);if(n.d<2.2){ringMat(n.id).opacity=0.9;ringMat(n.id).color.set(n.id===id?0x16a34a:0xdc2626);}};
     const up=(e:PointerEvent)=>{window.removeEventListener('pointermove',mv);window.removeEventListener('pointerup',up);controls.enabled=true;
      ids.forEach(k=>{ringMat(k).opacity=0;ringMat(k).color.set(0x18181b);});
      scene.remove(g);ghost=null;g.traverse(o=>{const m=o as TT.Mesh;if(m.isMesh)(Array.isArray(m.material)?m.material:[m.material]).forEach(x=>x.dispose());});
      if(!moved){place(id);return;}
      const dp=dropAt(e),n=dp?nearest(dp):{id,d:99};
      if(dp&&n.d<2.2&&n.id===id)place(id);else cb.current.onNote(dp&&n.d<2.2?'That part does not go there.':null);};
     window.addEventListener('pointermove',mv);window.addEventListener('pointerup',up);};
    cb.current.handle.current={beginDrag,place,remove};

    /* ---------- hover tooltip ---------- */
    const tip=document.createElement('div');tip.style.cssText='position:absolute;pointer-events:none;opacity:0;transition:opacity .12s;z-index:5;background:#09090b;color:#fff;border-radius:8px;padding:7px 10px;font-size:12px;line-height:1.35;max-width:220px;box-shadow:0 6px 20px rgba(0,0,0,.18)';el.appendChild(tip);
    const onMove=(e:PointerEvent)=>{if(ghost)return;const r=setMouse(e);ray.setFromCamera(mouse,cam);const h=ray.intersectObjects(hoverables.filter(o=>o.visible),false).find(x=>{let p:TT.Object3D|null=x.object;while(p&&p!==scene)p=p.parent;return p===scene;});
     const o=h?ownerOf.get(h.object)??null:null;
     if(o?.userData.part){const p=o.userData.part;tip.textContent='';const b=document.createElement('b');b.textContent=p.label;const s=document.createElement('span');s.style.color='#a1a1aa';s.textContent=p.desc;tip.append(b,document.createElement('br'),s);tip.style.left=Math.min(e.clientX-r.left+14,r.width-230)+'px';tip.style.top=(e.clientY-r.top+14)+'px';tip.style.opacity='1';cv.style.cursor='help';}
     else{tip.style.opacity='0';cv.style.cursor='grab';}};
    const onLeave=()=>{tip.style.opacity='0';};
    cv.addEventListener('pointermove',onMove);cv.addEventListener('pointerleave',onLeave);

    /* ---------- loop ---------- */
    const resize=()=>{const w=el.clientWidth,h=el.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();};
    const ro=new ResizeObserver(resize);ro.observe(el);resize();
    let raf=0;const loop=(now:number)=>{raf=requestAnimationFrame(loop);
     for(let i=tweens.length-1;i>=0;i--){const t=tweens[i],k=Math.max(0,Math.min(1,(now-t.t0)/t.ms));t.fn(t.e(k));if(k>=1){tweens.splice(i,1);t.res();}}
     (ledPwr.material as TT.MeshStandardMaterial).emissiveIntensity=supply==='good'?2.2:(Math.sin(now/90)>0.2?1.6:0.1);
     (ledAct.material as TT.MeshStandardMaterial).emissiveIntensity=Math.sin(now/130)>0.3?1.8:0.15;
     controls.update();renderer.render(scene,cam);};
    raf=requestAnimationFrame(loop);
    view.current={setSupply:k=>void setSupply(k),setDisabled:d=>{disabled=d;}};
    el.dataset.ready='true';setStatus('ready');
    cleanup=()=>{cancelAnimationFrame(raf);ro.disconnect();controls.dispose();cv.removeEventListener('pointermove',onMove);cv.removeEventListener('pointerleave',onLeave);
     scene.traverse(o=>{const m=o as TT.Mesh;if(m.isMesh){m.geometry.dispose();(Array.isArray(m.material)?m.material:[m.material]).forEach(x=>x.dispose());}});
     renderer.dispose();cv.remove();tip.remove();view.current=null;if(cb.current.handle.current?.place===place)cb.current.handle.current=null;};
    if(disposed)cleanup();else void setSupply(cb.current.supply);
   }catch(e){console.error('Pi 3D view failed',e);if(!disposed)setStatus('failed');}
  })();
  return()=>{disposed=true;cleanup();};
 },[]);
 useEffect(()=>{view.current?.setSupply(props.supply);},[props.supply,status]);
 useEffect(()=>{view.current?.setDisabled(props.disabled);},[props.disabled,status]);
 return <div className="pi-3d" ref={host} data-status={status}>
  {status==='loading'&&<span className="pi-3d-note">Loading 3D models…</span>}
  {status==='failed'&&<span className="pi-3d-note">The 3D view could not load. Use the part list.</span>}
  {status==='ready'&&<span className="pi-3d-hint">Drag to rotate · scroll to zoom · hover a part</span>}
 </div>;
}
