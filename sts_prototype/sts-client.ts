// Copy into existing React project. Use Vite proxy /ta-api -> http://127.0.0.1:8000.
export class StsClient {
  constructor(private base = '/ta-api') {}
  sessionId = '';
  private async request(path: string, method = 'GET', body?: unknown) {
    const response = await fetch(this.base + path, {
      method, headers: {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  async create(width: number, height: number) {
    const result = await this.request('/sessions', 'POST', {width, height});
    this.sessionId = result.session_id;
    return result;
  }
  calibrate(posture: 'duduk' | 'berdiri', delay = 10) {
    return this.request(`/sessions/${this.sessionId}/calibration`, 'POST', {posture, delay});
  }
  // t is seconds since session start. Keep video dimensions fixed during a session.
  // await this call before sending next frame; do not queue concurrent frames.
  frame(t: number, landmarks: {x:number;y:number;z:number;visibility:number}[] | null) {
    return this.request(`/sessions/${this.sessionId}/frames`, 'POST', {t, landmarks});
  }
  finish() { return this.request(`/sessions/${this.sessionId}/finish`, 'POST'); }
  export() { return this.request(`/sessions/${this.sessionId}/export`); }
}
