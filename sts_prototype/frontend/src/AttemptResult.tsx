import type {Attempt} from './types';
const names:Record<string,string>={hip:'Sudut badan–paha saat duduk',lean:'Kemiringan badan saat duduk',thigh:'Kemiringan paha saat duduk',ankle:'Posisi kaki awal'};
const status=(value:boolean|null|undefined)=>value===true?'Memenuhi aturan':value===false?'Belum memenuhi aturan':'Belum dapat dinilai';
function valueText(key:string,value:number|null|undefined){
  if(typeof value!=='number'||!Number.isFinite(value))return 'Tidak tersedia';
  return key==='ankle'?`${(value*100).toFixed(1)}% panjang torso`:`${value.toFixed(1)}°`;
}
export function AttemptResult({attempt:a,title='Percobaan terakhir'}:{attempt:Attempt;title?:string}){
  const personal=a.penilaian_tahap?.rule_set==='personal_dummy_v1';
  const standingReport=a.penilaian_tahap?.berdiri;
  const sitting=a.penilaian_tahap?.duduk;
  const leaning=a.penilaian_tahap?.condong;
  const checks=Object.entries(sitting?.pengukuran??{});
  const failures=checks.filter(([,c])=>c.memenuhi===false);
  const standing=a.bangkit_lengkap===true?(personal?'Acuan berdiri pribadi tercapai':'Berdiri lengkap'):a.bangkit_lengkap===false?(personal?'Acuan berdiri pribadi belum tercapai':'Berdiri lengkap belum tercapai'):'Berdiri belum dapat dikonfirmasi';
  return <section className="attempt-result" aria-label={title}>
    <h3>{title}</h3>
    <p className={'standing-result '+(a.bangkit_lengkap===true?'confirmed':'')}><strong>{standing}</strong></p>
    {typeof a.durasi==='number'&&<p>Durasi percobaan bangkit: {a.durasi.toFixed(2)} detik.</p>}
    <h4>{personal?'Pemeriksaan terhadap acuan pribadi':'Pemeriksaan postur — aturan versi lama'}</h4>
    {a.penilaian_tahap?<>
      <p><strong>Duduk awal:</strong> {status(sitting?.memenuhi)}.</p>
      {failures.length>0&&<ul>{failures.map(([key])=><li key={key}>{key==='ankle'?(personal?'Posisi kaki awal berbeda dari acuan pribadi melebihi toleransi.':'Posisi kaki awal melewati batas prototipe.'):`${names[key]??key} belum memenuhi aturan.`}</li>)}</ul>}
      <p><strong>{personal?'Kemiringan selama persiapan dan bangkit:':'Condong saat persiapan:'}</strong> {status(leaning?.memenuhi)}.
        {personal&&typeof leaning?.tambahan_teramati==='number'&&<> Tambahan {leaning.tambahan_teramati.toFixed(1)}° dari acuan {leaning.acuan?.toFixed(1)}°; target tambahan ≥{leaning.minimum_tambahan}°.</>}
        {!personal&&typeof leaning?.puncak_teramati==='number'&&typeof leaning.minimum==='number'&&<> Puncak teramati {leaning.puncak_teramati.toFixed(1)}°; minimum aturan {leaning.minimum}°.</>}
      </p>
      {checks.length>0&&<details><summary>Lihat nilai dan batas posisi duduk</summary><dl className="posture-values">{checks.map(([key,c])=><div key={key}><dt>{names[key]??key}</dt><dd>{valueText(key,c.nilai)}<br/><small>Batas: {key==='ankle'&&typeof c.acuan==='number'&&typeof c.toleransi==='number'?`${(c.acuan*100).toFixed(1)}% ± ${(c.toleransi*100).toFixed(1)}% panjang torso`:c.target??'Tidak tersedia'} · {status(c.memenuhi)}{typeof c.selisih==='number'&&<> · Selisih {valueText(key,c.selisih)}</>}</small></dd></div>)}</dl></details>}
    </>:<p>Rincian postur tidak tersedia untuk sesi ini. {a.alasan?.join('; ')}</p>}
    {personal&&standingReport&&<details><summary>Lihat acuan dan syarat berdiri</summary><p>Lutut: {standingReport.pengukuran_saat_keputusan?.knee?.toFixed(1)??'—'}°; acuan {standingReport.acuan_knee?.toFixed(1)}°; minimal {standingReport.target_knee?.toFixed(1)}°.</p><p>Badan–paha: {standingReport.pengukuran_saat_keputusan?.hip?.toFixed(1)??'—'}°; acuan {standingReport.acuan_hip?.toFixed(1)}°; minimal {standingReport.target_hip?.toFixed(1)}°.</p><p>Kenaikan pinggul minimal {((standingReport.target_progress??0)*100).toFixed(0)}% dari rentang kalibrasi; stabil {standingReport.hold_seconds} detik.</p></details>}
    <p className="assessment-note">{a.bantuan_tangan_dinilai===true?'Bantuan tangan: lihat rincian ekspor.':'Bantuan tangan tidak dinilai.'} {personal?'Angka asumsi teknis untuk belajar IIPP, bukan standar klinis.':'Aturan prototipe versi lama.'} Hasil postur ditampilkan terpisah dari keberhasilan berdiri.</p>
  </section>;
}
