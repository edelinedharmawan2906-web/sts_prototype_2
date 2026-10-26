"""Camera/output wiring with test doubles; does not run MediaPipe inference."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import numpy as np


def run():
    cv = ModuleType('cv2')
    for name in ('CAP_DSHOW','CAP_MSMF','CAP_ANY','CAP_PROP_FPS','COLOR_BGR2RGB','FONT_HERSHEY_SIMPLEX'):
        setattr(cv,name,0)
    class Capture:
        def isOpened(self):return True
        def get(self, prop):return 30
        def read(self):return True,np.zeros((480,640,3),dtype=np.uint8)
        def release(self):pass
    cv.VideoCapture=lambda *args:Capture()
    written=[]
    class Writer:
        def __init__(self,path,*args):Path(path).touch()
        def isOpened(self):return True
        def write(self,frame):written.append(frame.copy())
        def release(self):pass
    cv.VideoWriter=Writer
    cv.VideoWriter_fourcc=lambda *args:0
    cv.cvtColor=lambda frame,*args:frame
    cv.putText=lambda *args:None
    cv.imshow=lambda *args:None
    cv.destroyAllWindows=lambda:None
    keys=iter((-1,ord('q')))
    cv.waitKey=lambda *args:next(keys)
    mp=ModuleType('mediapipe')
    lm=[SimpleNamespace(x=.1,y=.1,visibility=1.) for _ in range(33)]
    for i,x,y in ((11,.2,.2),(23,.2,.6),(25,.6,.6),(27,.6,.9)):
        lm[i].x=x;lm[i].y=y
    class Pose:
        def __init__(self,**kwargs):pass
        def process(self,frame):
            self.n=getattr(self,"n",0)+1
            return SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=lm) if self.n==1 else None)
        def close(self):pass
    mp.solutions=SimpleNamespace(pose=SimpleNamespace(Pose=Pose,POSE_CONNECTIONS=()),
        drawing_utils=SimpleNamespace(draw_landmarks=lambda frame,*args:frame.fill(255)))
    saved_modules={k:sys.modules.get(k) for k in ('cv2','mediapipe')}
    saved_argv=sys.argv[:]
    try:
        sys.modules['cv2']=cv;sys.modules['mediapipe']=mp
        root=Path(__file__).resolve().parent
        spec=importlib.util.spec_from_file_location('sts_app_smoke',root/'app.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            sys.argv=['app.py','--config',str(root/'config.json'),'--output',tmp,'--model','full']
            module.main()
            session=json.loads(next(Path(tmp).glob('session_*.json')).read_text())
            assert session['version']=='0.5.6' and session['complete']==0
            assert session['config']['standing_window']==.5
            assert session['hand_warning']['enabled'] is False
            assert session['capture_archive']['frames_written']==2
            assert session['capture_archive']['error'] is None
            assert len(written)==2
            assert all(not frame.any() for frame in written)
            raw=[json.loads(line) for line in next(Path(tmp).glob('raw_*.jsonl')).read_text().splitlines()]
            assert len(raw)==2 and len(raw[0]['landmarks'])==33
            assert raw[0]['raw_angles']['hip']==90
            assert raw[0]['frame_index']==1 and raw[1]['frame_index']==2
            frames=list(csv.DictReader(next(Path(tmp).glob('frames_*.csv')).open()))
            assert len(frames)==2 and frames[0]['video_frame_index']=='0'
            assert frames[1]['time']==str(raw[1]['time'])
            rows=list(csv.DictReader(next(Path(tmp).glob('diagnostics_*.csv')).open()))
            assert len(rows)==2
            assert all(r['hand_context']=='False' and r['hand_stable']=='' for r in rows)
            assert [r['accepted'] for r in rows]==['True','False']
            assert raw[1]['raw_angles'] is None and raw[1]['landmarks'] is None
            assert raw[0]['image_size']==[640,480]
            # Failed codec must be explicit; raw tracking remains usable.
            class FailedWriter(Writer):
                def isOpened(self):return False
            cv.VideoWriter=FailedWriter
            from capture_archive import CaptureArchive
            failed=CaptureArchive(Path(tmp),'failed_codec',30)
            failed.write_frame(np.zeros((480,640,3),dtype=np.uint8),0.,1)
            failed.write_features(SimpleNamespace(pose_landmarks=None),None,0.,1,'CAL_DUDUK',dict(accepted=False,reason='pose_missing'))
            failed.close()
            assert failed.error and failed.count==0 and failed.last_video_index is None
            assert json.loads(failed.raw.read_text())['image_size']==[640,480]
    finally:
        sys.argv=saved_argv
        for name,old in saved_modules.items():
            if old is None:sys.modules.pop(name,None)
            else:sys.modules[name]=old
    print('v0.5.6: camera/output smoke test passed (test doubles only)')


if __name__=='__main__':run()
