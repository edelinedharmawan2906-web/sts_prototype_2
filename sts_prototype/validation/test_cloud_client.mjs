import test from 'node:test';
import assert from 'node:assert/strict';
import {CloudStsClient} from './cloud-client-test.mjs';

const ok = result => ({status:200,ok:true,json:async()=>({status:'ok',result})});
function setup(){
  const saved=new Map([['sts.cloud.access.v1',JSON.stringify({accessToken:'test.token.signature',expiresAt:Date.now()+3600000})]]);
  globalThis.sessionStorage={getItem:k=>saved.get(k)??null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)};
  const calls=[],frames=[],receipts=new Map();let version=0,closed=false,loseResponse=false,commitLosses=0;
  const state=()=>({session_id:'session-1',version,closed,complete:0,cycles:0,attempts:[],personal_calibration:{},rules:{},frame_interval:1/15});
  globalThis.fetch=async(url,options)=>{
    assert.equal(options.headers.Authorization,'Bearer test.token.signature');
    const command=JSON.parse(options.body);calls.push(command);
    if(command.action==='create')return ok(state());
    if(command.action==='status')return ok(state());
    if(command.action==='history')return ok({batches:[{frames}]});
    if(command.action==='health')return {ok:true,status:200,json:async()=>({status:'ok',mode:'authenticated_http'})};
    if(receipts.has(command.request_id)){
      assert.equal(receipts.get(command.request_id).body,options.body);
      if(commitLosses>0){commitLosses--;throw new TypeError('lost response again');}
      return ok(receipts.get(command.request_id).result);
    }
    assert.equal(command.expected_version,version);
    if(command.action==='frames')frames.push(...command.payload);
    if(command.action==='finish')closed=true;
    version++;
    const result=state();receipts.set(command.request_id,{body:options.body,result});
    if(loseResponse&&command.action==='frames'){loseResponse=false;throw new TypeError('response lost after commit');}
    return ok(result);
  };
  return {calls,frames,loseNext:()=>{loseResponse=true},loseThree:()=>{loseResponse=true;commitLosses=2}};
}
test('capture does not wait for server; finish drains frames with original timestamps',async()=>{
  const mock=setup(), client=new CloudStsClient();await client.create(640,480);
  for(let i=0;i<50;i++)await client.frame(i/15,null);
  assert.equal(mock.frames.length,0);
  await client.calibrate('duduk',10);
  for(let i=50;i<65;i++)await client.frame(i/15,null);
  const end=await client.finish();assert.equal(end.closed,true);
  assert.deepEqual(mock.frames.map(f=>f.t),Array.from({length:65},(_,i)=>i/15));
  const writes=mock.calls.filter(c=>c.action==='frames');
  assert(writes.length<65);assert(writes.every(c=>c.payload.length<=30));
  assert.equal((await client.export()).frames.length,65);
});
test('lost response retry reuses exact command and never duplicates frames',async()=>{
  const mock=setup(),client=new CloudStsClient();await client.create(640,480);
  for(let i=0;i<10;i++)await client.frame(i/15,null);
  mock.loseNext();await client.finish();
  assert.equal(mock.frames.length,10);
  const calls=mock.calls.filter(c=>c.action==='frames');assert.equal(calls.length,2);
  assert.deepEqual(calls[0],calls[1]);
});
test('calibration barrier finishes while capture continues',async()=>{
  setup();const original=globalThis.fetch;
  globalThis.fetch=async(u,o)=>{
    if(JSON.parse(o.body).action==='frames')await new Promise(resolve=>setTimeout(resolve,100));
    return original(u,o);
  };
  const client=new CloudStsClient();await client.create(640,480);
  let i=0;await client.frame(i++/15,null);
  const first=client.flush();
  const producer=setInterval(()=>{client.frame(i++/15,null).catch(()=>{})},30);
  try{
    await Promise.race([client.calibrate('duduk',5),new Promise((_,reject)=>setTimeout(()=>reject(Error('calibration hung')),800))]);
  }finally{clearInterval(producer)}
  await first;await client.finish();
});
test('uncertain commit can be recovered by repeating finish',async()=>{
  const mock=setup(),client=new CloudStsClient();await client.create(640,480);
  await client.frame(0,null);mock.loseThree();
  await assert.rejects(client.finish(),/lost response/);
  assert.equal((await client.finish()).closed,true);
  assert.equal(mock.frames.length,1);
});
