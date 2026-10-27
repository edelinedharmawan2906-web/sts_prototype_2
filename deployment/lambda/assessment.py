"""Operational PDF checks; these reports do not set or fit thresholds."""
def check(value, target, passed):
    return dict(nilai=value, target=target, memenuhi=passed)


def stage_report(sit, sit_ok, peak, standing, missing, end, cfg):
    tol=cfg.sitting_tolerance
    sitting={}
    for key, target, predicate in (
        ('hip',f'90 +/- {tol:g} derajat',lambda x:abs(x-90)<=tol),
        ('lean',f'<= {tol:g} derajat',lambda x:x<=tol),
        ('thigh',f'<= {tol:g} derajat',lambda x:x<=tol),
        ('ankle','<= 0.15 panjang torso',lambda x:x<=.15)):
        value=sit.get(key)
        sitting[key]=check(value,target,None if value is None else bool(predicate(value)))
    return dict(
        duduk=dict(memenuhi=sit_ok,pengukuran=sitting,ringkasan='Median posisi awal sebelum bangkit'),
        condong=dict(memenuhi=None if missing else bool(peak>=cfg.lean_min),
            puncak_teramati=peak,minimum=cfg.lean_min,
            catatan='Puncak sinyal tersaring selama persiapan; celah data membuat penilaian tidak pasti'),
        berdiri=dict(memenuhi=standing,pengukuran_saat_keputusan=dict(end),
            target_progress=cfg.stand_progress,target_hip=180-cfg.straight_tolerance,
            target_knee=180-cfg.straight_tolerance,hold_seconds=cfg.hold_seconds,
            stable_speed=cfg.stable_speed),
        bantuan_tangan=dict(dinilai=False,status='DITUNDA'))


def display_lines(result,cfg):
    if not result:return ['Rincian tahap muncul setelah percobaan selesai.']
    report=result['penilaian_tahap']
    labels={'hip':'Badan-paha','lean':'Badan-vertikal','thigh':'Paha-horizontal','ankle':'Kaki/torso'}
    rows=[]
    for name,c in report['duduk']['pengukuran'].items():
        value='?' if c['nilai'] is None else f"{c['nilai']:.1f}" if name!='ankle' else f"{c['nilai']:.3f}"
        status='?' if c['memenuhi'] is None else 'OK' if c['memenuhi'] else 'BELUM'
        rows.append(f"Duduk {labels[name]}: {value} | {c['target']} | {status}")
    rows.append(f"Condong puncak: {result['kemiringan_puncak']:.1f} | target >= {cfg.lean_min:g} derajat")
    rows.append(f"Berdiri: {result['status_berdiri']} | tinggi >= {cfg.stand_progress*100:g}% | sudut >= {180-cfg.straight_tolerance:g}")
    return rows
