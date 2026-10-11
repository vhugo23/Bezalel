// Bound generated float PCM and fade clip boundaries to avoid synthesis clicks.
export function prepareSpeechAudio(samples:Float32Array,rate:number){
  const edge=Math.min(Math.round(rate*.01),Math.floor(samples.length/2));
  for(let i=0;i<samples.length;i++){
    if(!Number.isFinite(samples[i]))throw new Error('Invalid synthesized audio');
    const gain=edge?Math.min(1,i/edge,(samples.length-1-i)/edge):1;
    samples[i]=Math.max(-1,Math.min(1,samples[i]))*gain;
  }
  return samples;
}
