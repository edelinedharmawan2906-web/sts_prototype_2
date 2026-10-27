"""Explicit assumed rules for technical learning; not clinical criteria."""
import statistics
from pydantic import BaseModel, ConfigDict, Field
from signals import MAX_SAMPLE_GAP

class PersonalRules(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    calibration_seconds: float = Field(2,ge=1,le=10)
    calibration_min_samples: int = Field(20,ge=9,le=300)
    calibration_max_y_range: float = Field(.03,gt=0,le=.1)
    calibration_max_angle_range: float = Field(10,gt=0,le=30)
    calibration_max_ankle_range: float = Field(.10,gt=0,le=.5)
    calibration_min_rise: float = Field(.08,gt=0,le=.5)
    calibration_min_extension: float = Field(10,gt=0,le=60)
    sitting_angle_tolerance: float = Field(10,gt=0,le=45)
    sitting_ankle_tolerance: float = Field(.10,gt=0,le=.5)
    sitting_capture_angle_range: float = Field(10,gt=0,le=45)
    sitting_capture_ankle_range: float = Field(.10,gt=0,le=.5)
    seated_anchor_tolerance: float = Field(20,gt=0,le=45)
    standing_angle_tolerance: float = Field(10,gt=0,le=45)
    lean_addition: float = Field(10,gt=0,le=45)
    preparation_lean_delta: float = Field(5,gt=0,le=20)
    min_rise_speed: float = Field(.01,gt=0,le=.5)
    stand_progress: float = Field(.9,gt=.5,le=1)
    seated_progress: float = Field(.2,ge=0,lt=.5)
    stable_speed: float = Field(.08,gt=0,le=.5)
    hold_seconds: float = Field(.3,ge=.1,le=3)

    @classmethod
    def load(cls,path):
        rules=cls.model_validate_json(path.read_text())
        if rules.preparation_lean_delta>=rules.lean_addition:
            raise ValueError('preparation_lean_delta harus lebih kecil dari lean_addition')
        return rules


def collect_personal(samples,t,m,height,rules):
    """Keep a bounded contiguous window; unstable windows roll until stable."""
    if samples and (t<=samples[-1][0] or t-samples[-1][0]>MAX_SAMPLE_GAP): samples.clear()
    samples.append((t,m.copy()))
    while samples and t-samples[0][0]>rules.calibration_seconds+MAX_SAMPLE_GAP:
        samples.pop(0)
    if len(samples)<rules.calibration_min_samples or t-samples[0][0]<rules.calibration_seconds-1e-9:
        return False,'Mengumpulkan sampel posisi'
    for key in ('y','hip','knee','lean','thigh','ankle'):
        values=[v[key] for _,v in samples]
        limit=(height*rules.calibration_max_y_range if key=='y' else rules.calibration_max_ankle_range if key=='ankle' else rules.calibration_max_angle_range)
        if max(values)-min(values)>limit:
            return False,'Posisi berubah; tahan diam untuk mengulang jendela kalibrasi'
    return True,'Posisi stabil'


def summarize(samples):
    keys=('y','hip','knee','lean','thigh','ankle')
    return dict(median={k:float(statistics.median(m[k] for _,m in samples)) for k in keys},
                sd={k:float(statistics.pstdev(m[k] for _,m in samples)) for k in keys},
                sample_count=len(samples),seconds=samples[-1][0]-samples[0][0])
