import { describe,it,expect,vi } from 'vitest';
import { LocalUtterance } from './localUtterance';
const frame=()=>new Int16Array(1600).fill(1000).buffer;
describe('bounded local speech segmentation',()=>{
 it('rejects quiet background and short clicks',()=>{
  const emit=vi.fn(),gate=new LocalUtterance(emit);for(let n=0;n<40;n++)gate.push(frame(),.001);
  gate.push(frame(),.1);for(let n=0;n<10;n++)gate.push(frame(),.001);expect(emit).not.toHaveBeenCalled();
 });
 it('previews while speaking and finalizes after an 800ms pause',()=>{
  const emit=vi.fn(),gate=new LocalUtterance(emit);for(let n=0;n<13;n++)gate.push(frame(),.05);
  expect(emit).toHaveBeenCalledWith(expect.any(Float32Array),false);
  for(let n=0;n<8;n++)gate.push(frame(),.001);expect(emit).toHaveBeenLastCalledWith(expect.any(Float32Array),true);
 });
 it('bounds uninterrupted speech to 12 seconds and resets mute buffers',()=>{
  const emit=vi.fn(),gate=new LocalUtterance(emit);for(let n=0;n<120;n++)gate.push(frame(),.05);
  expect(emit).toHaveBeenLastCalledWith(expect.any(Float32Array),true);expect(emit.mock.lastCall![0].length).toBe(192000);
  emit.mockClear();gate.push(frame(),.05);gate.reset();gate.commit();expect(emit).not.toHaveBeenCalled();
 });
});
