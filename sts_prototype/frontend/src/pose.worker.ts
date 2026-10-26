import {FilesetResolver,PoseLandmarker} from '@mediapipe/tasks-vision';
let model:PoseLandmarker|undefined;
const scope=self as unknown as {onmessage:(event:MessageEvent)=>void;postMessage:(message:unknown)=>void};
scope.onmessage=async(event)=>{
  const data=event.data;
  try {
    if(data.type==='init'){
      const files=await FilesetResolver.forVisionTasks(data.root+'mediapipe/wasm');
      model=await PoseLandmarker.createFromOptions(files,{
        baseOptions:{modelAssetPath:data.root+'mediapipe/pose_landmarker_full.task',delegate:'CPU'},
        runningMode:'VIDEO',numPoses:1,minPoseDetectionConfidence:.5,
        minPosePresenceConfidence:.5,minTrackingConfidence:.5,
        outputSegmentationMasks:false,
      });
      scope.postMessage({type:'ready'});
    } else if(data.type==='frame'){
      if(!model)throw Error('Model belum siap');
      const start=performance.now();
      const result=model.detectForVideo(data.bitmap,data.timestamp);
      scope.postMessage({type:'result',landmarks:result.landmarks[0]?.map(l=>({x:l.x,y:l.y,z:l.z,visibility:l.visibility}))??null,inferenceMs:performance.now()-start});
    }
  }catch(error){scope.postMessage({type:'error',message:error instanceof Error?error.message:String(error)})}
  finally{data.bitmap?.close()}
};
