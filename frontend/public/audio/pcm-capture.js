// AudioWorklet: continuous 16 kHz mono PCM, independent of playback/main-thread rendering.
class PCMCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Int16Array(1600); // 100 ms per network frame
    this.index = 0; this.phase = 0; this.sum = 0; this.count = 0; this.energy = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      this.sum += value; this.count++; this.phase += 16000;
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate;
        const sample = Math.max(-1, Math.min(1, this.sum / this.count));
        this.sum = 0; this.count = 0;
        this.energy += sample * sample;
        this.frame[this.index++] = sample < 0 ? sample * 32768 : sample * 32767;
        if (this.index === this.frame.length) {
          this.port.postMessage({pcm:this.frame.buffer,level:Math.sqrt(this.energy / this.index)}, [this.frame.buffer]);
          this.frame = new Int16Array(1600); this.index = 0; this.energy = 0;
        }
      }
    }
    // Outputs stay silent; the microphone is never monitored through the speakers.
    return true;
  }
}
registerProcessor('pcm-capture', PCMCapture);
