import {useId,useMemo,useState} from 'react';
import {phaseLabel,plotSegments} from './angle-data';
import type {AngleKey,AnglePoint} from './angle-data';

const series:{key:AngleKey;label:string;color:string}[]=[
  {key:'knee',label:'Lutut kiri',color:'#12695f'},
  {key:'hip',label:'Badan–paha kiri',color:'#b25b22'},
  {key:'lean',label:'Kemiringan badan',color:'#6255aa'}
];
const phaseColor=(p:AnglePoint)=>(p.knee===null&&p.hip===null&&p.lean===null)||p.mode!=='LATIHAN'?'#e4e8e4':({DUDUK:'#d4e8df',PERSIAPAN:'#f5dfb5',BANGKIT:'#cfdff2',BERDIRI:'#e4d7ef'} as Record<string,string>)[p.phase]??'#e4e8e4';
const W=900,L=58,R=22,T=28,H=220,BAND=275;

export function AngleChart({points,title='Grafik sudut',source='Frame API',gapSeconds=.3,live=false}:{points:AnglePoint[];title?:string;source?:string;gapSeconds?:number;live?:boolean}){
  const id=useId();
  const [all,setAll]=useState(false),[visible,setVisible]=useState<Record<AngleKey,boolean>>({knee:true,hip:true,lean:true});
  const [cursor,setCursor]=useState<number|null>(null);
  const filtered=useMemo(()=>all?points:points.filter(p=>p.mode==='LATIHAN'),[points,all]);
  const start=filtered[0]?.t??0,last=filtered[filtered.length-1]?.t??1,end=Math.max(start+1,last);
  const x=(t:number)=>L+(t-start)/(end-start)*(W-L-R);
  const y=(a:number)=>T+H-(Math.max(0,Math.min(180,a))/180)*H;
  const paths=useMemo(()=>Object.fromEntries(series.map(s=>[s.key,plotSegments(filtered,s.key,gapSeconds)])) as Record<AngleKey,AnglePoint[][]>,[filtered,gapSeconds]);
  const bands=useMemo(()=>{
    const out:{start:number;end:number;point:AnglePoint}[]=[];
    for(let i=0;i<filtered.length;i++){
      const p=filtered[i],next=filtered[i+1];
      const right=next?Math.min(next.t,p.t+gapSeconds):p.t;
      const previous=out[out.length-1];
      if(previous&&previous.end===p.t&&phaseLabel(previous.point)===phaseLabel(p))previous.end=right;
      else out.push({start:p.t,end:right,point:p});
    }
    return out;
  },[filtered,gapSeconds]);
  const nearest=(t:number)=>{
    let lo=0,hi=filtered.length-1;
    while(lo<hi){const mid=Math.floor((lo+hi)/2);if(filtered[mid].t<t)lo=mid+1;else hi=mid}
    return lo>0&&Math.abs(filtered[lo-1].t-t)<Math.abs(filtered[lo].t-t)?filtered[lo-1]:filtered[lo];
  };
  const chosen=filtered.length?nearest(cursor??last):undefined;
  const f=(n:number|null|undefined)=>n==null?'Tidak tersedia':`${n.toFixed(1)}°`;
  return <section className="angle-chart" aria-label={title}>
    <div className="panel-heading"><h2>{title}</h2><span className="badge">{live?'120 DETIK TERAKHIR':'SESI TERSIMPAN'}</span></div>
    <div className="chart-toolbar"><label className="chart-check"><input type="checkbox" checked={all} onChange={e=>{setAll(e.target.checked);setCursor(null)}}/>Sertakan kalibrasi</label><div className="chart-series">{series.map(s=><label className="chart-check" key={s.key}><input type="checkbox" checked={visible[s.key]} onChange={e=>setVisible(v=>({...v,[s.key]:e.target.checked}))}/><span style={{color:s.color}}>{s.label}</span></label>)}</div></div>
    {filtered.length===0?<p className="chart-empty">{points.length?'Belum ada data tahap LATIHAN. Centang Sertakan kalibrasi untuk melihat data awal.':'Menunggu pengukuran untuk menggambar grafik.'}</p>:<>
      <div className="chart-plot"><svg className="chart-svg" viewBox={`0 0 ${W} 325`} role="img" aria-labelledby={`${id}-title ${id}-desc`} onPointerMove={e=>{const r=e.currentTarget.getBoundingClientRect();const value=(e.clientX-r.left)/r.width*W;setCursor(start+Math.max(0,Math.min(1,(value-L)/(W-L-R)))*(end-start))}}>
        <title id={`${id}-title`}>{title}</title><desc id={`${id}-desc`}>Sudut dalam derajat terhadap waktu sesi dalam detik. Pita di bawah grafik menunjukkan fase. Garis terputus saat pengukuran hilang atau jeda data terlalu besar.</desc>
        {[0,45,90,135,180].map(a=><g key={a}><line x1={L} x2={W-R} y1={y(a)} y2={y(a)} stroke="#dce4da"/><text x={L-10} y={y(a)+4} textAnchor="end">{a}°</text></g>)}
        {Array.from({length:6},(_,i)=>start+(end-start)*i/5).map((t,i)=><text key={i} x={x(t)} y={BAND+38} textAnchor="middle">{t.toFixed(1)}</text>)}
        <text x={L} y={16}>Sudut (°)</text><text x={W-R} y={323} textAnchor="end">Waktu sesi (detik)</text>
        {series.filter(s=>visible[s.key]).map(s=><g key={s.key} data-series={s.key}>{paths[s.key].map((segment,i)=>segment.length===1?<circle key={i} cx={x(segment[0].t)} cy={y(segment[0][s.key]!)} r="2" fill={s.color}/>:<path key={i} d={segment.map((p,j)=>`${j?'L':'M'}${x(p.t).toFixed(2)},${y(p[s.key]!).toFixed(2)}`).join(' ')} fill="none" stroke={s.color} strokeWidth="2" vectorEffect="non-scaling-stroke"/>)}</g>)}
        {bands.map((b,i)=><rect key={i} x={x(b.start)} y={BAND} width={Math.max(1,x(b.end)-x(b.start))} height={15} fill={phaseColor(b.point)}><title>{`${phaseLabel(b.point)} · ${b.start.toFixed(2)}–${b.end.toFixed(2)} detik`}</title></rect>)}
        {chosen&&<line x1={x(chosen.t)} x2={x(chosen.t)} y1={T} y2={BAND+15} stroke="#57695f" strokeDasharray="4 4"/>}
      </svg></div>
      <div className="chart-phase-legend"><span style={{background:'#d4e8df'}}>Duduk</span><span style={{background:'#f5dfb5'}}>Persiapan</span><span style={{background:'#cfdff2'}}>Bangkit</span><span style={{background:'#e4d7ef'}}>Berdiri</span>{(all||filtered.some(p=>p.knee===null&&p.hip===null&&p.lean===null))&&<span style={{background:'#e4e8e4'}}>Kalibrasi / data kosong</span>}</div>
      <label className="chart-cursor">Periksa waktu<input aria-label="Periksa waktu grafik" type="range" min={start} max={last>start?last:start+1} step="0.01" value={chosen?.t??start} onChange={e=>setCursor(Number(e.target.value))}/></label>
      <div className="chart-readout" data-testid="chart-readout">{chosen&&<><strong>{chosen.t.toFixed(2)} detik · {phaseLabel(chosen)}</strong>{series.map(s=><span key={s.key}>{s.label}: {f(chosen[s.key])}</span>)}</>}</div>
      {live&&cursor!==null&&<button onClick={()=>setCursor(null)}>Ikuti data terbaru</button>}
    </>}
    <p className="chart-note">Sumber: {source}. {live?'Tampilan menyimpan maksimal 120 detik di tab ini. ':''}Garis tidak disambung melewati data hilang atau jeda lebih dari {gapSeconds.toLocaleString('id-ID')} detik. Pita fase mengikuti data yang teramati. Di HP, geser grafik ke samping untuk melihat seluruh sumbu. Grafik tidak mengubah penilaian gerakan.</p>
  </section>;
}
