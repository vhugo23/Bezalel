// Bounded PCM gate after browser echo cancellation/noise suppression. This is
// not speaker identification: recognized text and the server echo guard decide barge-in.
export class LocalUtterance {
  private frames:Float32Array[]=[];
  private pre:Float32Array[]=[];
  private voiced=0;
  private silence=0;
  private noise=0.002;
  private lastPreview=0;
  constructor(private emit:(pcm:Float32Array,final:boolean)=>void){}
  reset(){this.frames=[];this.pre=[];this.voiced=0;this.silence=0;this.lastPreview=0;}
  private pcm(){const out=new Float32Array(this.frames.reduce((n,f)=>n+f.length,0));let i=0;for(const f of this.frames){out.set(f,i);i+=f.length;}return out;}
  push(buffer:ArrayBuffer,rms:number){
    const data=Float32Array.from(new Int16Array(buffer),n=>n/32768);
    const speech=rms>Math.max(0.008,this.noise*3);
    if(!this.frames.length){
      if(!speech){this.noise=this.noise*.95+rms*.05;this.pre=[...this.pre.slice(-1),data];return;}
      this.frames=this.pre;this.pre=[];
    }
    this.frames.push(data);
    if(speech){this.voiced++;this.silence=0;}else this.silence++;
    if(this.voiced>=3&&this.frames.length-this.lastPreview>=12&&this.silence<8){this.lastPreview=this.frames.length;this.emit(this.pcm(),false);}
    if(this.silence>=8||this.frames.length>=120)this.commit();
  }
  commit(){if(this.voiced>=3)this.emit(this.pcm(),true);this.reset();}
}
