import {loginUrl, callback, accessToken, clearLogin, testApi} from './sts-cloud-auth.mjs';

const panel = document.createElement('section');
panel.id = 'sts-cloud-login-panel';
panel.setAttribute('aria-label','Login dan pengujian AWS');
panel.innerHTML = `<style>
#sts-cloud-login-panel{box-sizing:border-box;max-width:1100px;margin:16px auto;padding:18px;border:1px solid #bad5d0;border-radius:14px;background:#f0faf7;color:#183c35;font:15px/1.5 system-ui,sans-serif}
#sts-cloud-login-panel h2{font-size:19px;margin:0 0 6px}
#sts-cloud-login-panel p{margin:6px 0 12px}
#sts-cloud-login-panel button{padding:10px 15px;margin:0 8px 8px 0;border:1px solid #12695f;border-radius:8px;background:white;color:#12695f;font:inherit;cursor:pointer}
#sts-cloud-login-panel button:first-of-type{background:#12695f;color:white}
#sts-cloud-login-panel button:disabled{opacity:.5;cursor:wait}
#sts-cloud-login-panel output{display:block;white-space:pre-wrap;overflow-wrap:anywhere}
#sts-cloud-login-panel [data-error=true]{color:#a22424}
@media(max-width:700px){#sts-cloud-login-panel{margin:10px}}
</style><h2>Login AWS · Uji koneksi cloud</h2>
<p>Masuk untuk menguji akses API. Pilih mode kamera cloud di bawah untuk memakai Lambda dan DynamoDB.</p>
<button type="button" data-action="login">Login AWS</button>
<button type="button" data-action="test">Uji API cloud</button>
<button type="button" data-action="clear">Hapus login tab</button>
<output aria-live="polite">Memeriksa sesi login…</output>`;
document.body.prepend(panel);
const output = panel.querySelector('output');
const buttons = [...panel.querySelectorAll('button')];
const message = (text, error = false) => { output.textContent=text; output.dataset.error=String(error); };
const busy = value => buttons.forEach(button => button.disabled=value);
function showError(error) {
  if (error instanceof TypeError) message('Koneksi browser gagal. Periksa internet dan CORS API: origin http://localhost:8000, method POST/OPTIONS, header authorization/content-type.',true);
  else if (['TimeoutError','AbortError'].includes(error?.name)) message('Permintaan terlalu lama. Periksa internet lalu coba lagi.',true);
  else message(error?.message || 'Permintaan gagal. Coba lagi.',true);
}
panel.addEventListener('click', async event => {
  const action = event.target?.dataset?.action;
  if (!action) return;
  busy(true);
  try {
    if (action === 'login') {
      message('Membuka halaman login Cognito…');
      window.location.assign(await loginUrl(sessionStorage, window.location));
    } else if (action === 'test') {
      message('Menghubungi API cloud…');
      await testApi(sessionStorage);
      message('BERHASIL — HTTP 200\nLogin Cognito → API Gateway → Lambda sudah terhubung.\nTes ini belum memeriksa analisis gerak atau penyimpanan sesi kamera.');
    } else {
      clearLogin(sessionStorage);
      message('Login di tab ini sudah dihapus. Untuk tes ulang, klik Login AWS.');
    }
  } catch (error) { showError(error); }
  finally { busy(false); }
});
busy(true);
try {
  await callback(sessionStorage, window.location, window.history);
  message(accessToken(sessionStorage) ? 'Login tersedia. Klik Uji API cloud.' : 'Belum login. Klik Login AWS.');
} catch (error) { showError(error); }
finally { busy(false); }
