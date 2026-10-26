import {mkdir,cp,writeFile,stat,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
await mkdir('public/mediapipe',{recursive:true});
await cp('node_modules/@mediapipe/tasks-vision/wasm','public/mediapipe/wasm',{recursive:true});
const path='public/mediapipe/pose_landmarker_full.task';
const url='https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task';
let exists=false;try{exists=(await stat(path)).size>1000000}catch{}
if(!exists){const response=await fetch(url);if(!response.ok)throw Error(`Model download: ${response.status}`);const bytes=Buffer.from(await response.arrayBuffer());if(bytes.length<1000000)throw Error('Unduhan model tidak lengkap');await writeFile(path,bytes)}
await writeFile('public/mediapipe/SOURCE.json',JSON.stringify({package:'@mediapipe/tasks-vision@0.10.21',model_url:url,sha256:createHash('sha256').update(await readFile(path)).digest('hex')},null,2));
console.log('MediaPipe WASM dan model Full siap secara lokal.');
