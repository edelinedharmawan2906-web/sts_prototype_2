import {useMemo,useState} from 'react';
import {AngleChart} from './AngleChart';
import {pointsFromFrames} from './angle-data';
import {StsClient} from './sts-client';
import {AttemptResult} from './AttemptResult';
import type {HistoryPage,HistoryRecord} from './types';
const client=new StsClient();
const date=(value:string)=>new Date(value).toLocaleString('id-ID');
export function History(){
  const [page,setPage]=useState<HistoryPage|null>(null),[selected,setSelected]=useState<HistoryRecord|null>(null);
  const chartPoints=useMemo(()=>pointsFromFrames(selected?.data.frames??[]),[selected]);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function refresh(offset=0){setBusy(true);setError('');try{setPage(await client.history(offset));setSelected(null)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  async function open(id:string){setBusy(true);setError('');try{setSelected(await client.detail(id))}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  function download(){if(!selected)return;const url=URL.createObjectURL(new Blob([JSON.stringify(selected.data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`sts-history-${selected.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  return <section className="history-panel">
    <div className="panel-heading"><h2>Riwayat latihan</h2><button disabled={busy} onClick={()=>refresh()}>{busy?'Memuat…':page?'Perbarui riwayat':'Buka riwayat latihan'}</button></div>
    <p>Sesi muncul setelah menekan Akhiri &amp; simpan. Waktu mengikuti perangkatmu.</p>
    {error&&<p role="alert" className="error">{error}</p>}
    {page&&<><p>{page.total} sesi tersimpan.</p>{page.items.length===0?<p>Belum ada sesi tersimpan.</p>:<div className="history-list">{page.items.map(item=><button className={'history-row '+(selected?.id===item.id?'selected':'')} key={item.id} disabled={busy} onClick={()=>open(item.id)}><span><strong>{date(item.saved_at)}</strong><small>{item.input_source==='browser_camera'?'Kamera':item.input_source==='simulation'?'Simulasi':item.input_source} · ID {item.id.slice(0,8)}</small></span><span>{item.complete} bangkit · {item.cycles} siklus <small>Lihat detail →</small></span></button>)}</div>}
      <div className="actions"><button disabled={busy||page.offset===0} onClick={()=>refresh(Math.max(0,page.offset-page.limit))}>Sebelumnya</button><button disabled={busy||page.offset+page.limit>=page.total} onClick={()=>refresh(page.offset+page.limit)}>Berikutnya</button></div></>}
    {selected&&<article className="history-detail"><h3>Detail sesi — {date(selected.saved_at)}</h3><p>{selected.data.complete} bangkit lengkap · {selected.data.cycles} siklus · {selected.data.frames.length} frame tersimpan</p><p>ID: <code>{selected.id}</code></p>
      <AngleChart key={selected.id} points={chartPoints} title="Grafik sudut sesi tersimpan" source="Seluruh frame JSON sesi tersimpan"/>
      {selected.data.attempts.length===0?<p>Tidak ada percobaan STS yang tercatat.</p>:<ol>{selected.data.attempts.map((a,i)=><li key={i}><AttemptResult attempt={a} title={`Percobaan ${i+1}`}/></li>)}</ol>}
      <button onClick={download}>Unduh JSON sesi ini ↓</button>
    </article>}
  </section>;
}
