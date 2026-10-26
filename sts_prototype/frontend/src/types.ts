export type Landmark = {x:number;y:number;z:number;visibility:number};
export type Criterion = {nilai?:number|null;target?:string;memenuhi?:boolean|null;acuan?:number;toleransi?:number;selisih?:number|null};
export type Attempt = {
  status_sts?:string;durasi?:number;alasan?:string[];bangkit_lengkap?:boolean|null;
  bantuan_tangan_dinilai?:boolean;
  penilaian_tahap?: {
    rule_set?:string;acuan?:string;
    duduk?:{memenuhi?:boolean|null;pengukuran?:Record<string,Criterion>};
    condong?:{memenuhi?:boolean|null;puncak_teramati?:number;minimum?:number;acuan?:number;tambahan_teramati?:number;minimum_tambahan?:number};
    berdiri?:{memenuhi?:boolean|null;pengukuran_saat_keputusan?:{progress?:number;hip?:number;knee?:number};acuan_hip?:number;acuan_knee?:number;target_hip?:number;target_knee?:number;target_progress?:number;hold_seconds?:number;selisih_hip?:number|null;selisih_knee?:number|null};
    bantuan_tangan?:{dinilai?:boolean;status?:string};
  };
};
export type Reference={median:Record<string,number>;sd:Record<string,number>;sample_count:number;seconds:number};
export type State = {
  assessment_mode?:string;rules?:Record<string,number>;personal_calibration?:{duduk:Reference|null;berdiri:Reference|null};
  session_id?:string; mode:string;phase:string;message:string;
  complete:number;cycles:number;closed:boolean;calibrated:boolean;
  calibration_samples:number;
  measurement:null|{y:number;hip:number;knee:number;lean:number;thigh:number;ankle:number};
  capture:null|{posture:string;remaining_seconds:number;recording:boolean};
  quality:{accepted:boolean;reason:string};frame_interval:number|null;
  attempts: Attempt[];
};

export type HistoryItem={id:string;saved_at:string;input_source:string;complete:number;cycles:number;attempt_count:number};
export type SavedData={complete:number;cycles:number;input_source:string;attempts:State['attempts'];frames:unknown[]};
export type HistoryRecord={id:string;saved_at:string;data:SavedData};
export type HistoryPage={items:HistoryItem[];total:number;limit:number;offset:number};
