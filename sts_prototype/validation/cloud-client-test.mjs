// src/sts-client.ts
var StsClient = class {
  constructor(base = "") {
    this.base = base;
  }
  sessionId = "";
  queue = Promise.resolve();
  request(path, method = "GET", body) {
    const operation = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1e4);
      try {
        const r = await fetch(this.base + path, {
          method,
          signal: controller.signal,
          headers: { "Content-Type": "application/json" },
          body: body === void 0 ? void 0 : JSON.stringify(body)
        });
        if (!r.ok) {
          const text = await r.text();
          throw Error(`Backend ${r.status}: ${text}`);
        }
        return await r.json();
      } finally {
        clearTimeout(timeout);
      }
    };
    const next = this.queue.then(operation, operation);
    this.queue = next.catch(() => {
    });
    return next;
  }
  async create(width, height) {
    const r = await this.request("/sessions", "POST", { width, height, input_source: "browser_camera" });
    this.sessionId = r.session_id;
    return r;
  }
  calibrate(posture, delay = 10) {
    return this.request(`/sessions/${this.sessionId}/calibration`, "POST", { posture, delay });
  }
  frame(t, landmarks) {
    return this.request(`/sessions/${this.sessionId}/frames`, "POST", { t, landmarks });
  }
  finish() {
    return this.request(`/sessions/${this.sessionId}/finish`, "POST");
  }
  export() {
    return this.request(`/sessions/${this.sessionId}/export`);
  }
  history(offset = 0) {
    return this.request(`/history?limit=50&offset=${offset}`);
  }
  detail(id) {
    return this.request(`/history/${encodeURIComponent(id)}`);
  }
  health() {
    return this.request("/health");
  }
};

// public/sts-cloud-auth.mjs
var config = Object.freeze({
  domain: "https://ap-southeast-2k2qaxxosn.auth.ap-southeast-2.amazoncognito.com",
  clientId: "1o3uv31tupfo8lhn1tcl776u9f",
  redirectUri: "http://localhost:8000/camera/",
  apiUrl: "https://lxjml9oo40.execute-api.ap-southeast-2.amazonaws.com/sts"
});
var tokenKey = "sts.cloud.access.v1";
var lifetime = 10 * 60 * 1e3;
function accessToken(storage, now = Date.now()) {
  try {
    const saved = JSON.parse(storage.getItem(tokenKey));
    if (typeof saved?.accessToken === "string" && saved.expiresAt > now + 3e4) {
      return saved.accessToken;
    }
  } catch {
  }
  storage.removeItem(tokenKey);
  return null;
}

// src/cloud-client.ts
var wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
var CloudStsClient = class extends StsClient {
  current = null;
  frames = [];
  serial = Promise.resolve();
  flushing = null;
  timer = null;
  fatal = null;
  pending = null;
  dimensions = { width: 640, height: 480 };
  onState = null;
  async post(command) {
    const text = JSON.stringify(command);
    for (let attempt = 0; attempt < 3; attempt++) {
      const token = accessToken(sessionStorage);
      if (!token) throw Error("Login AWS sudah habis. Jangan hapus login saat sesi berjalan.");
      try {
        const r = await fetch(config.apiUrl, {
          method: "POST",
          credentials: "omit",
          cache: "no-store",
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: text,
          signal: AbortSignal.timeout(25e3)
        });
        if (r.status >= 500 || r.status === 429) {
          if (attempt < 2) {
            await wait(500 * (attempt + 1));
            continue;
          }
        }
        if (!r.ok) {
          const message = r.status === 409 ? "Konflik versi sesi. Jangan buka dua kamera untuk sesi yang sama." : r.status === 401 ? "Token ditolak. Login AWS perlu diperbarui." : `API cloud HTTP ${r.status}. Periksa CloudWatch/CORS dan simpan ID sesi.`;
          throw Object.assign(Error(message), { terminal: true });
        }
        const data = await r.json();
        if (data.status !== "ok") throw Object.assign(Error("Respons cloud gagal"), { terminal: true });
        return data;
      } catch (e) {
        if (e?.terminal || attempt === 2) throw e;
        await wait(500 * (attempt + 1));
      }
    }
    throw Error("Tidak ada respons cloud");
  }
  enqueue(work) {
    const next = this.serial.then(work);
    this.serial = next.catch(() => {
    });
    return next;
  }
  mutation(action, payload) {
    return this.enqueue(async () => {
      if (this.pending) throw Error("Ada permintaan yang belum terkonfirmasi. Akhiri & simpan untuk mencoba ulang.");
      const command = {
        action,
        session_id: this.sessionId,
        request_id: crypto.randomUUID(),
        expected_version: this.current.version,
        payload
      };
      this.pending = command;
      const data = await this.post(command);
      this.current = data.result;
      this.pending = null;
      return this.current;
    });
  }
  schedule() {
    if (this.timer || this.fatal) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.flush().catch((e) => {
        this.fatal = e instanceof Error ? e : Error(String(e));
      });
    }, 600);
  }
  flush() {
    if (this.flushing) return this.flushing;
    if (!this.frames.length) return Promise.resolve();
    if (this.fatal) return Promise.reject(this.fatal);
    const batch = this.frames.slice(0, 30), started = performance.now();
    this.flushing = this.mutation("frames", batch).then((state) => {
      this.frames.splice(0, batch.length);
      this.onState?.(state, batch[batch.length - 1].t, performance.now() - started);
    }).catch((e) => {
      this.fatal = e instanceof Error ? e : Error(String(e));
      throw this.fatal;
    }).finally(() => {
      this.flushing = null;
      if (this.frames.length && !this.fatal) this.schedule();
    });
    return this.flushing;
  }
  async health() {
    const r = await this.post({ action: "health" });
    if (r.mode !== "authenticated_http") throw Error("Lambda v04 diperlukan");
    return { status: r.status };
  }
  async create(width, height) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.frames = [];
    this.fatal = null;
    this.pending = null;
    const data = await this.post({
      action: "create",
      request_id: crypto.randomUUID(),
      payload: { width, height, input_source: "browser_camera" }
    });
    this.dimensions = { width, height };
    this.current = data.result;
    this.sessionId = this.current.session_id;
    sessionStorage.setItem("sts.cloud.lastSession", this.sessionId);
    return this.current;
  }
  async frame(t, landmarks) {
    if (this.fatal) throw this.fatal;
    if (this.frames.length >= 120) {
      this.fatal = Error("Cloud tertinggal lebih dari 120 frame. Akhiri & simpan; jangan lanjut bergerak.");
      throw this.fatal;
    }
    this.frames.push({ t, landmarks });
    this.schedule();
    return this.current;
  }
  async calibrate(posture, delay = 10) {
    const boundary = this.frames.at(-1)?.t;
    while (boundary !== void 0 && this.frames.length && this.frames[0].t <= boundary) await this.flush();
    if (this.fatal) throw this.fatal;
    return this.mutation("calibration", { posture, delay });
  }
  async finish() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    await this.serial;
    if (this.pending) {
      const pending = this.pending;
      const data = await this.post(pending);
      this.current = data.result;
      this.pending = null;
      if (pending.action === "frames") this.frames.splice(0, pending.payload.length);
    }
    this.fatal = null;
    while (this.frames.length) await this.flush();
    if (this.current?.closed) return this.current;
    return this.mutation("finish", {});
  }
  async export() {
    await this.serial;
    const state = (await this.post({ action: "status", session_id: this.sessionId })).result;
    const history = (await this.post({ action: "history", session_id: this.sessionId })).result;
    return {
      version: "camera-cloud-v01",
      session_id: this.sessionId,
      cloud_version: state.version,
      storage: "DynamoDB",
      transport: "HTTPS API Gateway + Cognito",
      source: "Python personal_dummy_v1",
      input_source: "browser_camera",
      angle_source: "geometry_2d",
      dimensions: this.dimensions,
      personal_rules: state.rules,
      personal_calibration: state.personal_calibration,
      complete: state.complete,
      cycles: state.cycles,
      attempts: state.attempts,
      closed: state.closed,
      batches: history.batches,
      frames: history.batches.flatMap((b) => b.frames)
    };
  }
};
export {
  CloudStsClient
};
