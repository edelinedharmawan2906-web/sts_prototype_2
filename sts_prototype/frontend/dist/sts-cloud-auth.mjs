// Public application settings. No client secret or AWS credentials.
export const config = Object.freeze({
  domain: 'https://ap-southeast-2k2qaxxosn.auth.ap-southeast-2.amazoncognito.com',
  clientId: '1o3uv31tupfo8lhn1tcl776u9f',
  redirectUri: 'http://localhost:8000/camera/',
  apiUrl: 'https://lxjml9oo40.execute-api.ap-southeast-2.amazonaws.com/sts'
});
const pendingKey = 'sts.cloud.pkce.v1';
const tokenKey = 'sts.cloud.access.v1';
const lifetime = 10 * 60 * 1000;
const encode = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const random = () => encode(crypto.getRandomValues(new Uint8Array(32)));

export async function challenge(verifier) {
  return encode(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
}

function requireLocation(location) {
  if (location.origin + location.pathname !== config.redirectUri) {
    throw new Error('Untuk tes login, buka http://localhost:8000/camera/ di laptop.');
  }
}

export async function loginUrl(storage, location, now = Date.now()) {
  requireLocation(location);
  const verifier = random(), state = random();
  const url = new URL('/oauth2/authorize', config.domain);
  url.search = new URLSearchParams({
    response_type:'code', client_id:config.clientId, redirect_uri:config.redirectUri,
    scope:'openid email', state, code_challenge_method:'S256',
    code_challenge:await challenge(verifier), prompt:'login'
  }).toString();
  storage.removeItem(tokenKey);
  storage.setItem(pendingKey, JSON.stringify({verifier, state, createdAt:now}));
  return url.href;
}

export function accessToken(storage, now = Date.now()) {
  try {
    const saved = JSON.parse(storage.getItem(tokenKey));
    if (typeof saved?.accessToken === 'string' && saved.expiresAt > now + 30000) {
      return saved.accessToken;
    }
  } catch { /* Missing or expired tab session. */ }
  storage.removeItem(tokenKey);
  return null;
}

export function clearLogin(storage) {
  storage.removeItem(tokenKey); storage.removeItem(pendingKey);
}

export async function callback(storage, location, history, fetcher = fetch, now = Date.now()) {
  const url = new URL(location.href);
  if (!url.searchParams.has('code') && !url.searchParams.has('error')) return false;
  const code = url.searchParams.get('code'), state = url.searchParams.get('state');
  const duplicate = ['code','state','error'].some(key => url.searchParams.getAll(key).length > 1);
  const failed = url.searchParams.has('error');
  // Scrub codes/errors immediately, before any asynchronous request.
  for (const key of ['code','state','error','error_description','error_uri']) url.searchParams.delete(key);
  history.replaceState(null, '', url.pathname + url.search + url.hash);
  let pending;
  try { pending = JSON.parse(storage.getItem(pendingKey)); } catch { pending = null; }
  clearLogin(storage); // Consume state/verifier once, including on rejection.
  requireLocation(location);
  if (duplicate || !pending || pending.state !== state
      || typeof pending.verifier !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(pending.verifier)
      || !Number.isFinite(pending.createdAt) || now < pending.createdAt || now - pending.createdAt > lifetime) {
    throw new Error('Sesi login tidak cocok atau kedaluwarsa. Klik Login AWS dari tab ini lagi.');
  }
  if (failed || !code) throw new Error('Login dibatalkan atau ditolak. Klik Login AWS untuk mencoba lagi.');
  const response = await fetcher(new URL('/oauth2/token', config.domain), {
    method:'POST', credentials:'omit', cache:'no-store', referrerPolicy:'no-referrer',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({grant_type:'authorization_code', client_id:config.clientId,
      redirect_uri:config.redirectUri, code, code_verifier:pending.verifier}),
    signal:AbortSignal.timeout(20000)
  });
  if (!response.ok) throw new Error(`Pertukaran token gagal (HTTP ${response.status}). Periksa callback URL dan Authorization code grant di Cognito, lalu login lagi.`);
  const result = await response.json();
  if (result.token_type?.toLowerCase() !== 'bearer' || typeof result.access_token !== 'string'
      || !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(result.access_token)
      || !Number.isFinite(result.expires_in) || result.expires_in <= 0 || result.expires_in > 86400) {
    throw new Error('Respons token tidak sesuai. Coba login kembali.');
  }
  // Only keep access token in this tab. Discard ID and refresh tokens.
  storage.setItem(tokenKey, JSON.stringify({accessToken:result.access_token,
    expiresAt:now + result.expires_in * 1000}));
  return true;
}

export async function testApi(storage, fetcher = fetch) {
  const token = accessToken(storage);
  if (!token) throw new Error('Belum login atau sesi login sudah habis. Klik Login AWS.');
  const response = await fetcher(config.apiUrl, {
    method:'POST', credentials:'omit', cache:'no-store', referrerPolicy:'no-referrer',
    headers:{'Content-Type':'application/json', Authorization:'Bearer ' + token},
    body:JSON.stringify({action:'health'}), signal:AbortSignal.timeout(25000)
  });
  if (response.status === 401) {
    clearLogin(storage);
    throw new Error('API menolak token (401). Login lagi; jika tetap gagal, periksa issuer dan audience authorizer.');
  }
  if (response.status === 403) throw new Error('Akses ditolak (403). Periksa scope openid pada route API dan app client.');
  if (!response.ok) throw new Error(`API merespons HTTP ${response.status}. Periksa integrasi Lambda dan CloudWatch.`);
  const result = await response.json();
  if (result.status !== 'ok' || result.mode !== 'authenticated_http') {
    throw new Error('Respons API belum sesuai. Pastikan Lambda memakai STS_Lambda_v04.zip.');
  }
  return result;
}
