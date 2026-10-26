import {useEffect,useMemo,useRef,useState} from 'react';
import {CloudStsClient} from './cloud-client';
import type {CloudSessionItem} from './cloud-client';
import type {Attempt} from './types';
import {AngleChart} from './AngleChart';
import {pointsFromFrames} from './angle-data';
import {AttemptResult} from './AttemptResult';
import {accessToken} from '../public/sts-cloud-auth.mjs';
type ExportData={session_id:string;complete:number;cycles:number;closed:boolean;frames:unknown[];attempts:Attempt[]};
const date=(value:number)=>new Date(value*1000).toLocaleString('id-ID');

export function CloudHistory({refreshKey}:{refreshKey:string}){
  const [items,setItems]=useState<CloudSessionItem[]>([]),[loaded,setLoaded]=useState(false);
  const [cursor,setCursor]=useState<string|null>(null),[selected,setSelected]=useState<ExportData|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const [legacy,setLegacy]=useState(()=>sessionStorage.getItem('sts.cloud.lastSession')??'');
  const alive=useRef(true),locked=useRef(false);
  const points=useMemo(()=>pointsFromFrames(selected?.frames??[]),[selected]);
  async function refresh(before?:string){
    if(locked.current)return;locked.current=true;setBusy(true);setError('');
    try{
      const client=new CloudStsClient();
      if(!before){
        const known=sessionStorage.getItem('sts.cloud.lastSession');
        if(known){try{await client.registerCloudSession(known)}catch(e){if(![404,410].includes((e as {status?:number}).status??0))throw e}}
      }
      const page=await client.cloudSessions(before);
      if(!alive.current)return;
      setItems(old=>before?[...old,...page.items.filter(x=>!old.some(y=>y.session_id===x.session_id))]:page.items);
      setCursor(page.next_before);setLoaded(true);
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e))}
    finally{locked.current=false;if(alive.current)setBusy(false)}
  }
  useEffect(()=>{alive.current=true;if(accessToken(sessionStorage))void refresh();return()=>{alive.current=false}},[refreshKey]);
  async function open(id:string){
    if(locked.current)return;locked.current=true;setBusy(true);setError('');
    try{
      const reader=new CloudStsClient();reader.sessionId=id;
      const data=await reader.export();
      if(alive.current)setSelected(data as ExportData);
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e))}
    finally{locked.current=false;if(alive.current)setBusy(false)}
  }
  async function addLegacy(){
    if(!/^[A-Za-z0-9_-]{1,64}$/.test(legacy.trim())){setError('Masukkan ID sesi yang benar.');return}
    if(locked.current)return;locked.current=true;setBusy(true);setError('');
    try{await new CloudStsClient().registerCloudSession(legacy.trim());locked.current=false;await refresh()}
    catch(e){setError(e instanceof Error?e.message:String(e))}
    finally{locked.current=false;setBusy(false)}
  }
  function download(){
    if(!selected)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(selected,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`sts-cloud-history-${selected.session_id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <section className="history-panel">
    <div className="panel-heading"><h2>Riwayat latihan cloud</h2><button disabled={busy} onClick={()=>refresh()}>{busy?'Memuat…':'Perbarui riwayat cloud'}</button></div>
    <p>Sumber: DynamoDB · sesi akun yang sedang login. Sesi baru muncul otomatis; retensi saat ini 7 hari.</p>
    {error&&<p role="alert" className="error">{error}</p>}
    {!loaded&&!busy&&<p>Login AWS, lalu klik Perbarui riwayat cloud.</p>}
    {loaded&&!items.length&&<p>Belum ada sesi dalam daftar. Untuk sesi dari versi lama, masukkan ID-nya di bawah.</p>}
    <div className="history-list">{items.map(item=><button key={item.session_id} disabled={busy} className={'history-row '+(selected?.session_id===item.session_id?'selected':'')} onClick={()=>open(item.session_id)}>
      <span><strong>{date(item.created_at)}{item.created_at_estimated?' (perkiraan)':''}</strong><small>ID {item.session_id.slice(0,8)} · {item.closed?'Selesai':'Belum diakhiri'}</small></span>
      <span>{item.attempt_count} percobaan · {item.complete} bangkit · {item.cycles} siklus<small>Lihat grafik dan detail →</small></span>
    </button>)}</div>
    {cursor&&<button disabled={busy} onClick={()=>refresh(cursor)}>Muat sesi berikutnya</button>}
    <details><summary>Tambahkan sesi dari versi lama</summary><p>Sesi cloud terakhir pada tab ini dimasukkan otomatis. Sesi lama lainnya dapat ditambahkan memakai session_id dari JSON milik akunmu.</p><label>ID sesi<input value={legacy} disabled={busy} onChange={e=>setLegacy(e.target.value)} placeholder="session_id dari JSON"/></label><button disabled={busy} onClick={addLegacy}>Tambahkan ke riwayat cloud</button></details>
    {selected&&<article className="history-detail"><h3>Detail sesi cloud</h3><p>{selected.attempts.length} percobaan · {selected.complete} bangkit lengkap · {selected.cycles} siklus selesai · {selected.frames.length} frame</p><p className="session-id">ID: {selected.session_id}</p>{!selected.closed&&<p>Sesi ini belum diakhiri. Detail adalah cuplikan data yang sudah tersimpan ketika dibuka.</p>}
      <AngleChart key={selected.session_id} points={points} title="Grafik sudut riwayat cloud" source="Seluruh frame tersimpan dari DynamoDB"/>
      {selected.attempts.length?<ol>{selected.attempts.map((attempt,i)=><li key={i}><AttemptResult attempt={attempt} title={`Percobaan ${i+1}`}/></li>)}</ol>:<p>Belum ada percobaan bangkit tercatat.</p>}
      <button onClick={download}>Unduh JSON sesi ini ↓</button>
    </article>}
  </section>;
}
