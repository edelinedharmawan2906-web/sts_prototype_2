import type {State,Landmark,HistoryPage,HistoryRecord} from './types';
/** Browser-side HTTP client. STS calculations stay in Python. */
export class StsClient {
  sessionId='';
  private queue:Promise<unknown>=Promise.resolve();
  constructor(private base=''){}
  private request<T>(path:string,method='GET',body?:unknown):Promise<T> {
    const operation=async()=>{
      const controller=new AbortController();
      const timeout=setTimeout(()=>controller.abort(),10000);
      try {
        const r=await fetch(this.base+path,{method,signal:controller.signal,
          headers:{'Content-Type':'application/json'},
          body:body===undefined?undefined:JSON.stringify(body)});
        if(!r.ok){const text=await r.text();throw Error(`Backend ${r.status}: ${text}`)}
        return await r.json() as T;
      } finally {clearTimeout(timeout)}
    };
    const next=this.queue.then(operation,operation);this.queue=next.catch(()=>{});return next;
  }
  async create(width:number,height:number){
    const r=await this.request<State & {session_id:string}>('/sessions','POST',{width,height,input_source:'browser_camera'});
    this.sessionId=r.session_id;return r;
  }
  calibrate(posture:'duduk'|'berdiri',delay=10){return this.request<State>(`/sessions/${this.sessionId}/calibration`,'POST',{posture,delay})}
  frame(t:number,landmarks:Landmark[]|null){return this.request<State>(`/sessions/${this.sessionId}/frames`,'POST',{t,landmarks})}
  finish(){return this.request<State>(`/sessions/${this.sessionId}/finish`,'POST')}
  export(){return this.request<Record<string,unknown>>(`/sessions/${this.sessionId}/export`)}
  history(offset=0){return this.request<HistoryPage>(`/history?limit=50&offset=${offset}`)}
  detail(id:string){return this.request<HistoryRecord>(`/history/${encodeURIComponent(id)}`)}
  health(){return this.request<{status:string}>('/health')}
}
