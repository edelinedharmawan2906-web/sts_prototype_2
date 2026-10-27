import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {readFile} from 'node:fs/promises';
import {acceptSnapshot,checkGrant,snapshotFromStatus,MonitorConnection} from '../camera/monitor-core.mjs';
const sid='camera-123',owner='cognito-'+'a'.repeat(64),now=1700000000000;
const grant=(id=sid)=>({url:'wss://as4p4a02r32pn-ats.iot.ap-southeast-2.amazonaws.com/mqtt?signature=fake',
  client_id:'sts-monitor-'+'b'.repeat(32),topic:`sts/cloud/${owner}/${id}/state`,read_only:true,qos:1,
  credentials_expire_at:new Date(now+900000).toISOString(),initial_state:state(1,id)});
function state(version=1,id=sid){return {schema:'sts-live-v1',session_id:id,version,attempt_count:2,complete:1,cycles:0,closed:false};}
class Timers {
  constructor(){this.jobs=new Map();this.next=0;}
  setTimeout(fn,ms){const id=++this.next;this.jobs.set(id,{fn,ms});return id;}
  clearTimeout(id){this.jobs.delete(id);}
  fire(ms){const match=[...this.jobs].find(([id,j])=>j.ms===ms);assert.ok(match,`Timer ${ms} exists`);this.jobs.delete(match[0]);match[1].fn();}
}
const flush=async()=>{await new Promise(resolve=>setImmediate(resolve));};
function setup(overrides={}){
  const timers=new Timers(),calls=[],clients=[],states=[],statuses=[];
  let loggedIn=true;
  const api=overrides.api||(async(action,id)=>{calls.push([action,id]);return action==='monitor_connect'?grant(id):state(2,id);});
  const controller=new MonitorConnection({api,connect:(url,options)=>{
    const client=new EventEmitter();client.options=options;client.url=url;
    client.subscribe=(topic,opts,cb)=>{client.topic=topic;client.subcb=cb;};
    client.end=()=>{client.ended=true;};clients.push(client);return client;
  },hasLogin:()=>loggedIn,onState:(value,source)=>states.push([value,source]),
  onStatus:(...args)=>statuses.push(args),timers,now:()=>now});
  return {controller,timers,calls,clients,states,statuses,logout:()=>{loggedIn=false;}};
}

test('reject duplicate, stale, wrong-session and malformed snapshots',()=>{
  const current=state(5);
  for(const incoming of [state(5),state(4),state(6,'other'),{...state(6),closed:'false'},
    {...state(6),cycles:-1},{...state(6),version:Infinity},{...state(6),schema:'other'}])
    assert.equal(acceptSnapshot(current,incoming,sid),current);
  assert.equal(acceptSnapshot(current,state(6),sid).version,6);
});
test('derive attempt count for status including ongoing bangkit',()=>{
  assert.equal(snapshotFromStatus({attempts:[{},{}],phase:'BANGKIT'}).attempt_count,3);
  assert.equal(snapshotFromStatus({attempts:[{},{}],phase:'BERDIRI'}).attempt_count,2);
});
test('validate exact read-only grant and reject endpoint/topic substitution',()=>{
  assert.equal(checkGrant(grant(),sid,now),780000);
  for(const patch of [{topic:'sts/cloud/#'},{topic:`sts/cloud/${owner}/other/state`},
    {read_only:false},{client_id:'arbitrary'},{qos:2},
    {credentials_expire_at:new Date(now).toISOString()},
    {url:'wss://evil.example/mqtt'},{url:'ws://as4p4a02r32pn-ats.iot.ap-southeast-2.amazonaws.com/mqtt'}])
    assert.throws(()=>checkGrant({...grant(),...patch},sid,now));
});
test('connect read-only with exact client; fetch status only after SUBACK',async()=>{
  const x=setup();x.controller.start(sid);await flush();
  const client=x.clients[0];assert.equal(client.options.reconnectPeriod,0);
  assert.equal(client.options.protocolVersion,4);assert.equal(client.options.clean,true);
  assert.deepEqual(x.calls,[['monitor_connect',sid]]);
  client.emit('connect');assert.equal(client.topic,grant().topic);
  client.subcb(null,[{qos:1}]);await flush();
  assert.equal(x.calls[1][0],'status');assert.equal(x.controller.current.version,2);
});
test('newer MQTT message wins over delayed database status',async()=>{
  let resolveStatus;
  const x=setup({api:async action=>action==='monitor_connect'?grant():new Promise(r=>resolveStatus=r)});
  x.controller.start(sid);await flush();const client=x.clients[0];client.emit('connect');client.subcb(null,[{qos:1}]);
  client.emit('message',grant().topic,Buffer.from(JSON.stringify(state(5))));
  resolveStatus(state(3));await flush();assert.equal(x.controller.current.version,5);
});
test('ignore packet from other topic and oversized/malformed packet',async()=>{
  const x=setup();x.controller.start(sid);await flush();const client=x.clients[0];
  client.emit('message','sts/cloud/other',Buffer.from(JSON.stringify(state(8))));
  client.emit('message',grant().topic,Buffer.from('invalid'));
  client.emit('message',grant().topic,Buffer.alloc(17000));
  assert.equal(x.controller.current.version,1);
});
test('reconnect requests fresh grant instead of reusing URL',async()=>{
  const x=setup();x.controller.start(sid);await flush();x.clients[0].emit('close');
  assert.equal(x.clients[0].ended,true);x.timers.fire(1000);await flush();
  assert.equal(x.calls.filter(c=>c[0]==='monitor_connect').length,2);
});
test('failed SUBACK never reports connected and schedules recovery',async()=>{
  const x=setup();x.controller.start(sid);await flush();x.clients[0].emit('connect');
  x.clients[0].subcb(null,[{qos:128}]);await flush();
  assert.equal(x.statuses.some(s=>s[1]==='connected'),false);assert.equal(x.clients[0].ended,true);
});
test('changing session rejects late grant from previous selection',async()=>{
  let oldResolve;
  const x=setup({api:async(action,id)=>id===sid?new Promise(r=>oldResolve=r):grant(id)});
  x.controller.start(sid);x.controller.start('other-session');await flush();
  oldResolve(grant());await flush();assert.equal(x.clients.length,1);
  assert.equal(x.controller.current.session_id,'other-session');
});
test('explicit stop prevents pending retry and late network effects',async()=>{
  const x=setup();x.controller.start(sid);await flush();x.clients[0].emit('close');
  x.controller.stop();assert.equal(x.timers.jobs.size,0);
  assert.equal(x.controller.enabled,false);
});
test('expired login closes connection without requesting more grants',async()=>{
  const x=setup();x.controller.start(sid);await flush();x.logout();x.timers.fire(15000);
  assert.equal(x.controller.enabled,false);assert.equal(x.clients[0].ended,true);
  assert.equal(x.timers.jobs.size,0);
});
test('refresh connection before temporary credentials expire',async()=>{
  const x=setup();x.controller.start(sid);await flush();x.timers.fire(780000);await flush();
  assert.equal(x.clients[0].ended,true);assert.equal(x.clients.length,2);
});
test('not found or expired owned session stops without retries',async()=>{
  for(const status of [401,403,404,410]) {
    const x=setup({api:async()=>{throw {status};}});x.controller.start(sid);await flush();
    assert.equal(x.controller.enabled,false);assert.equal(x.timers.jobs.size,0);assert.equal(x.clients.length,0);
  }
});
test('retry budget prevents unlimited failing connections',async()=>{
  const x=setup({api:async()=>{throw new Error('network');}});x.controller.start(sid);await flush();
  for(const ms of [1000,2000,4000,8000,16000,30000]){x.timers.fire(ms);await flush();}
  assert.equal(x.controller.enabled,false);assert.equal(x.timers.jobs.size,0);
});

async function cameraLogin({authenticated=false,query='',returnTime=null,callbackLogin=false}={}) {
  const redirects=[],map=new Map();if(returnTime!==null)map.set('sts.monitor.login-return.v1',String(returnTime));
  const storage={getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
  const output={dataset:{},textContent:''};
  const panel={setAttribute(){},querySelector:()=>output,querySelectorAll:()=>[],addEventListener(){}};
  const document={createElement:()=>panel,body:{prepend(){}}};
  const location={href:'https://sts.test/camera/'+query,origin:'https://sts.test',pathname:'/camera/',
    replace:url=>redirects.push(['replace',url]),assign:url=>redirects.push(['assign',url])};
  const window={location,history:{replaceState(){}}};
  const source=(await readFile(new URL('../camera/sts-cloud-login.mjs',import.meta.url),'utf8')).replace(/^import[^\n]+\n/,'');
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  const run=new AsyncFunction('document','window','sessionStorage','loginUrl','callback','accessToken','clearLogin','testApi',source);
  await run(document,window,storage,async()=> 'https://login.example/authorize',async()=>{if(callbackLogin)authenticated=true;},
    ()=>authenticated?'token':null,()=>{authenticated=false;},async()=>({}));
  return {redirects,map};
}
test('monitor login reuses authenticated tab and fixed monitor destination',async()=>{
  const x=await cameraLogin({authenticated:true,query:'?monitor_login=1'});
  assert.deepEqual(x.redirects,[['replace','/camera/monitor.html']]);
});
test('monitor login stores return intent and redirects to Cognito',async()=>{
  const x=await cameraLogin({query:'?monitor_login=1'});
  assert.deepEqual(x.redirects,[['assign','https://login.example/authorize']]);
  assert.ok(Number(x.map.get('sts.monitor.login-return.v1'))>0);
});
test('successful callback returns to monitor; expired return intent is ignored',async()=>{
  const x=await cameraLogin({callbackLogin:true,returnTime:Date.now()});
  assert.deepEqual(x.redirects,[['replace','/camera/monitor.html']]);
  assert.equal(x.map.has('sts.monitor.login-return.v1'),false);
  const expired=await cameraLogin({authenticated:true,returnTime:Date.now()-700000});
  assert.deepEqual(expired.redirects,[]);
});
