import type { CSSProperties } from 'react';
import './DanaOrb.css';

type OrbState='off'|'connecting'|'loading'|'listening'|'transcribing'|'thinking'|'speaking'|'muted';
export function DanaOrb({phase,level=0,paused=false}:{phase:OrbState;level?:number;paused?:boolean}) {
  const state=paused?'muted':phase;
  const pondering=['thinking','transcribing','connecting','loading'].includes(state);
  return <div className="voice-orb dana-orb" data-state={state} aria-hidden="true" style={{'--level':Number.isFinite(level)?Math.max(0,Math.min(1,level)):0} as CSSProperties}>
    <span/><span/><span/>
    <svg className="dana-face" viewBox="0 0 64 64" fill="none">
      <g className="dana-eyes">
        {state==='muted'?<path d="M20 28q3 3 6 0m12 0q3 3 6 0"/>:<><ellipse cx="23" cy={pondering?26:28} rx="2.4" ry={state==='listening'?3.6:3}/><ellipse cx="41" cy={pondering?26:28} rx="2.4" ry={state==='listening'?3.6:3}/></>}
      </g>
      {state==='speaking'?<ellipse className="dana-talking-mouth" cx="32" cy="39" rx="5" ry="4"/>:pondering?<path className="dana-ponder-mouth" d="M29 39h6"/>:<path d={state==='muted'?'M28 39q4 3 8 0':'M26 37q6 7 12 0'}/>}
    </svg>
  </div>;
}
