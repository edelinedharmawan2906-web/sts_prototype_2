import test from 'node:test';
import assert from 'node:assert/strict';
import {monitorLstmValues} from '../camera/lstm-monitor.mjs';
import {acceptSnapshot,snapshotFromStatus} from '../camera/monitor-core.mjs';
test('legacy sessions show unavailable rather than stale numbers',()=>{
  const values=monitorLstmValues();assert.equal(values['lstm-left'],'—');
  assert.match(values['lstm-status'],/belum memiliki/);
});
test('ready flexion has no 180 degree conversion in monitor',()=>{
  const result={status:'ready',knee_flexion_deg:{left:15,right:null},geometry_knee_flexion_deg:{left:16,right:20}};
  const values=monitorLstmValues(result);assert.equal(values['lstm-left'],'15.0°');
  assert.equal(values['geo-left'],'16.0°');assert.equal(values['lstm-right'],'—');
  const incoming=snapshotFromStatus({session_id:'abc',version:1,complete:0,cycles:0,attempts:[],closed:false,lstm:result});
  assert.deepEqual(acceptSnapshot(null,incoming,'abc').lstm,result);
});
test('missing pose and errors clear displayed numbers',()=>{
  for(const status of ['pose_missing','warming_up','inference_error','disabled'])
    assert.equal(monitorLstmValues({status,knee_flexion_deg:{left:90,right:90}})['lstm-left'],'—');
});
