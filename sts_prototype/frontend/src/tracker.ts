import type {Landmark} from './types';
export class Tracker {
  private worker=new Worker(new URL('./pose.worker.ts',import.meta.url));
  private pending:{resolve:(data:any)=>void;reject:(e:Error)=>void;timer:ReturnType<typeof setTimeout>}|null=null;
  constructor(){
    this.worker.onmessage=event=>{
      const pending=this.pending;if(!pending)return;
      clearTimeout(pending.timer);this.pending=null;
      if(event.data.type==='error')pending.reject(Error(event.data.message));else pending.resolve(event.data);
    };
    this.worker.onerror=event=>{if(this.pending){clearTimeout(this.pending.timer);this.pending.reject(Error(event.message||'MediaPipe worker gagal'));this.pending=null}};
  }
  private send(data:unknown,transfer:Transferable[]=[],timeout=15000):Promise<any>{
    if(this.pending)return Promise.reject(Error('Frame sebelumnya belum selesai'));
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending=null;reject(Error('MediaPipe terlalu lama merespons. Akhiri sesi lalu coba lagi.'))},timeout);
      this.pending={resolve,reject,timer};
      try{this.worker.postMessage(data,transfer)}catch(error){clearTimeout(timer);this.pending=null;reject(error)}
    });
  }
  init(root:string){return this.send({type:'init',root},[],60000)}
  frame(bitmap:ImageBitmap,timestamp:number):Promise<{landmarks:Landmark[]|null;inferenceMs:number}>{return this.send({type:'frame',bitmap,timestamp},[bitmap])}
  close(){if(this.pending){clearTimeout(this.pending.timer);this.pending.reject(Error('MediaPipe dihentikan'));this.pending=null}this.worker.terminate()}
}
