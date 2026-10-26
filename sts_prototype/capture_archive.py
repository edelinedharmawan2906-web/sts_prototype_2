"""Archive unannotated processed input frames and their actual time mapping.

Video uses a fixed playback FPS. CSV time is authoritative for variable-rate
camera input. This records frames read by the application, not unseen frames.
"""
import csv
import json
from pathlib import Path
import cv2


class CaptureArchive:
    def __init__(self,out,stamp,fps):
        self.video=Path(out)/f'camera_{stamp}.avi'
        self.timeline=Path(out)/f'frames_{stamp}.csv'
        self.raw=Path(out)/f'raw_{stamp}.jsonl'
        self.fps=float(fps); self.writer=None; self.count=0; self.error=None
        self.size=None; self.input_size=None; self.last_video_index=None
        self.timeline_file=self.timeline.open('w',newline='',encoding='utf-8')
        self.timeline_writer=csv.DictWriter(self.timeline_file,fieldnames=['frame_index','video_frame_index','time','video_written'])
        self.timeline_writer.writeheader()
        self.raw_file=self.raw.open('w',encoding='utf-8')

    def write_frame(self,frame,t,index):
        h,w=frame.shape[:2]
        self.input_size=(w,h)
        if self.writer is None and self.error is None:
            writer=cv2.VideoWriter(str(self.video),cv2.VideoWriter_fourcc(*'MJPG'),self.fps,(w,h))
            if not writer.isOpened():
                writer.release();self.error='Codec MJPG/AVI tidak dapat dibuka'
                print('Rekaman kamera gagal: '+self.error)
            else:self.writer=writer;self.size=(w,h)
        self.last_video_index=None
        written=False
        if self.writer is not None:
            if self.size!=(w,h):
                self.error='Ukuran frame berubah; rekaman video dihentikan'
                self.writer.release();self.writer=None
                print(self.error)
            else:
                self.writer.write(frame);written=True;self.last_video_index=self.count
        self.timeline_writer.writerow(dict(frame_index=index,video_frame_index=self.count if written else '',time=t,video_written=written))
        if written:self.count+=1

    def write_features(self,result,measurement,t,index,mode,quality):
        landmarks=None
        if result.pose_landmarks:
            landmarks=[dict(id=i,x=float(p.x),y=float(p.y),z=float(getattr(p,'z',0)),visibility=float(p.visibility))
                       for i,p in enumerate(result.pose_landmarks.landmark)]
        self.raw_file.write(json.dumps(dict(frame_index=index,video_frame_index=self.last_video_index,time=t,mode=mode,
            accepted=bool(quality['accepted']),reason=quality['reason'],
            image_size=list(self.input_size) if self.input_size else None,
            raw_angles=measurement,landmarks=landmarks),allow_nan=False)+'\n')

    def close(self):
        if self.writer is not None:self.writer.release()
        self.timeline_file.close();self.raw_file.close()

    def metadata(self):
        return dict(video=self.video.name,frames=self.timeline.name,raw=self.raw.name,
            frames_written=self.count,playback_fps=self.fps,error=self.error,
            timing='Use frames CSV time, not AVI playback time, for original session timing',
            landmarks='Normalized MediaPipe image coordinates; z is model-relative, not metres',
            scope='Input frames before skeleton/text; includes calibration and rejected poses')
