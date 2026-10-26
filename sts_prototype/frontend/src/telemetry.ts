export type Telemetry = {
  schema_version: 1;
  session_id: string;
  input_source: 'browser_camera'|'simulation'|'unspecified';
  t: number|null;
  mode: string;
  phase: string;
  knee_angle: number|null;
  hip_angle: number|null;
  trunk_lean: number|null;
  complete: number;
  cycles: number;
  pose_valid: boolean;
  closed: boolean;
  message: string;
};

export function parseTelemetry(text:string):Telemetry|null {
  try {
    const d=JSON.parse(text);
    if(!d || typeof d!=='object' || Array.isArray(d) || d.schema_version!==1) return null;
    if(typeof d.session_id!=='string' || !/^[a-f0-9]{32}$/.test(d.session_id)) return null;
    if(!['browser_camera','simulation','unspecified'].includes(d.input_source)) return null;
    if(!['CAL_DUDUK','CAL_BERDIRI','KEMBALI','LATIHAN'].includes(d.mode)) return null;
    if(!['DUDUK','PERSIAPAN','BANGKIT','BERDIRI'].includes(d.phase)) return null;
    if(typeof d.message!=='string' || typeof d.pose_valid!=='boolean' || typeof d.closed!=='boolean') return null;
    if(![d.complete,d.cycles].every(n=>Number.isSafeInteger(n) && n>=0)) return null;
    if(d.t!==null && !(typeof d.t==='number' && Number.isFinite(d.t) && d.t>=0)) return null;
    if(![d.knee_angle,d.hip_angle,d.trunk_lean].every(n=>n===null || (typeof n==='number' && Number.isFinite(n)))) return null;
    return d as Telemetry;
  } catch { return null; }
}
