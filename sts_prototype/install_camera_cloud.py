"""Install camera cloud frontend while preserving backend and MediaPipe assets."""
from pathlib import Path
from datetime import datetime, timezone
import shutil

def install(root=None):
    root=Path(root) if root else Path(__file__).resolve().parent
    payload=root/'camera_cloud_payload'
    checks=[root/'api.py',root/'frontend/dist/index.html',
            root/'frontend/dist/mediapipe/pose_landmarker_full.task',
            root/'frontend/dist/mediapipe/wasm/vision_wasm_internal.wasm',
            payload/'frontend/dist/index.html']
    for path in checks:
        if not path.is_file():
            raise SystemExit('File tidak ditemukan: '+str(path)+'\nLetakkan installer dan camera_cloud_payload di folder proyek kamera yang sudah berjalan.')
    files=sorted(p for p in payload.rglob('*') if p.is_file())
    backup=root/'camera_cloud_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    replaced=[]
    for src in files:
        relative=src.relative_to(payload);dest=root/relative
        if dest.is_file() and dest.read_bytes()==src.read_bytes():continue
        if dest.is_file():
            old=backup/relative;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,old)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);replaced.append(str(relative))
    print('Kamera cloud terpasang. File diperbarui:',len(replaced))
    if backup.exists():print('Cadangan file lama:',backup)
    print('Buka http://localhost:8000/camera/ lalu Ctrl+F5, login AWS, dan pilih Gunakan kamera cloud.')

if __name__=='__main__':install()
