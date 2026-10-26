import {useEffect,useRef,useState} from 'react';
import mqtt from 'mqtt';
import type {MqttClient} from 'mqtt';
import {parseTelemetry} from './telemetry';
import type {Telemetry} from './telemetry';
import {AngleChart} from './AngleChart';
import {History} from './History';
import {loadBrokerUrl} from './runtime-config';
import {appendPoint} from './angle-data';
import type {AnglePoint} from './angle-data';

type Entry={data:Telemetry;received:number;points:AnglePoint[]};

const topic='sts/latihan';
const modeLabels:Record<string,string>={CAL_DUDUK:'Kalibrasi duduk',CAL_BERDIRI:'Kalibrasi berdiri',KEMBALI:'Kembali duduk',LATIHAN:'Latihan STS'};
const sourceLabels:Record<string,string>={browser_camera:'Kamera browser',simulation:'Simulasi',unspecified:'Tidak disebutkan'};

export function MqttMonitor(){
  const [brokerUrl,setBrokerUrl]=useState('');
  const clientRef=useRef<MqttClient|null>(null);
  const [active,setActive]=useState(false),[connected,setConnected]=useState(false);
  const [status,setStatus]=useState('Belum terhubung'),[error,setError]=useState('');
  const [entries,setEntries]=useState<Record<string,Entry>>({}),[recent,setRecent]=useState<Entry[]>([]);
  const [selected,setSelected]=useState(''),[latestSid,setLatestSid]=useState('');
  const [total,setTotal]=useState(0),[ignored,setIgnored]=useState(0),[now,setNow]=useState(Date.now());
  useEffect(()=>{const id=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(id)},[]);
  useEffect(()=>{
    if(!active)return;
    let disposed=false;
    let connection:MqttClient|undefined;
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),5000);
    void (async()=>{
    const url=await loadBrokerUrl(location,controller.signal);
    clearTimeout(timeout);
    if(disposed)return;
    setBrokerUrl(url);
    const client=mqtt.connect(url,{protocolVersion:4,clean:true,reconnectPeriod:2000,connectTimeout:5000,resubscribe:false,timerVariant:'native'});
    connection=client;
    clientRef.current=client;
    client.on('connect',()=>{
      if(disposed)return;
      setError('');setStatus('Menyiapkan langganan…');
      client.subscribe(topic,{qos:0},(err,granted)=>{
        if(disposed)return;
        if(err || !granted?.length || granted.some(g=>g.qos===128)){
          setError('Langganan ditolak broker.');setConnected(false);return;
        }
        setConnected(true);setStatus('Terhubung · menunggu hasil STS');
      });
    });
    client.on('message',(receivedTopic,payload)=>{
      if(disposed || receivedTopic!==topic)return;
      const data=parseTelemetry(payload.toString());
      if(!data){setIgnored(n=>n+1);return}
      const entry:Entry={data,received:Date.now(),points:[]};
      setEntries(previous=>{
        const trace=previous[data.session_id]?.points??[];
        const point=data.t===null?null:{t:data.t,mode:data.mode,phase:data.phase,knee:data.knee_angle,hip:data.hip_angle,lean:data.trunk_lean};
        const next={...previous,[data.session_id]:{...entry,points:point?appendPoint(trace,point):trace}};
        const keys=Object.keys(next).sort((a,b)=>next[b].received-next[a].received);
        return Object.fromEntries(keys.slice(0,20).map(key=>[key,next[key]]));
      });
      setLatestSid(data.session_id);setRecent(items=>[entry,...items].slice(0,30));
      setTotal(n=>n+1);setNow(entry.received);setStatus('Terhubung · menerima hasil STS');
    });
    const disconnected=()=>{if(!disposed){setConnected(false);setStatus('Terputus · mencoba tersambung kembali')}};
    client.on('close',disconnected);client.on('offline',disconnected);
    client.on('error',()=>{if(!disposed){setConnected(false);setError('Broker belum dapat dihubungi. Periksa alamat broker pada detail koneksi, konfigurasi server, dan izin akses.')}});
    })().catch(()=>{if(!disposed){setError('Konfigurasi MQTT tidak dapat dimuat. Periksa koneksi API dan STS_MQTT_WS_URL.');setStatus('Gagal menyiapkan koneksi');setActive(false)}});
    return()=>{disposed=true;clearTimeout(timeout);controller.abort();clientRef.current=null;connection?.end(true)};
  },[active]);
  function disconnect(){setActive(false);setConnected(false);setStatus('Koneksi dihentikan');setError('')}
  const current=entries[selected||latestSid];
  const data=current?.data;
  const age=current?Math.max(0,(now-current.received)/1000):null;
  const freshness=!data?'Belum ada data':data.closed?'Sesi selesai':!connected?'Data terakhir · koneksi terputus':age!==null&&age>3?'Tidak ada pesan baru lebih dari 3 detik':'Data baru diterima';
  const angle=(value:number|null|undefined)=>value==null?'—':`${value.toFixed(1)}°`;
  const rows=recent.filter(item=>!selected||item.data.session_id===selected);
  return <main className="mqtt-monitor">
    <header><a className="brand" href="/camera/">gerak<span>STS</span></a><span className="tag">Pemantau MQTT · v0.8.1</span><a href="/camera/" target="_blank" rel="noopener">Halaman latihan ↗</a></header>
    <section className="intro"><p className="eyebrow">HASIL LATIHAN LANGSUNG</p><h1>Pantau gerakan.<br/><span>Dari tab lain.</span></h1><p>Jalankan kamera di laptop. Pantau hasilnya dari tab lain atau HP yang dapat mengakses server dan broker.</p></section>
    <section className="monitor-connection">
      <div><span className={'badge '+(connected?'online':'')}>{connected?'TERHUBUNG':'BELUM TERHUBUNG'}</span><p role="status">{status}</p></div>
      <div className="actions"><button className="primary" disabled={active} onClick={()=>{setError('');setActive(true)}}>Hubungkan MQTT</button><button disabled={!active} onClick={disconnect}>Putuskan</button></div>
    </section>
    {error&&<div role="alert" className="error">{error}</div>}
    <section className="monitor-session">
      <label>Sesi yang dipantau<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Ikuti pesan sesi terbaru</option>{Object.entries(entries).map(([sid,entry])=><option key={sid} value={sid}>{sid.slice(0,8)} · {sourceLabels[entry.data.input_source]}{entry.data.closed?' · selesai':''}</option>)}</select></label>
      <p className="monitor-freshness" aria-live="polite">{freshness}{age!==null?` · diterima ${age.toFixed(0)} detik lalu`:''}</p>
    </section>
    <div className="layout">
      <section className="monitor-main">
        <div className="instruction"><p className="eyebrow">KEADAAN TERAKHIR DITERIMA</p><h2>{data?modeLabels[data.mode]:'Menunggu sesi'}</h2><p>{data?.message??'Hubungkan MQTT, lalu jalankan kamera atau simulasi di tab lain.'}</p><small>Fase latihan: {data?.phase??'—'}{data&&data.mode!=='LATIHAN'?' · penghitungan latihan belum dimulai':''}</small></div>
        <section className="metrics"><div><span>Bangkit lengkap</span><strong data-testid="complete">{data?.complete??'—'}</strong></div><div><span>Siklus selesai</span><strong data-testid="cycles">{data?.cycles??'—'}</strong></div></section>
        <section className="data"><h2>Sesi yang diterima</h2><p className="session-id">{data?.session_id??'Belum ada sesi'}</p><p>Sumber: {data?sourceLabels[data.input_source]:'—'} · Waktu sesi: {data?.t==null?'—':`${data.t.toFixed(2)} detik`}</p><p>{data?data.pose_valid?'Titik tubuh memenuhi pemeriksaan kualitas.':'Pengukuran tubuh belum tersedia.':'Menunggu pengukuran tubuh.'}</p></section>
      </section>
      <aside><section className="angles"><h2>Sudut dari pesan MQTT</h2><dl><div><dt>Lutut kiri</dt><dd data-testid="knee">{angle(data?.knee_angle)}</dd></div><div><dt>Badan–paha kiri</dt><dd>{angle(data?.hip_angle)}</dd></div><div><dt>Kemiringan badan</dt><dd>{angle(data?.trunk_lean)}</dd></div></dl><p>Angka mengikuti hasil pengukuran backend pada timestamp pesan.</p></section><section className="data"><h2>Pesan diterima</h2><p><b>{total}</b> pesan STS sejak halaman dibuka.</p>{ignored>0&&<p>{ignored} pesan lain diabaikan karena formatnya berbeda.</p>}<p>Bangkit lengkap dan siklus selesai adalah hitungan gerakan. Rincian penilaian postur tersedia di halaman latihan dan riwayat.</p></section></aside>
    </div>
    <AngleChart key={selected||latestSid} points={current?.points??[]} title="Grafik sudut dari MQTT" source="Pesan MQTT yang diterima pemantau, bukan seluruh frame" gapSeconds={1.5} live/>
    <section className="monitor-log"><div className="panel-heading"><h2>Pesan terbaru</h2><span className="badge">MAKSIMAL 30 PESAN</span></div><div className="monitor-table"><table><thead><tr><th>Waktu sesi</th><th>Sesi</th><th>Tahap</th><th>Fase</th><th>Bangkit</th><th>Siklus</th></tr></thead><tbody>{rows.map((entry,i)=><tr key={`${entry.received}-${i}`}><td>{entry.data.t?.toFixed(2)??'—'}</td><td>{entry.data.session_id.slice(0,8)}</td><td>{entry.data.closed?'Selesai':modeLabels[entry.data.mode]}</td><td>{entry.data.phase}</td><td>{entry.data.complete}</td><td>{entry.data.cycles}</td></tr>)}</tbody></table>{!rows.length&&<p>Belum ada pesan untuk ditampilkan.</p>}</div></section>
    <details><summary>Pelajari koneksi halaman ini</summary><p>Backend Python mengirim hasil melalui MQTT TCP port 1883. Broker yang sama meneruskannya ke browser melalui MQTT lewat WebSocket port 9001. Kamera tetap mengirim landmark ke FastAPI melalui HTTP.</p><p>Broker browser: {brokerUrl} · Topic: {topic}. Grafik langsung menerima pesan MQTT. Riwayat sesi di bawah mengambil data tersimpan melalui API HTTP. Halaman ini tidak menyalakan kamera. Alamat broker menggunakan konfigurasi server. Tanpa konfigurasi khusus, HTTP memakai port 9001 dan HTTPS memakai jalur /mqtt pada domain yang sama.</p><p>Data langsung menggunakan QoS 0 tanpa retain. Buka pemantau sebelum mulai sesi agar menerima perubahannya. Halaman hanya menyimpan pesan sementara; setelah refresh, tunggu pesan baru. Riwayat lengkap tetap ada di halaman kamera setelah sesi disimpan.</p></details>
    <History/>
    <footer>Prototipe pembelajaran IIPP & TA. Aturan penilaian adalah asumsi teknis pribadi.</footer>
  </main>;
}
