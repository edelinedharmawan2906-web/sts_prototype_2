import {config,accessToken,clearLogin} from './sts-cloud-auth.mjs';
import {MonitorConnection,validId} from './monitor-core.mjs';

import {monitorLstmValues} from './lstm-monitor.mjs';

const $=id=>document.getElementById(id);
const sidKey='sts.monitor.selected.v1';
let nextBefore=null,listBusy=false,rows=[],listGeneration=0,lastReceived=0,lastSource='',mqttCount=0;
const notices=(text,error=false)=>{$('notice').textContent=text;$('notice').dataset.error=String(error);};
const selected=()=> $('session-id').value.trim();
function loginState() {
  const signedIn=Boolean(accessToken(sessionStorage));
  $('auth-badge').textContent=signedIn?'Login tersedia':'Belum login';
  $('refresh').disabled=!signedIn||listBusy;$('more').disabled=!signedIn||listBusy;
  $('logout').disabled=!signedIn;
  $('connect').disabled=!signedIn||!validId(selected())||connection.enabled;
  $('disconnect').disabled=!connection.enabled;
  return signedIn;
}
async function api(action,sid=null,payload={}) {
  const token=accessToken(sessionStorage);
  if(!token)throw Object.assign(new Error('Login habis. Silakan login kembali.'),{status:401});
  const body={action,payload};if(sid)body.session_id=sid;
  const response=await fetch(config.apiUrl,{method:'POST',credentials:'omit',cache:'no-store',
    referrerPolicy:'no-referrer',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},
    body:JSON.stringify(body),signal:AbortSignal.timeout(25000)});
  if(response.status===401)clearLogin(sessionStorage);
  if(!response.ok) {
    const messages={401:'Login habis. Silakan login kembali.',403:'Akses ditolak. Periksa izin monitor.',
      404:'Sesi tidak ditemukan pada akun ini.',410:'Sesi sudah kedaluwarsa.',
      400:'Permintaan belum sesuai. Pastikan Lambda v10 sudah terpasang.',
      500:'Lambda gagal memproses permintaan. Periksa CloudWatch dan izin role monitor.'};
    throw Object.assign(new Error(messages[response.status]||`API cloud HTTP ${response.status}. Coba lagi.`),{status:response.status});
  }
  const data=await response.json();if(data.status!=='ok'||!data.result)throw new Error('Respons API belum sesuai. Periksa versi Lambda.');
  return data.result;
}
const labels={DUDUK:'Duduk',CONDONG:'Condong ke depan',BANGKIT:'Bangkit',BERDIRI:'Berdiri',TURUN:'Kembali duduk',SIAP:'Siap latihan'};
function draw(state,source) {
  for(const [id,value] of Object.entries(monitorLstmValues(state?.lstm)))$(id).textContent=value;
  if(!state){
    for(const id of ['attempts','complete','cycles','knee','hip','lean','closed'])$(id).textContent='—';
    $('phase').textContent='Menunggu data';$('movement-message').textContent='Mulai latihan di halaman kamera pada laptop.';
    $('quality').textContent='Sudut ditampilkan jika posisi tubuh terbaca.';
    $('updated').textContent='Belum ada data';$('source').textContent='Data tersimpan di cloud; monitor ini hanya menerima hasil.';
    lastReceived=0;mqttCount=0;return;
  }
  $('attempts').textContent=state.attempt_count;$('complete').textContent=state.complete;$('cycles').textContent=state.cycles;
  $('phase').textContent=labels[state.phase]||state.phase||state.mode||'Menunggu fase';
  $('closed').textContent=state.closed?'Sesi selesai':'Sesi masih terbuka';
  $('movement-message').textContent=state.message||'Menunggu gerakan berikutnya.';
  const accepted=state.quality?.accepted===true;
  for(const key of ['knee','hip','lean']){
    const value=state.measurement?.[key];
    $(key).textContent=accepted&&Number.isFinite(value)?value.toFixed(1)+'°':'—';
  }
  $('quality').textContent=accepted?'Posisi tubuh terbaca.':
    state.quality?.reason==='pose_tidak_terdeteksi'?'Tubuh belum terdeteksi. Hitungan sebelumnya tetap tersimpan.':
    'Sudut belum dapat ditampilkan. Pastikan tubuh terlihat lengkap pada kamera.';
  lastReceived=Date.now();lastSource=source;if(source==='mqtt')mqttCount++;
  $('updated').textContent='Pembaruan baru diterima';
  $('source').textContent=`Versi ${state.version} · ${source==='mqtt'?'Pembaruan MQTT':'Status dari database'} · ${mqttCount} pembaruan MQTT diterima di monitor ini.`;
}
const connection=new MonitorConnection({api,connect:(url,options)=>globalThis.mqtt.connect(url,options),
  hasLogin:()=>Boolean(accessToken(sessionStorage)),onState:draw,
  onStatus:(text,state)=>{
    $('connection').textContent=text;$('connection').dataset.state=state;
    if(state==='connected')notices('Terhubung. Lakukan gerakan di laptop untuk melihat pembaruan di sini.');
    else if(state==='idle'&&text!=='Terputus')notices(text,true);
    loginState();
  }});

function choose(sid) {
  if(sid!==selected()) {
    connection.stop();draw(null,'reset');$('session-id').value=sid;
  }
  if(validId(sid))sessionStorage.setItem(sidKey,sid);
  $('selected-id').textContent=validId(sid)?'ID sesi · '+sid:'Belum memilih sesi';
  loginState();
}
function renderList() {
  const select=$('sessions');select.replaceChildren(new Option('Pilih sesi latihan…',''));
  for(const row of rows) {
    if(!validId(row.session_id))continue;
    const date=new Date(row.created_at*1000).toLocaleString('id-ID',{dateStyle:'short',timeStyle:'short'});
    select.add(new Option(`${row.closed?'Selesai':'Terbuka'} · ${date} · ${row.complete} bangkit · ${row.session_id.slice(0,8)}`,row.session_id));
  }
  if(rows.some(x=>x.session_id===selected()))select.value=selected();
  $('more').hidden=!nextBefore;
}
async function loadSessions(more=false) {
  if(listBusy)return;
  const generation=++listGeneration;
  listBusy=true;loginState();notices('Memuat daftar sesi…');
  try {
    const payload={limit:10};if(more&&nextBefore)payload.before=nextBefore;
    const result=await api('sessions',null,payload);
    if(generation!==listGeneration)return;
    rows=more?[...rows,...result.items]:result.items;nextBefore=result.next_before;
    renderList();
    if(!validId(selected())&&rows.length){choose(rows[0].session_id);$('sessions').value=rows[0].session_id;}
    notices(rows.length?'Pilih sesi, lalu klik Hubungkan monitor.':'Belum ada sesi tersimpan. Mulai latihan di kamera laptop terlebih dahulu.');
  } catch(error){if(generation===listGeneration)notices(error instanceof TypeError?'Gagal menghubungi API. Periksa internet dan CORS.':error.message,true);}
  finally{if(generation===listGeneration){listBusy=false;loginState();}}
}
$('sessions').addEventListener('change',()=>choose($('sessions').value));
$('session-id').addEventListener('input',()=>{
  if(connection.enabled){connection.stop();draw(null,'reset');}
  $('sessions').value='';$('selected-id').textContent=validId(selected())?'ID sesi · '+selected():'Belum memilih sesi';loginState();
});
$('refresh').addEventListener('click',()=>loadSessions());$('more').addEventListener('click',()=>loadSessions(true));
$('connect').addEventListener('click',()=>{
  try {
    if(!globalThis.mqtt)throw new Error('Library MQTT belum termuat. Muat ulang halaman.');
    sessionStorage.setItem(sidKey,selected());$('selected-id').textContent='ID sesi · '+selected();
    connection.start(selected());
  } catch(error){notices(error.message,true);}
});
$('disconnect').addEventListener('click',()=>{connection.stop();notices('Monitor diputus. Kamera dan penyimpanan sesi tetap berjalan.');});
$('login').addEventListener('click',()=>{
  connection.stop();if(validId(selected()))sessionStorage.setItem(sidKey,selected());
  location.assign('/camera/?monitor_login=1');
});
$('logout').addEventListener('click',()=>{
  connection.stop();clearLogin(sessionStorage);sessionStorage.removeItem(sidKey);
  listGeneration++;listBusy=false;rows=[];nextBefore=null;renderList();$('session-id').value='';draw(null,'reset');
  $('selected-id').textContent='Belum memilih sesi';notices('Login tab dihapus.');loginState();
});
addEventListener('pagehide',()=>connection.stop());
addEventListener('pageshow',event=>{if(event.persisted){connection.stop('Halaman dibuka kembali. Klik Hubungkan monitor.');loginState();}});
setInterval(()=>{
  if(lastReceived){const seconds=Math.floor((Date.now()-lastReceived)/1000);$('updated').textContent=`Data terakhir ${seconds} detik lalu`;
    if(seconds>15&&connection.enabled&&$('connection').dataset.state==='connected')
      $('updated').textContent+= ' · menunggu pembaruan';}
  if(!accessToken(sessionStorage)&&connection.enabled)connection.stop('Login habis. Silakan login kembali.');
  loginState();
},1000);
const saved=sessionStorage.getItem(sidKey);if(validId(saved))choose(saved);
if(loginState())loadSessions();
