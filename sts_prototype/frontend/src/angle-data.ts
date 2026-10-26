export type AnglePoint={t:number;mode:string;phase:string;knee:number|null;hip:number|null;lean:number|null};
export type AngleKey='knee'|'hip'|'lean';
const finite=(value:unknown):number|null=>typeof value==='number'&&Number.isFinite(value)?value:null;

export function pointFromState(t:number,state:{mode:string;phase:string;quality:{accepted:boolean};measurement:null|{knee:number;hip:number;lean:number}}):AnglePoint{
  const m=state.quality.accepted?state.measurement:null;
  return {t,mode:state.mode,phase:state.phase,knee:finite(m?.knee),hip:finite(m?.hip),lean:finite(m?.lean)};
}

export function pointsFromFrames(frames:unknown[]):AnglePoint[]{
  const points:AnglePoint[]=[];
  for(const raw of frames){
    if(!raw||typeof raw!=='object')continue;
    const f=raw as Record<string,unknown>;
    const t=finite(f.t);
    if(t===null||t<0||(points.length>0&&t<=points[points.length-1].t))continue;
    const quality=f.quality as {accepted?:boolean}|undefined;
    const m=(quality?.accepted===false?null:f.measurement) as Record<string,unknown>|null;
    points.push({t,mode:typeof f.mode==='string'?f.mode:'TIDAK_DIKETAHUI',phase:typeof f.phase==='string'?f.phase:'TIDAK_DIKETAHUI',knee:finite(m?.knee),hip:finite(m?.hip),lean:finite(m?.lean)});
  }
  return points;
}

export function appendPoint(points:AnglePoint[],point:AnglePoint,maxPoints=2400,seconds=120):AnglePoint[]{
  if(points.length&&point.t<=points[points.length-1].t)return points;
  return [...points,point].filter(p=>p.t>=point.t-seconds).slice(-maxPoints);
}

// Split at missing measurements and time gaps before reducing drawing points.
// Keep first/last/min/max per horizontal bucket, preserving visible extrema.
export function plotSegments(points:AnglePoint[],key:AngleKey,gapSeconds:number,buckets=600):AnglePoint[][]{
  const segments:AnglePoint[][]=[];
  let current:AnglePoint[]=[];
  let previous:AnglePoint|undefined;
  for(const point of points){
    if(point[key]===null||previous&&point.t-previous.t>gapSeconds){
      if(current.length)segments.push(current);
      current=[];
    }
    if(point[key]!==null)current.push(point);
    previous=point;
  }
  if(current.length)segments.push(current);
  if(!points.length)return segments;
  const start=points[0].t,span=Math.max(.001,points[points.length-1].t-start);
  return segments.map(segment=>{
    const out:AnglePoint[]=[];
    let group:AnglePoint[]=[],bucket=-1;
    const flush=()=>{
      if(!group.length)return;
      let min=group[0],max=group[0];
      for(const p of group){if(p[key]!<min[key]!)min=p;if(p[key]!>max[key]!)max=p}
      const keep=[...new Set([group[0],min,max,group[group.length-1]])].sort((a,b)=>a.t-b.t);
      out.push(...keep);group=[];
    };
    for(const p of segment){
      const next=Math.floor((p.t-start)/span*buckets);
      if(next!==bucket){flush();bucket=next}
      group.push(p);
    }
    flush();return out;
  });
}

export function phaseLabel(point:AnglePoint):string{
  if(point.knee===null&&point.hip===null&&point.lean===null)return 'Pengukuran tidak tersedia';
  if(point.mode!=='LATIHAN')return ({CAL_DUDUK:'Kalibrasi duduk',CAL_BERDIRI:'Kalibrasi berdiri',KEMBALI:'Kembali duduk'} as Record<string,string>)[point.mode]??'Tahap tidak diketahui';
  return ({DUDUK:'Duduk',PERSIAPAN:'Persiapan',BANGKIT:'Bangkit',BERDIRI:'Berdiri'} as Record<string,string>)[point.phase]??'Fase tidak diketahui';
}
