import test from 'node:test';
import assert from 'node:assert/strict';
import {challenge, loginUrl, callback, accessToken, testApi, config, clearLogin} from './frontend/public/sts-cloud-auth.mjs';
const storage = () => { const m=new Map(); return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}; };
const location = () => new URL(config.redirectUri);
async function returning(s, now=Date.now()) {
  const login=new URL(await loginUrl(s,location(),now));
  const url=location(); url.search=new URLSearchParams({code:'one-time-code',state:login.searchParams.get('state')});
  return url;
}
const tokens = () => ({ok:true,status:200,json:async()=>({access_token:'header.payload.signature',token_type:'Bearer',expires_in:3600})});

test('PKCE S256 matches RFC 7636 example',async()=>{
  assert.equal(await challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'),'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
});
test('login uses configured domain, scopes and fresh state with exact callback',async()=>{
  const s=storage(), a=new URL(await loginUrl(s,location())), b=new URL(await loginUrl(s,location()));
  assert.equal(a.origin,config.domain); assert.equal(a.searchParams.get('code_challenge_method'),'S256');
  assert.equal(a.searchParams.get('scope'),'openid email');
  assert.equal(a.searchParams.get('redirect_uri'),config.redirectUri);
  assert.notEqual(a.searchParams.get('state'),b.searchParams.get('state'));
  await assert.rejects(loginUrl(s,new URL('http://127.0.0.1:8000/camera/')));
});
test('callback exchanges code once, scrubs URL and sends access token to API',async()=>{
  const s=storage(), url=await returning(s); let scrubbed=false, exchanges=0;
  await callback(s,url,{replaceState:(_,__,clean)=>{assert(!clean.includes('code='));scrubbed=true;}},async(u,o)=>{
    exchanges++; assert(scrubbed); assert.equal(new URL(u).pathname,'/oauth2/token');
    assert.equal(o.body.get('code'),'one-time-code'); assert.equal(o.body.get('code_verifier').length,43);
    assert(!o.body.has('client_secret')); return tokens();
  });
  assert.equal(accessToken(s),'header.payload.signature');
  await testApi(s,async(u,o)=>{
    assert.equal(u,config.apiUrl); assert.equal(o.headers.Authorization,'Bearer header.payload.signature');
    assert.equal(o.body,'{"action":"health"}');
    return {ok:true,status:200,json:async()=>({status:'ok',mode:'authenticated_http'})};
  });
  await assert.rejects(callback(s,url,{replaceState(){}},()=>{throw Error('Must not retry code');}));
  assert.equal(exchanges,1);
});
test('state mismatch, expired callback and duplicate fields never call token endpoint',async()=>{
  for(const kind of ['state','expired','duplicate']) {
    const s=storage(), now=Date.now(), url=await returning(s,now);
    if(kind==='state') url.searchParams.set('state','wrong');
    if(kind==='duplicate') url.searchParams.append('code','other');
    await assert.rejects(callback(s,url,{replaceState(){}},()=>{throw Error('Not allowed');},kind==='expired'?now+601000:now),/Sesi login/);
    assert.equal(accessToken(s),null);
  }
});
test('expired access token and API 401 clear tab login',async()=>{
  const s=storage(), now=Date.now(), url=await returning(s,now);
  await callback(s,url,{replaceState(){}},async()=>tokens(),now);
  assert.equal(accessToken(s,now+3600000),null);
  const next=await returning(s);
  await callback(s,next,{replaceState(){}},async()=>tokens());
  await assert.rejects(testApi(s,async()=>({status:401,ok:false})),/401/);
  assert.equal(accessToken(s),null); clearLogin(s);
});
test('Lambda error payload is never reported as success',async()=>{
  const s=storage(), url=await returning(s);
  await callback(s,url,{replaceState(){}},async()=>tokens());
  await assert.rejects(testApi(s,async()=>({status:200,ok:true,json:async()=>({status:'error'})})),/belum sesuai/);
});
