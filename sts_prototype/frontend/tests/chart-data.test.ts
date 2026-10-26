import assert from 'node:assert/strict';
import {appendPoint,phaseLabel,plotSegments,pointsFromFrames,pointFromState} from '../src/angle-data';
import type {AnglePoint} from '../src/angle-data';
const p=(t:number,knee:number|null=90):AnglePoint=>({t,mode:'LATIHAN',phase:'DUDUK',knee,hip:knee,lean:knee===null?null:0});

// Missing measurements and time gaps must not become interpolated lines.
const missing=[p(0),p(.1),p(.2,null),p(.3),p(.4)];
assert.deepEqual(plotSegments(missing,'knee',.3).map(s=>s.map(v=>v.t)),[[0,.1],[.3,.4]]);
assert.deepEqual(plotSegments([p(0),p(.1),p(1),p(1.1)],'knee',.3).map(s=>s.length),[2,2]);
assert.equal(plotSegments([p(0,null)],'knee',.3).length,0);

// Extrema survive reduction; domain includes all raw observations.
const dense=Array.from({length:36000},(_,i)=>p(i*.01,i===11000?179:i===11001?1:90));
const reduced=plotSegments(dense,'knee',.3);
assert.equal(reduced.length,1);
assert.ok(reduced[0].length<2500);
assert.ok(reduced[0].some(v=>v.knee===179));assert.ok(reduced[0].some(v=>v.knee===1));
assert.equal(reduced[0][0].t,0);assert.equal(reduced[0].at(-1)!.t,dense.at(-1)!.t);

// History loading supports missing fields and rejects invalid/duplicate times.
const frames=[{t:0,mode:'LATIHAN',phase:'DUDUK',measurement:{knee:92,hip:80,lean:5}},
 {t:.1,mode:'LATIHAN',phase:'DUDUK',quality:{accepted:false},measurement:{knee:99,hip:99,lean:99}},
 {t:.2,measurement:null},{t:.2,measurement:{knee:1}},{t:-1},{t:'bad'},null];
const history=pointsFromFrames(frames);
assert.equal(history.length,3);assert.equal(history[0].knee,92);assert.equal(history[1].knee,null);
assert.equal(history[2].mode,'TIDAK_DIKETAHUI');
const lost=pointFromState(1,{mode:'LATIHAN',phase:'BANGKIT',quality:{accepted:false},measurement:{knee:170,hip:160,lean:20}});
assert.equal(lost.knee,null);

// Live buffers are bounded per session, never combine repeated timestamps.
let buffer:AnglePoint[]=[];
for(let i=0;i<5000;i++)buffer=appendPoint(buffer,p(i*.05));
assert.ok(buffer.length<=2400);assert.ok(buffer[0].t>=buffer.at(-1)!.t-120);
assert.equal(appendPoint(buffer,p(buffer.at(-1)!.t)),buffer);
assert.equal(phaseLabel({...p(0),mode:'CAL_BERDIRI'}),'Kalibrasi berdiri');
assert.equal(phaseLabel({...p(0),phase:'BANGKIT'}),'Bangkit');
console.log('PASS chart data: gaps, missing data, extrema, old history, bounded live buffer and phase labels.');
