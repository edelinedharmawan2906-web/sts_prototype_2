/** API stays on the same origin as the page; only the MQTT endpoint varies. */
export async function loadBrokerUrl(page:Pick<Location,'protocol'|'host'|'hostname'>,signal?:AbortSignal):Promise<string>{
  const response=await fetch('/runtime-config',{signal,cache:'no-store'});
  if(!response.ok)throw Error('Runtime configuration unavailable');
  const config:unknown=await response.json();
  if(!config || typeof config!=='object')throw Error('Invalid configuration');
  const supplied=(config as {mqtt_ws_url?:unknown}).mqtt_ws_url;
  if(supplied!=null && typeof supplied!=='string')throw Error('Invalid broker URL');
  const fallback=page.protocol==='https:'?`wss://${page.host}/mqtt`:`ws://${page.hostname}:9001`;
  const url=new URL(typeof supplied==='string'&&supplied.trim()?supplied.trim():fallback);
  if(!['ws:','wss:'].includes(url.protocol)||url.username||url.password||url.hash)throw Error('Invalid broker URL');
  if(page.protocol==='https:'&&url.protocol!=='wss:')throw Error('HTTPS requires secure MQTT WebSocket');
  return url.href;
}
