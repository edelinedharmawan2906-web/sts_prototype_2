import math

NAMES={11:'bahu',23:'pinggul',25:'lutut',27:'pergelangan_kaki'}

def pose_quality(result,threshold=.65):
    if not result.pose_landmarks:
        return {'accepted':False,'reason':'pose_tidak_terdeteksi',**{'visibility_'+name:None for name in NAMES.values()}}
    lm=result.pose_landmarks.landmark
    values={'visibility_'+name:float(lm[i].visibility) for i,name in NAMES.items()}
    low=[name for name in NAMES.values() if not math.isfinite(values['visibility_'+name]) or values['visibility_'+name]<threshold]
    return {'accepted':not low,'reason':'visibility_rendah:'+','.join(low) if low else 'ok',**values}
