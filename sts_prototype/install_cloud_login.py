"""Run in project root. Adds cloud login while preserving existing camera assets."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
TAG = '<script type="module" src="/camera/sts-cloud-login.mjs"></script>'

def install(root=ROOT):
    dist = root / 'frontend' / 'dist'
    public = root / 'frontend' / 'public'
    required = [root/'api.py', dist/'index.html', public/'sts-cloud-auth.mjs', public/'sts-cloud-login.mjs']
    for path in required:
        if not path.is_file():
            raise SystemExit('File tidak ditemukan: ' + str(path) + '\nLetakkan isi paket di folder proyek yang memiliki api.py dan frontend/dist/index.html.')
    indexes = [dist/'index.html', root/'frontend'/'index.html']
    for path in indexes:
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        if TAG not in text:
            if '</body>' not in text:
                raise SystemExit('HTML tidak dikenali: ' + str(path))
            backup = path.with_name('index.before-cloud-login.html')
            if not backup.exists():
                shutil.copy2(path, backup)
            path.write_text(text.replace('</body>', TAG+'</body>', 1),encoding='utf-8')
    for name in ['sts-cloud-auth.mjs','sts-cloud-login.mjs']:
        shutil.copy2(public/name, dist/name)
    print('Berhasil memasang panel Login AWS. Buka http://localhost:8000/camera/ lalu Ctrl+F5.')

if __name__ == '__main__':
    install()
