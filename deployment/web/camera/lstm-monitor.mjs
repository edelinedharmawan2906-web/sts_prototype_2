export function monitorLstmValues(result) {
  const format=value=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(1)+'°':'—';
  const ready=result?.status==='ready';
  const labels={ready:'Prediksi LSTM tersedia',disabled:'LSTM belum diaktifkan di backend',
    warming_up:'Mengumpulkan gerakan sekitar 1 detik',pose_missing:'Titik tubuh hilang; menunggu input baru',
    frame_gap:'Jeda frame terlalu besar; mengumpulkan ulang',inference_error:'LSTM belum tersedia; periksa backend'};
  return {
    'lstm-status':labels[result?.status]||'Sesi ini belum memiliki hasil LSTM',
    'geo-left':format(ready?result.geometry_knee_flexion_deg?.left:null),
    'geo-right':format(ready?result.geometry_knee_flexion_deg?.right:null),
    'lstm-left':format(ready?result.knee_flexion_deg?.left:null),
    'lstm-right':format(ready?result.knee_flexion_deg?.right:null),
  };
}
