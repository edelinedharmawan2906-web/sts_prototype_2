import {StsClient} from './sts-client';
import type {State,Landmark} from './types';
import {accessToken,config} from '../public/sts-cloud-auth.mjs';

type CloudState = State & {version:number; session_id:string;dimensions?:{width:number;height:number};input_source?:string};
type Command = {action:string;request_id?:string;session_id?:string;expected_version?:number;payload?:unknown};
type Frame = {t:number;landmarks:Landmark[]|null};
const wait = (ms:number) => new Promise(resolve=>setTimeout(resolve,ms));

/** Capture timestamps remain unchanged. One bounded queue, one writer per session. */
export class CloudStsClient extends StsClient {
  private current:CloudState|null=null;
  private frames:Frame[]=[];
  private serial:Promise<unknown>=Promise.resolve();
  private flushing:Promise<void>|null=null;
  private timer:ReturnType<typeof setTimeout>|null=null;
  private fatal:Error|null=null;
  private pending:Command|null=null;
  private dimensions={width:640,height:480};
  onState:((state:State,t:number,ms:number)=>void)|null=null;

  private async post(command:Command):Promise<any>{
    const text=JSON.stringify(command); // Same ID, version and payload for every retry.
    for(let attempt=0;attempt<3;attempt++){
      const token=accessToken(sessionStorage);
      if(!token)throw Error('Login AWS sudah habis. Jangan hapus login saat sesi berjalan.');
      try{
        const r=await fetch(config.apiUrl,{method:'POST',credentials:'omit',cache:'no-store',
          headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},
          body:text,signal:AbortSignal.timeout(25000)});
        if(r.status>=500||r.status===429){if(attempt<2){await wait(500*(attempt+1));continue}}
        if(!r.ok){
          let detail='';
          try{const problem=await r.json();if(typeof problem.code==='string')detail=' ('+problem.code+')'}catch{}
          const message=r.status===409?'Konflik versi sesi. Jangan buka dua kamera untuk sesi yang sama.':
            r.status===401?'Token ditolak. Login AWS perlu diperbarui.':`API cloud HTTP ${r.status}${detail}. Periksa versi Lambda dan simpan ID sesi.`;
          throw Object.assign(Error(message),{terminal:true,status:r.status});
        }
        const data=await r.json();
        if(data.status!=='ok')throw Object.assign(Error('Respons cloud gagal'),{terminal:true});
        return data;
      }catch(e){
        if((e as {terminal?:boolean})?.terminal||attempt===2)throw e;
        await wait(500*(attempt+1));
      }
    }
    throw Error('Tidak ada respons cloud');
  }
  private enqueue<T>(work:()=>Promise<T>):Promise<T>{
    const next=this.serial.then(work);this.serial=next.catch(()=>{});return next;
  }
  private mutation(action:string,payload:unknown):Promise<CloudState>{
    return this.enqueue(async()=>{
      if(this.pending)throw Error('Ada permintaan yang belum terkonfirmasi. Akhiri & simpan untuk mencoba ulang.');
      const command:Command={action,session_id:this.sessionId,request_id:crypto.randomUUID(),
        expected_version:this.current!.version,payload};
      this.pending=command;
      const data=await this.post(command);
      this.current=data.result;this.pending=null;
      return this.current!;
    });
  }
  private schedule(){
    if(this.timer||this.fatal)return;
    this.timer=setTimeout(()=>{this.timer=null;this.flush().catch(e=>{this.fatal=e instanceof Error?e:Error(String(e))})},600);
  }
  private flush():Promise<void>{
    if(this.flushing)return this.flushing;
    if(!this.frames.length)return Promise.resolve();
    if(this.fatal)return Promise.reject(this.fatal);
    const batch=this.frames.slice(0,30), started=performance.now();
    this.flushing=this.mutation('frames',batch).then(state=>{
      this.frames.splice(0,batch.length);
      this.onState?.(state,batch[batch.length-1].t,performance.now()-started);
    }).catch(e=>{this.fatal=e instanceof Error?e:Error(String(e));throw this.fatal})
      .finally(()=>{this.flushing=null;if(this.frames.length&&!this.fatal)this.schedule()});
    return this.flushing;
  }
  async health(){
    const r=await this.post({action:'health'});
    if(r.mode!=='authenticated_http')throw Error('Lambda v04 diperlukan');
    return {status:r.status as string};
  }
  async create(width:number,height:number){
    if(this.timer)clearTimeout(this.timer);this.timer=null;
    this.frames=[];this.fatal=null;this.pending=null;
    const data=await this.post({action:'create',request_id:crypto.randomUUID(),
      payload:{width,height,input_source:'browser_camera'}});
    this.dimensions={width,height};this.current=data.result;this.sessionId=this.current!.session_id;
    sessionStorage.setItem('sts.cloud.lastSession',this.sessionId);
    return this.current!;
  }
  async frame(t:number,landmarks:Landmark[]|null){
    if(this.fatal)throw this.fatal;
    if(this.frames.length>=120){this.fatal=Error('Cloud tertinggal lebih dari 120 frame. Akhiri & simpan; jangan lanjut bergerak.');throw this.fatal}
    this.frames.push({t,landmarks});this.schedule();
    return this.current!;
  }
  async calibrate(posture:'duduk'|'berdiri',delay=10){
    const boundary=this.frames.at(-1)?.t;
    while(boundary!==undefined&&this.frames.length&&this.frames[0].t<=boundary)await this.flush();
    if(this.fatal)throw this.fatal;
    return this.mutation('calibration',{posture,delay});
  }
  async finish(){
    if(this.timer)clearTimeout(this.timer);this.timer=null;
    // Recover an uncertain commit using its original immutable command.
    await this.serial;
    if(this.pending){
      const pending=this.pending;
      const data=await this.post(pending);this.current=data.result;this.pending=null;
      if(pending.action==='frames')this.frames.splice(0,(pending.payload as Frame[]).length);
    }
    this.fatal=null;
    while(this.frames.length)await this.flush();
    if(this.current?.closed)return this.current;
    return this.mutation('finish',{});
  }
  async export():Promise<Record<string,unknown>>{
    await this.serial;
    const state=(await this.post({action:'status',session_id:this.sessionId})).result as CloudState;
    const batches:{version:number;operation:string;frames:unknown[]}[]=[];
    let after=0;
    for(let pageNumber=0;pageNumber<36010;pageNumber++){
      const page=(await this.post({action:'history',session_id:this.sessionId,
        payload:{after_version:after,through_version:state.version,limit:3}})).result;
      if(page.through_version!==state.version||!Array.isArray(page.batches))throw Error('Ekspor bertahap memerlukan Lambda v05.');
      for(const batch of page.batches){
        if(!Number.isInteger(batch.version)||batch.version<=after||batch.version>state.version||!Array.isArray(batch.frames))throw Error('Urutan riwayat cloud tidak sesuai');
        after=batch.version;batches.push(batch);
      }
      if(page.next_after_version===null)break;
      if(page.next_after_version!==after||!page.batches.length)throw Error('Cursor ekspor tidak maju');
    }
    return {version:'camera-cloud-v02',session_id:this.sessionId,cloud_version:state.version,
      storage:'DynamoDB',transport:'HTTPS API Gateway + Cognito',source:'Python personal_dummy_v1',
      input_source:state.input_source??'browser_camera',angle_source:'geometry_2d',dimensions:state.dimensions??this.dimensions,
      personal_rules:state.rules,personal_calibration:state.personal_calibration,
      complete:state.complete,cycles:state.cycles,attempts:state.attempts,closed:state.closed,
      batches,frames:batches.flatMap(b=>b.frames)};
  }
  async cloudSessions(before?:string):Promise<CloudSessionPage>{
    return (await this.post({action:'sessions',payload:{limit:10,...(before?{before}:{})}})).result;
  }
  async cloudDetail(id:string,onUpdate:(detail:CloudDetail)=>void):Promise<CloudDetail>{
    const state=(await this.post({action:'status',session_id:id})).result as CloudState;
    let detail:CloudDetail={...state,session_id:id,frames:[],graphComplete:false};
    onUpdate(detail); // Show results before waiting for the chart.
    let after=0;
    for(let pageNumber=0;pageNumber<36010;pageNumber++){
      const page=(await this.post({action:'angles',session_id:id,
        payload:{after_version:after,through_version:state.version,limit:100}})).result;
      if(page.session_id!==id||page.through_version!==state.version||!Array.isArray(page.batches))throw Error('Grafik ringan memerlukan Lambda v07.');
      const frames:unknown[]=[];
      for(const batch of page.batches){
        if(batch.version!==after+1||batch.version>state.version||!Array.isArray(batch.frames))throw Error('Ada bagian grafik cloud yang belum tersedia. Buka ulang sesi.');
        after=batch.version;frames.push(...batch.frames);
      }
      const done=page.next_after_version===null;
      if(done&&after!==state.version)throw Error('Grafik cloud belum lengkap. Buka ulang sesi.');
      if(!done&&(page.next_after_version!==after||!page.batches.length))throw Error('Cursor grafik tidak maju');
      detail={...detail,frames:[...detail.frames,...frames],graphComplete:done};
      onUpdate(detail);
      if(done)return detail;
    }
    throw Error('Batas halaman grafik terlampaui');
  }
  async registerCloudSession(id:string){
    return (await this.post({action:'status',session_id:id})).result;
  }
}

export type CloudSessionItem={session_id:string;created_at:number;created_at_estimated:boolean;
  complete:number;cycles:number;attempt_count:number;closed:boolean;input_source:string;version:number};
export type CloudSessionPage={items:CloudSessionItem[];next_before:string|null};
export type CloudDetail=CloudState&{frames:unknown[];graphComplete:boolean};
