import {build} from 'esbuild';
const result=await build({entryPoints:['tests/chart-data.test.ts'],bundle:true,write:false,platform:'node',format:'esm'});
await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].contents).toString('base64'));
