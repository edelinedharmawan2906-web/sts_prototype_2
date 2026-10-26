"""Run on the user's laptop: python app.py --source 0."""
import argparse
import csv
import json
import math
import time
import sys
from calibration import speed_stats, collect_calibration
from signals import MAX_SAMPLE_GAP
from serialization import json_scalar
from diagnostics import pose_quality
from hand_warning import HandWarning
from capture_archive import CaptureArchive
from assessment import display_lines
from pathlib import Path
import cv2
import mediapipe as mp
import numpy as np
from engine import Engine, Config


from measurements import angle, measure


def open_capture(source, backend):
    if not source.isdigit():
        cap=cv2.VideoCapture(source)
        if cap.isOpened(): return cap
        cap.release()
        raise RuntimeError('Video tidak dapat dibuka: '+source)
    choices={'auto': ([cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]), 'dshow':[cv2.CAP_DSHOW], 'msmf':[cv2.CAP_MSMF]}
    for api in choices[backend]:
        cap=cv2.VideoCapture(int(source),api)
        if cap.isOpened(): return cap
        cap.release()
    raise RuntimeError('Kamera '+source+' gagal dibuka. Tutup aplikasi kamera lain, cek Camera Windows dan izin kamera. Coba --source 1 atau --backend msmf.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='0',help='Camera index or video path')
    parser.add_argument('--config',default='config.json')
    parser.add_argument('--output',default='results')
    parser.add_argument('--delay',type=float,default=5,help='Countdown seconds before calibration')
    parser.add_argument('--backend',choices=['auto','dshow','msmf'],default='auto')
    parser.add_argument('--model',choices=['full','heavy'],default='full',help='MediaPipe Full (1) or Heavy (2)')
    args=parser.parse_args()
    cfg=Config(**json.loads(Path(args.config).read_text()))
    engine=Engine(cfg)
    hand_warning=HandWarning()
    try:
        cap=open_capture(args.source,args.backend)
    except RuntimeError as exc:
        print(exc)
        return
    live=args.source.isdigit()
    fps=cap.get(cv2.CAP_PROP_FPS) or 30
    if not math.isfinite(fps) or fps<=0: fps=30
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S')+f'_{time.time_ns()%1000000000:09d}'
    archive=CaptureArchive(out,stamp,fps)
    model_complexity={'full':1,'heavy':2}[args.model]
    pose=mp.solutions.pose.Pose(model_complexity=model_complexity)
    print(f'Model: {args.model} (model_complexity={model_complexity})')
    mode='CAL_DUDUK'; samples=[]; seated=standing=None; filtered=None
    recording=False; deadline=None; ready_since=None; rows=[]; frame_index=0; origin=time.monotonic()
    sitting_samples=[]; camera_fail_since=None; diagnostic_rows=[]
    previous_t=None; previous_capture=None
    message='Tekan D, lalu kembali duduk sebelum hitung mundur selesai'
    try:
        while True:
            capture_start=time.perf_counter()
            ok,frame=cap.read()
            capture_end=time.perf_counter()
            if not ok:
                if not live:
                    print('Video selesai atau frame video tidak terbaca.')
                    break
                engine.missing(); filtered=None; ready_since=None; samples=[]
                hand_warning.reset()
                if recording:
                    collect_calibration(samples,t if frame_index else 0,None)
                if camera_fail_since is None:
                    camera_fail_since=time.monotonic()
                    print('Frame kamera gagal; mencoba ulang hingga 5 detik.')
                if time.monotonic()-camera_fail_since >=5:
                    print('Kamera tidak pulih setelah 5 detik. Hasil sesi disimpan.')
                    break
                if cv2.waitKey(50)&255 == ord('q'): break
                continue
            camera_fail_since=None
            t=time.monotonic()-origin if live else frame_index/fps
            frame_interval_ms=None if previous_capture is None else (capture_end-previous_capture)*1000
            previous_capture=capture_end
            if previous_t is not None and t-previous_t>MAX_SAMPLE_GAP:
                engine.missing(); filtered=None; ready_since=None; samples=[]
            previous_t=t
            frame_index+=1
            h,w=frame.shape[:2]
            archive.write_frame(frame,t,frame_index)
            pose_start=time.perf_counter()
            result=pose.process(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            pose_ms=(time.perf_counter()-pose_start)*1000
            quality=pose_quality(result)
            hand_data=dict(hand_raw=None,hand_stable=None,hand_context=False,hand_enabled=False)
            hand_active=None; hand_context=False
            hand_data.update(hand_stable=None,hand_context=False)
            frame_mode,frame_recording=mode,recording
            m=measure(result,w,h)
            if quality['accepted'] and m is None:
                quality['accepted']=False; quality['reason']='geometri_titik_tidak_valid'
            archive.write_features(result,m,t,frame_index,frame_mode,quality)
            if result.pose_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(frame,result.pose_landmarks,mp.solutions.pose.POSE_CONNECTIONS)
            if m:
                if filtered is None: filtered=m.copy()
                dt=t-filtered.get('_t',t-1/fps)
                alpha=1-math.exp(-max(dt,1e-3)/.12)
                for key in ('y','lean','hip','knee','thigh','ankle'):
                    filtered[key]+=alpha*(m[key]-filtered[key])
                filtered['_t']=t
                hand_active=None
                filtered['hand']=False
                hand_data.update(hand_stable=hand_active,hand_context=hand_context)
                if deadline is not None:
                    remaining=deadline-time.monotonic()
                    message=f'Kembali ke posisi {mode}: {max(0, math.ceil(remaining))} detik'
                    if remaining <= 0:
                        deadline=None; recording=True; samples=[]
                if recording:
                    done=collect_calibration(samples,t,filtered)
                    message=f'MEREKAM {mode}: diam {min(1,t-samples[0][0]):.1f}/1.0 detik'
                    if done:
                        recording=False
                        ys=[x[1]['y'] for x in samples]
                        if mode=='CAL_DUDUK':
                            sitting_samples=list(samples)
                            seated=float(np.median(ys))
                            engine.lean_base=float(np.mean([x[1]['lean'] for x in samples]))
                            engine.lean_sd=float(np.std([x[1]['lean'] for x in samples]))
                            mode='CAL_BERDIRI'; message='DUDUK TERSIMPAN. Tekan B, lalu berdiri saat timer'
                            print('Kalibrasi duduk tersimpan. Berikutnya tekan B.')
                        else:
                            standing=float(np.median(ys))
                            if seated-standing < h*.08:
                                message='Berdiri belum cukup tinggi; tetap berdiri, rekam ulang otomatis'; standing=None; recording=True
                            else:
                                try:
                                    engine.speed_baseline,engine.speed_sd,engine.rise_threshold=speed_stats(sitting_samples,seated-standing,cfg.speed_sd_multiplier,cfg.speed_window)
                                except ValueError as exc:
                                    print(exc); standing=None; mode='CAL_DUDUK'; message='Kalibrasi noise gagal; kembali duduk, rekam ulang otomatis'; recording=True; samples=[]; continue
                                print(f'Ambang bangkit: {engine.rise_threshold:.6f}; SD kecepatan: {engine.speed_sd:.6f}')
                                mode='KEMBALI'; message='BERDIRI TERSIMPAN. Kembali duduk; tunggu LATIHAN'
                                print('Kalibrasi berdiri tersimpan. Kembali duduk.')
                        samples=[]
                if mode=='KEMBALI':
                    p=(seated-filtered['y'])/(seated-standing)
                    if p<=cfg.seated_progress and filtered['hip']<120:
                        if ready_since is None: ready_since=t
                        if t-ready_since>=1:
                            mode='LATIHAN'; ready_since=None
                            print('LATIHAN dimulai; duduk diam sebentar sebelum bangkit.')
                    else:
                        ready_since=None
                if mode=='LATIHAN':
                    p=(seated-filtered['y'])/(seated-standing)
                    message=engine.update(t,p,filtered['lean'],filtered['hip'],filtered['knee'],filtered['thigh'],filtered['ankle'],filtered['hand'])
                    # A confirmed standing/return transition ends the warning
                    # on this frame, rather than leaving a stale visible alert.
                    if True:  # Hand assessment deferred by project decision.
                        hand_warning.reset(); hand_active=None; hand_context=False
                        filtered['hand']=False
                        hand_data.update(hand_stable=None,hand_context=False)
                    rows.append(dict(frame_index=frame_index,video_frame_index=archive.last_video_index,time=t,progress=p,state=engine.state,lean=filtered['lean'],hip=filtered['hip'],knee=filtered['knee'],thigh=filtered['thigh'],ankle=filtered['ankle'],hand=filtered['hand'],velocity=engine.velocity,**{('stand_'+k):(engine.standing_checks.get(k) if engine.state=='BANGKIT' else None) for k in ('height','hip','knee','speed')},**{'stand_'+key:engine.stability_details.get(key) for key in ('short_speed','window_speed','window_excursion','window_span','source')},**hand_data))
                cv2.putText(frame,f"Lean {filtered['lean']:.1f} | Hip {filtered['hip']:.1f} | Knee {filtered['knee']:.1f}",(15,65),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
            else:
                hand_warning.reset()
                filtered=None
                collect_calibration(samples,t,None); ready_since=None
                message=engine.missing()
                if recording:
                    message='Rekam ulang otomatis: '+quality['reason']
                elif deadline is not None:
                    message=f'Kalibrasi menunggu tubuh terlihat; timer {max(0,math.ceil(deadline-time.monotonic()))} detik'
            diagnostic_rows.append(dict(frame_index=frame_index,video_frame_index=archive.last_video_index,time=t,mode=frame_mode,recording=frame_recording,model=args.model,model_complexity=model_complexity,frame_interval_ms=frame_interval_ms,capture_ms=(capture_end-capture_start)*1000,pose_ms=pose_ms,**quality,**hand_data))
            hand_text='Bantuan tangan: tidak dinilai pada versi ini'
            for i,text in enumerate([f'v0.5.6 | {args.model} | {mode} / {engine.state}',message,f'Berdiri lengkap: {engine.complete} | Siklus terkonfirmasi: {engine.cycles}',engine.assessment_text(),hand_text,'D: duduk | B: berdiri | Mulai otomatis | R: reset | Q: simpan & keluar']):
                cv2.putText(frame,text,(15,30+i*35 if i==0 else 100+(i-1)*35),cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),2)
            panel=np.zeros((420,w,3),dtype=np.uint8)
            labels=['VISIBILITY KIRI - batas 0.65 (bukan persen akurasi)',
                    ' | '.join(name+': '+('--' if quality['visibility_'+name] is None else f"{quality['visibility_'+name]:.2f}") for name in ('bahu','pinggul','lutut','pergelangan_kaki')),
                    'Frame: '+('DITERIMA' if quality['accepted'] else 'DITOLAK')+' | '+quality['reason'],
                    f'Kalibrasi: {len(samples)} sampel | '+('rekam otomatis aktif' if recording else 'belum merekam'),
                    f'Bangkit teramati: {engine.rise_attempts} | Kembali duduk: {engine.returned_attempts}' if mode=='LATIHAN' else 'Mulai STS hanya setelah status LATIHAN.']
            labels.extend(display_lines(engine.results[-1] if engine.results else None,cfg))
            labels.append('Rekaman kamera: '+('aktif' if archive.error is None else 'GAGAL - lihat terminal'))
            for j,label in enumerate(labels):
                cv2.putText(panel,label,(10,25+j*32),cv2.FONT_HERSHEY_SIMPLEX,.43,(0,255,0) if quality['accepted'] else (0,200,255),1)
            cv2.imshow('STS Prototype',np.vstack((frame,panel)))
            key=cv2.waitKey(1 if live else max(1,int(1000/fps)))&255
            if key==ord('q'): break
            if key==ord('r') and rows:
                message='Sesi sudah berisi data. Tekan Q lalu buka ulang untuk sesi baru.'
                continue
            if key==ord('r'):
                engine=Engine(cfg); mode='CAL_DUDUK'; seated=standing=None; samples=[]; recording=False; deadline=None; ready_since=None; filtered=None; sitting_samples=[]
                hand_warning.reset()
                message='Duduk tegak, lalu tekan D'
            if not recording and deadline is None and ((key==ord('d') and mode=='CAL_DUDUK') or (key==ord('b') and mode=='CAL_BERDIRI')):
                deadline=time.monotonic()+max(0,args.delay); samples=[]
            if key==32 and mode=='KEMBALI' and m:
                p=(seated-m['y'])/(seated-standing)
                if p<=cfg.seated_progress and m['hip']<120: mode='LATIHAN'
                else: message='Kembali duduk dahulu'
    finally:
        if engine.state == 'BANGKIT':
            engine.observation_missing=True
            engine.finish(time.monotonic()-origin if live else frame_index/fps,False)
        archive.close()
        cap.release(); pose.close(); cv2.destroyAllWindows()
        out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
        (out/f'session_{stamp}.json').write_text(json.dumps({'version':'0.5.6','model':args.model,'model_complexity':model_complexity,'config':vars(cfg),'capture_archive':archive.metadata(),'assessment_reference':'Aturan operasional PDF; angka toleransi sementara di config','hand_warning':{'enabled':False,'status':'DITUNDA'},'calibration':{'lean_base':engine.lean_base,'lean_sd':engine.lean_sd,'seated_y':seated,'standing_y':standing,'speed_baseline':engine.speed_baseline,'speed_sd':engine.speed_sd,'rise_threshold':engine.rise_threshold},'attempts':engine.results,'complete':engine.complete,'cycles':engine.cycles,'rise_attempts':engine.rise_attempts,'returned_attempts':engine.returned_attempts,'unconfirmed_standing':sum(r['bangkit_lengkap'] is None for r in engine.results)},indent=2,default=json_scalar),encoding='utf-8')
        if diagnostic_rows:
            with (out/f'diagnostics_{stamp}.csv').open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(diagnostic_rows[0]))
                writer.writeheader(); writer.writerows(diagnostic_rows)
            print('CSV diagnostik tersimpan: '+str(out/f'diagnostics_{stamp}.csv'))
        if not rows:
            print('CSV tidak dibuat: belum ada data LATIHAN. Pastikan kalibrasi selesai dan status LATIHAN muncul.')
        if rows:
            with (out/f'angles_{stamp}.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

if __name__=='__main__': main()
