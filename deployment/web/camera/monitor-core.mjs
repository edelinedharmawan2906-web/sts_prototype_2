// Pure state validation and a testable MQTT lifecycle; no persistent credentials.
export const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(value);
export function snapshotFromStatus(state) {
  return {...state,schema:'sts-live-v1',attempt_count:(state.attempts?.length||0)+(state.phase==='BANGKIT'?1:0)};
}
export function acceptSnapshot(current,incoming,sid) {
  if (!incoming || incoming.schema!=='sts-live-v1' || incoming.session_id!==sid
      || !Number.isSafeInteger(incoming.version) || incoming.version<0
      || !['complete','cycles','attempt_count'].every(k=>Number.isSafeInteger(incoming[k]) && incoming[k]>=0)
      || typeof incoming.closed!=='boolean'
      || (current && incoming.version<=current.version)) return current;
  return incoming;
}
export function checkGrant(grant,sid,now=Date.now()) {
  if (!grant || !validId(sid) || !/^sts-monitor-[a-f0-9]{32}$/.test(grant.client_id||'')) throw new Error('INVALID_GRANT');
  const url=new URL(grant.url);
  const topic=new RegExp('^sts/cloud/cognito-[a-f0-9]{64}/'+sid+'/state$');
  const expires=Date.parse(grant.credentials_expire_at);
  if (url.protocol!=='wss:' || url.hostname!=='as4p4a02r32pn-ats.iot.ap-southeast-2.amazonaws.com'
      || url.pathname!=='/mqtt' || url.port || url.username || url.password
      || !topic.test(grant.topic||'') || grant.read_only!==true || grant.qos!==1
      || !Number.isFinite(expires) || expires<now+60000) throw new Error('INVALID_GRANT');
  return Math.min(13*60*1000,expires-now-60000);
}

export class MonitorConnection {
  constructor({api,connect,hasLogin,onState,onStatus,timers=globalThis,now=Date.now}) {
    Object.assign(this,{api,connect,hasLogin,onState,onStatus,timers,now});
    this.generation=0;this.serial=0;this.enabled=false;this.jobs=new Set();
  }
  later(fn,ms) {
    const job=this.timers.setTimeout(()=>{this.jobs.delete(job);fn();},ms);
    this.jobs.add(job);return job;
  }
  cleanup() {
    for (const job of this.jobs) this.timers.clearTimeout(job);
    this.jobs.clear();
    const client=this.client;this.client=null;
    if(client){client.removeAllListeners();client.on('error',()=>{});client.end(true);}
  }
  stop(label='Terputus') {
    this.enabled=false;this.generation++;this.serial++;this.cleanup();
    this.onStatus(label,'idle');
  }
  start(sid) {
    if(!validId(sid))throw new Error('ID sesi tidak valid.');
    this.stop();this.enabled=true;this.sid=sid;this.failures=0;
    this.current=null;this.onState(null,'reset');this.open(this.generation);
  }
  receive(value,source) {
    const next=acceptSnapshot(this.current,value,this.sid);
    if(next!==this.current){this.current=next;this.onState(next,source);}
  }
  async open(generation) {
    if(!this.enabled || generation!==this.generation)return;
    this.cleanup();const serial=++this.serial;
    const active=()=>this.enabled && generation===this.generation && serial===this.serial;
    if(!this.hasLogin()){this.stop('Login habis. Silakan login kembali.');return;}
    this.onStatus('Meminta akses sementara…','loading');
    let grant;
    try {grant=await this.api('monitor_connect',this.sid);}
    catch(error){if(active())this.failed(error,generation);return;}
    if(!active())return;
    let renewAfter;
    try {renewAfter=checkGrant(grant,this.sid,this.now());}
    catch {this.stop('Respons akses belum sesuai. Periksa versi Lambda.');return;}
    this.receive(grant.initial_state,'status');
    this.onStatus('Menyambungkan MQTT…','loading');
    let client;
    try {
      client=this.connect(grant.url,{clientId:grant.client_id,protocolVersion:4,clean:true,
        reconnectPeriod:0,resubscribe:false,connectTimeout:15000,keepalive:30,
        queueQoSZero:false});
      this.client=client;
    } catch {this.failed(null,generation);return;}
    // Grant URL stays in memory only. All retries request a fresh URL/client ID.
    const timeout=this.later(()=>{if(active())this.failed(null,generation);},20000);
    client.on('message',(topic,bytes)=>{
      if(!active() || topic!==grant.topic || bytes.length>16*1024)return;
      try {this.receive(JSON.parse(bytes.toString()),'mqtt');} catch { /* Ignore malformed packets. */ }
    });
    client.on('connect',()=>{
      if(!active())return;
      client.subscribe(grant.topic,{qos:1},async(error,granted)=>{
        if(!active())return;
        if(error || !granted?.length || granted.some(x=>x.qos>1)) {this.failed(null,generation);return;}
        this.timers.clearTimeout(timeout);this.jobs.delete(timeout);
        this.failures=0;this.onStatus('Terhubung · MQTT cloud','connected');
        // Fetch AFTER SUBACK to close the initial-read/subscribe race. Version
        // gating prevents this response from replacing newer MQTT data.
        try {
          const state=await this.api('status',this.sid);
          if(active())this.receive(snapshotFromStatus(state),'status');
        } catch(error) {
          if(active() && [401,403,404,410].includes(error?.status))this.failed(error,generation);
          else if(active())this.onStatus('MQTT terhubung · sinkronisasi status gagal','connected');
        }
      });
    });
    client.on('error',()=>{if(active())this.failed(null,generation);});
    client.on('close',()=>{if(active())this.failed(null,generation);});
    this.later(()=>{if(active())this.open(generation);},renewAfter);
    const checkLogin=()=>{
      if(!active())return;
      if(!this.hasLogin()){this.stop('Login habis. Silakan login kembali.');return;}
      this.later(checkLogin,15000);
    };
    this.later(checkLogin,15000);
  }
  failed(error,generation) {
    this.serial++;this.cleanup();
    if([401,403,404,410].includes(error?.status)) {
      const messages={401:'Login habis. Silakan login kembali.',403:'Akses ditolak. Periksa izin monitor.',
        404:'Sesi tidak ditemukan pada akun ini.',410:'Sesi sudah kedaluwarsa.'};
      this.stop(messages[error.status]);return;
    }
    if(++this.failures>6){this.stop('Belum tersambung. Periksa internet dan izin MQTT, lalu coba lagi.');return;}
    const delay=Math.min(30000,1000*2**(this.failures-1));
    this.onStatus(`Koneksi terputus · mencoba lagi ${Math.ceil(delay/1000)} detik…`,'loading');
    this.later(()=>this.open(generation),delay);
  }
}
