import {createRoot} from 'react-dom/client';
import {useEffect,useRef,useState,lazy,Suspense} from 'react';
import {StsClient} from './sts-client';
import {Tracker} from './tracker';
import {History} from './History';
import {AttemptResult} from './AttemptResult';
import {AngleChart} from './AngleChart';
import {appendPoint,pointFromState} from './angle-data';
import type {AnglePoint} from './angle-data';
import type {Landmark,State} from './types';
import './style.css';
const MqttMonitor=lazy(()=>import('./MqttMonitor').then(module=>({default:module.MqttMonitor})));
const connections=[[11,12],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[11,13],[13,15],[12,14],[14,16],[27,29],[29,31],[28,30],[30,32]];
const steps=['Buka kamera','Rekam duduk','Rekam berdiri','Latihan STS'];
function App(){
  const [anglePoints,setAnglePoints]=useState<AnglePoint[]>([]);
  const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null);
  const api=useRef(new StsClient()),tracker=useRef<Tracker|null>(null),stream=useRef<MediaStream|null>(null);
  const running=useRef(false),timer=useRef<ReturnType<typeof setTimeout>|null>(null),inFlight=useRef<Promise<void>>(Promise.resolve());
  const origin=useRef(0),lastCapture=useRef(-1),mounted=useRef(true);
  const [state,setState]=useState<State|null>(null),[starting,setStarting]=useState(false),[active,setActive]=useState(false),[working,setWorking]=useState(false);
  const [error,setError]=useState(''),[delay,setDelay]=useState(10),[device,setDevice]=useState(''),[devices,setDevices]=useState<MediaDeviceInfo[]>([]);
  const [latency,setLatency]=useState({inference:0,api:0,fps:0}),[status,setStatus]=useState('Aktifkan kamera untuk mulai.'),[download,setDownload]=useState<Record<string,unknown>|null>(null);
  function release(){
    running.current=false;if(timer.current)clearTimeout(timer.current);
    tracker.current?.close();tracker.current=null;
    stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;
    if(video.current)video.current.srcObject=null;
  }
  useEffect(()=>{mounted.current=true;navigator.mediaDevices?.enumerateDevices().then(list=>{if(mounted.current)setDevices(list.filter(d=>d.kind==='videoinput'))}).catch(()=>{});return()=>{mounted.current=false;release()}},[]);
  function draw(points:Landmark[]|null){
    const c=canvas.current,v=video.current;if(!c||!v)return;
    c.width=v.videoWidth;c.height=v.videoHeight;const ctx=c.getContext('2d');if(!ctx)return;
    ctx.clearRect(0,0,c.width,c.height);if(!points)return;
    ctx.lineWidth=3;ctx.strokeStyle='#a2ffce';
    for(const [a,b] of connections){if(points[a].visibility<.4||points[b].visibility<.4)continue;ctx.beginPath();ctx.moveTo(points[a].x*c.width,points[a].y*c.height);ctx.lineTo(points[b].x*c.width,points[b].y*c.height);ctx.stroke()}
    points.forEach((p,i)=>{if(p.visibility<.4)return;ctx.beginPath();ctx.fillStyle=[11,23,25,27].includes(i)?'#ffd76b':'#e1fff2';ctx.arc(p.x*c.width,p.y*c.height,[11,23,25,27].includes(i)?6:3,0,2*Math.PI);ctx.fill()});
  }
  async function tick(){
    if(!running.current)return;
    const started=performance.now();
    try{
      const v=video.current;if(!v||!tracker.current||v.readyState<2)throw Error('Frame kamera tidak tersedia');
      if(v.currentTime!==lastCapture.current){
        lastCapture.current=v.currentTime;
        const capture=performance.now();
        const bitmap=await createImageBitmap(v);
        if(!running.current){bitmap.close();return}
        const result=await tracker.current.frame(bitmap,capture);
        if(!running.current)return;
        draw(result.landmarks);
        const apiStart=performance.now();
        const next=await api.current.frame((capture-origin.current)/1000,result.landmarks);
        if(!mounted.current)return;
        setState(next);setAnglePoints(points=>appendPoint(points,pointFromState((capture-origin.current)/1000,next)));setLatency({inference:result.inferenceMs,api:performance.now()-apiStart,fps:next.frame_interval?1/next.frame_interval:0});
      }
    }catch(e){
      if(mounted.current){setError('Aliran data berhenti: '+(e instanceof Error?e.message:String(e)));setStatus('Akhiri & simpan sesi ini sebelum mencoba lagi.');setActive(false)}
      running.current=false;
    }
    if(running.current)timer.current=setTimeout(()=>{inFlight.current=tick()},Math.max(0,66-(performance.now()-started)));
  }
  async function start(){
    setStarting(true);setError('');setDownload(null);setAnglePoints([]);setStatus('Memeriksa backend…');
    try{
      await api.current.health();
      if(!navigator.mediaDevices?.getUserMedia)throw Error('Akses kamera tidak tersedia. Buka melalui localhost di Chrome/Edge.');
      setStatus('Meminta izin kamera…');
      stream.current=await navigator.mediaDevices.getUserMedia({video:device?{deviceId:{exact:device},width:{ideal:640},height:{ideal:480}}:{width:{ideal:640},height:{ideal:480},facingMode:'user'},audio:false});
      const v=video.current!;v.srcObject=stream.current;
      await v.play();
      if(!v.videoWidth||!v.videoHeight)throw Error('Ukuran video belum tersedia. Coba kamera lain.');
      setDevices((await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput'));
      setStatus('Memuat model MediaPipe lokal…');
      tracker.current=new Tracker();await tracker.current.init(new URL(import.meta.env.BASE_URL,location.origin).href);
      const next=await api.current.create(v.videoWidth,v.videoHeight);
      setState(next);origin.current=performance.now();lastCapture.current=-1;running.current=true;setActive(true);
      setStatus('Kamera terhubung. Rekam posisi duduk untuk kalibrasi.');
      inFlight.current=tick();
    }catch(e){release();setError(e instanceof Error?e.message:String(e));setStatus('Kamera belum terhubung. Periksa izin kamera dan terminal backend.')}
    finally{setStarting(false)}
  }
  async function calibrate(posture:'duduk'|'berdiri'){
    setWorking(true);setError('');
    try{setState(await api.current.calibrate(posture,delay))}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setWorking(false)}
  }
  async function finish(){
    setWorking(true);setError('');running.current=false;if(timer.current)clearTimeout(timer.current);
    await inFlight.current;
    try{
      const next=await api.current.finish();setState(next);
      const data=await api.current.export();setDownload(data);setStatus('Sesi tersimpan. Unduh JSON untuk memeriksa data.');
    }catch(e){setError('Belum tersimpan: '+(e instanceof Error?e.message:String(e)))}
    finally{release();setActive(false);setWorking(false)}
  }
  async function saveJson(){try{const data=download??await api.current.export();setDownload(data);const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`sts-camera-${api.current.sessionId}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){setError('Export gagal: '+(e instanceof Error?e.message:String(e)))}}
  const capture=state?.capture;
  const stage=!state?0:state.mode==='CAL_DUDUK'?1:state.mode==='CAL_BERDIRI'?2:3;
  const locked=starting||working||!!capture;
  const unfinished=!!state&&!state.closed;
  const format=(n:number|undefined)=>n===undefined?'—':`${n.toFixed(1)}°`;
  return <main>
    <header><a className="brand" href="/camera/">gerak<span>STS</span></a><span className="tag">TA · Kamera + FastAPI · v0.8.1</span><a href="/camera/?view=monitor" target="_blank" rel="noopener">Pantau MQTT ↗</a><a href="/simulation">Uji simulasi ↗</a></header>
    <section className="intro"><p className="eyebrow">BELAJAR DENGAN SISTEM YANG SAMA</p><h1>Duduk. Bangkit.<br/><span>Lihat gerakanmu.</span></h1><p>Kamera membaca titik tubuh di browser. Mesin Python TA menganalisis sudut, fase, dan repetisi.</p></section>
    <ol className="steps">{steps.map((text,i)=><li key={text} className={stage===i?'current':stage>i?'done':''}><span>{i+1}</span>{text}</li>)}</ol>
    {error&&<div role="alert" className="error">{error}</div>}
    <div className="layout"><section className="camera-panel">
      <div className="panel-heading"><h2>Kamera latihan</h2><span className={'badge '+(active?'online':'')}>{active?'TERHUBUNG':'SIAPKAN KAMERA'}</span></div>
      <div className="viewport"><video ref={video} autoPlay muted playsInline/><canvas ref={canvas}/>
        {!active&&!starting&&<div className="placeholder"><span className="camera-icon">◎</span><strong>{state?.closed?'Latihan selesai':'Mulai dari posisi kamera'}</strong><p>Tempatkan kamera di sisi kiri tubuh.<br/>Pastikan bahu sampai kaki dapat terlihat.</p></div>}
        {starting&&<div className="placeholder"><strong>{status}</strong></div>}
        {active&&capture&&<div className="countdown" role="status"><strong>{capture.recording?'Tahan posisi':Math.ceil(capture.remaining_seconds)}</strong><span>{capture.recording?'Pengambilan posisi sedang berlangsung':`Menuju posisi ${capture.posture}`}</span></div>}
      </div>
      <div className="camera-note"><span className={'dot '+(state?.quality.accepted?'good':'')}/>{active?(state?.quality.accepted?'Titik kiri memenuhi pemeriksaan kualitas':'Titik kiri belum terbaca dengan cukup jelas'):'Kamera hanya aktif selama sesi.'}<small>Titik kuning: bahu, pinggul, lutut, pergelangan kaki kiri.</small></div>
      <div className="controls"><label>Kamera<select value={device} disabled={active||starting||unfinished} onChange={e=>setDevice(e.target.value)}><option value="">Kamera bawaan / default</option>{devices.map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||`Kamera ${i+1}`}</option>)}</select></label><label>Waktu menuju kursi<select value={delay} disabled={locked} onChange={e=>setDelay(Number(e.target.value))}>{[5,10,15,20].map(n=><option key={n} value={n}>{n} detik</option>)}</select></label></div>
      <div className="actions"><button className="primary" disabled={active||starting||working||unfinished} onClick={start}>{starting?'Menyiapkan…':state?.closed?'Mulai sesi baru':'Aktifkan kamera'}</button><button disabled={!active||locked||state?.mode!=='CAL_DUDUK'} onClick={()=>calibrate('duduk')}>Rekam duduk</button><button disabled={!active||locked||state?.mode!=='CAL_BERDIRI'} onClick={()=>calibrate('berdiri')}>Rekam berdiri</button><button className="finish" disabled={!unfinished||starting||working} onClick={finish}>Akhiri & simpan</button></div>
      <p className="help">Tekan rekam dari dekat laptop, lalu menuju kursi selama hitung mundur. Tubuh belum harus terlihat saat tombol ditekan.</p>
    </section><aside>
      <section className="instruction"><p className="eyebrow">PANDUAN SAAT INI</p><h2>{state?.closed?'Sesi selesai':state?.mode==='LATIHAN'?state.phase==='DUDUK'?'Siap untuk bangkit':state.phase==='BERDIRI'?'Kembali duduk':state.phase==='PERSIAPAN'?'Condong ke depan':'Terus bangkit':state?.mode==='KEMBALI'?'Kembali duduk':state?.mode==='CAL_BERDIRI'?'Rekam posisi berdiri':'Rekam posisi duduk'}</h2><p aria-live="polite">{active?state?.message:status}</p>{active&&state?.mode==='KEMBALI'&&<small>Kembali ke posisi duduk acuan selama 1 detik. Latihan akan dimulai otomatis.</small>}</section>
      <section className="metrics"><div><span>Bangkit lengkap</span><strong>{state?.complete??0}</strong></div><div><span>Siklus selesai</span><strong>{state?.cycles??0}</strong></div></section>
      <section className="angles"><h2>Sudut dari Python</h2><dl><div><dt>Lutut kiri</dt><dd>{format(state?.measurement?.knee)}</dd></div><div><dt>Badan–paha kiri</dt><dd>{format(state?.measurement?.hip)}</dd></div><div><dt>Kemiringan badan</dt><dd>{format(state?.measurement?.lean)}</dd></div></dl><p>Geometri 2D · acuan pribadi · aturan asumsi IIPP</p></section>
      <section className="data"><h2>Hasil sesi</h2><p>{download?'Data sudah siap diunduh.':'Akhiri sesi untuk menyimpan landmark, waktu, kalibrasi, sudut, dan hasil STS.'}</p><button disabled={(!download&&!state?.closed)||working} onClick={saveJson}>Unduh JSON sesi ↓</button>{state?.attempts.length?<AttemptResult attempt={state.attempts[state.attempts.length-1]}/>:null}</section>
    </aside></div>
    <details><summary>Aliran data & informasi untuk belajar</summary><p><b>Browser:</b> kamera → MediaPipe Full → 33 landmark. <b>FastAPI:</b> landmark → geometri → kalibrasi → engine.py → respons. Rekaman gambar kamera tidak dikirim; JSON menyimpan data titik tubuh.</p><div className="diagnostics"><span>MediaPipe: {latency.inference.toFixed(0)} ms</span><span>API pulang-pergi: {latency.api.toFixed(0)} ms</span><span>Data diterima: {latency.fps.toFixed(1)} frame/detik</span></div><p>{latency.fps>0&&latency.fps<7?'Aliran lambat: tutup aplikasi berat. Jeda besar dapat membuat kalibrasi mengulang atau penilaian terputus.':'Timestamp berasal dari saat gambar diambil. Frame dikirim berurutan tanpa menumpuk antrian.'}</p><p>Mode: {state?.mode??'—'} · Fase: {state?.phase??'—'} · Sampel kalibrasi: {state?.calibration_samples??0} · Kualitas: {state?.quality.reason??'belum ada data'}</p></details>
    <AngleChart key={api.current.sessionId||'no-session'} points={anglePoints} title="Grafik sudut sesi berjalan" source="Frame HTTP dari backend Python" live/>
    <section className="personal-panel"><h2>Acuan pribadi sesi ini</h2><p>Rekam posisi duduk dan berdiri yang akan menjadi acuanmu. Setelah hitung mundur, tahan diam {state?.rules?.calibration_seconds??2} detik. Aturan di bawah adalah asumsi teknis untuk belajar IIPP.</p>
      <p>Duduk: sudut boleh berbeda ±{state?.rules?.sitting_angle_tolerance??10}°; posisi kaki ±{((state?.rules?.sitting_ankle_tolerance??.1)*100).toFixed(0)}% panjang torso dari acuan. Berdiri: sudut minimal acuan dikurangi {state?.rules?.standing_angle_tolerance??10}°, tinggi pinggul minimal {((state?.rules?.stand_progress??.9)*100).toFixed(0)}% rentang kalibrasi, stabil {state?.rules?.hold_seconds??.3} detik. Tambahan kemiringan saat bergerak: minimal {state?.rules?.lean_addition??10}° dari acuan duduk.</p>
      {state?.personal_calibration?.duduk&&<p><strong>Duduk tersimpan:</strong> badan–paha {state.personal_calibration.duduk.median.hip.toFixed(1)}° · kemiringan badan {state.personal_calibration.duduk.median.lean.toFixed(1)}° · posisi kaki {(state.personal_calibration.duduk.median.ankle*100).toFixed(1)}% panjang torso.</p>}
      {state?.personal_calibration?.berdiri&&<p><strong>Berdiri tersimpan:</strong> lutut {state.personal_calibration.berdiri.median.knee.toFixed(1)}° · badan–paha {state.personal_calibration.berdiri.median.hip.toFixed(1)}°.</p>}
    </section>
    <History/>
    <footer>Prototipe pembelajaran IIPP & TA. Hasil pengukuran belum tervalidasi untuk penggunaan klinis.</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('view')==='monitor'?<Suspense fallback={<main><p>Memuat pemantau…</p></main>}><MqttMonitor/></Suspense>:<App/>);
