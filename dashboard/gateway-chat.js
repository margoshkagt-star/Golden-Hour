/**
 * Browser WebSocket client for OpenClaw gateway (chat.history, chat.send, chat events).
 */
(function (global) {
  function uuid() {
    return crypto.randomUUID();
  }

  function extractText(message) {
    if (message == null) return "";
    if (typeof message === "string") return message;
    if (typeof message.text === "string") return message.text;
    if (typeof message.content === "string") return message.content;
    if (Array.isArray(message.content)) {
      return message.content
        .filter((b) => b && b.type === "text" && b.text)
        .map((b) => b.text)
        .join("\n");
    }
    return "";
  }

  class GatewayChat {
    constructor() {
      this.ws = null;
      this.connected = false;
      this.connecting = false;
      this.token = "";
      this.url = "";
      this.pending = new Map();
      this.listeners = new Map();
      this.connectReqId = null;
      this.methods = new Set();
      this.backoffMs = 1000;
      this.reconnectTimer = null;
      this.intentionalClose = false;
    }

    on(event, cb) {
      if (!this.listeners.has(event)) this.listeners.set(event, new Set());
      this.listeners.get(event).add(cb);
      return () => this.listeners.get(event)?.delete(cb);
    }

    emit(event, data) {
      const subs = this.listeners.get(event);
      if (!subs) return;
      for (const cb of subs) {
        try { cb(data); } catch (e) { console.error("[gw-chat]", e); }
      }
    }

    hasMethod(name) {
      return this.methods.has(name);
    }

    connect(url, token) {
      this.url = url;
      this.token = token;
      this.intentionalClose = false;
      if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
        return Promise.resolve();
      }
      if (this.connecting) {
        return new Promise((resolve, reject) => {
          const off = this.on("connected", () => { off(); resolve(); });
          const offE = this.on("error", (e) => { offE(); reject(e); });
        });
      }

      return new Promise((resolve, reject) => {
        this.connecting = true;
        let settled = false;
        const done = (fn) => {
          if (settled) return;
          settled = true;
          fn();
        };

        const ws = new WebSocket(url);
        this.ws = ws;

        ws.onopen = () => {
          this.connectReqId = uuid();
          const frame = {
            type: "req",
            id: this.connectReqId,
            method: "connect",
            params: {
              minProtocol: 4,
              maxProtocol: 4,
              client: {
                id: "openclaw-control-ui",
                displayName: "Felpik Dashboard",
                version: "1.0.0",
                platform: "web",
                mode: "webchat",
                instanceId: uuid().slice(0, 8),
              },
              auth: { token: this.token },
              role: "operator",
              scopes: ["operator.read", "operator.write", "operator.admin"],
            },
          };
          ws.send(JSON.stringify(frame));
        };

        ws.onmessage = (ev) => {
          let frame;
          try { frame = JSON.parse(ev.data); } catch { return; }

          if (frame.type === "res") {
            if (frame.id === this.connectReqId) {
              this.connectReqId = null;
              this.connecting = false;
              if (frame.ok && frame.payload) {
                this.connected = true;
                this.backoffMs = 1000;
                const methods = frame.payload.features?.methods || [];
                this.methods = new Set(methods);
                this.emit("connected", frame.payload);
                done(() => resolve(frame.payload));
              } else {
                const err = new Error(frame.error?.message || "Gateway handshake failed");
                this.emit("error", err);
                done(() => reject(err));
              }
              return;
            }
            const p = this.pending.get(frame.id);
            if (!p) return;
            this.pending.delete(frame.id);
            clearTimeout(p.timer);
            if (frame.ok) p.resolve(frame.payload);
            else p.reject(new Error(frame.error?.message || "RPC error"));
            return;
          }

          if (frame.type === "event") {
            this.emit("event", frame);
            if (frame.event) this.emit("event:" + frame.event, frame.payload);
          }
        };

        ws.onclose = () => {
          this.ws = null;
          this.connected = false;
          this.connecting = false;
          this.connectReqId = null;
          this.rejectAll("Connection closed");
          this.emit("disconnected");
          if (!this.intentionalClose) this.scheduleReconnect();
        };

        ws.onerror = () => {
          this.connecting = false;
          const err = new Error("WebSocket error");
          this.emit("error", err);
          done(() => reject(err));
        };

        setTimeout(() => {
          if (!settled && !this.connected) {
            done(() => reject(new Error("Gateway connect timeout")));
          }
        }, 15000);
      });
    }

    disconnect() {
      this.intentionalClose = true;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
      this.connected = false;
    }

    scheduleReconnect() {
      if (this.reconnectTimer || !this.url || !this.token) return;
      const delay = this.backoffMs + Math.random() * 300;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect(this.url, this.token).catch(() => {});
      }, delay);
      this.backoffMs = Math.min(this.backoffMs * 2, 30000);
    }

    rejectAll(reason) {
      for (const [, p] of this.pending) {
        clearTimeout(p.timer);
        p.reject(new Error(reason));
      }
      this.pending.clear();
    }

    request(method, params, timeoutMs = 120000) {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return Promise.reject(new Error("Gateway not connected"));
      }
      return new Promise((resolve, reject) => {
        const id = uuid();
        const timer = setTimeout(() => {
          if (this.pending.has(id)) {
            this.pending.delete(id);
            reject(new Error("RPC timeout: " + method));
          }
        }, timeoutMs);
        this.pending.set(id, { resolve, reject, timer });
        this.ws.send(JSON.stringify({ type: "req", id, method, params }));
      });
    }

    chatHistory(sessionKey, limit = 200) {
      return this.request("chat.history", { sessionKey, limit });
    }

    chatSend(sessionKey, message, idempotencyKey) {
      return this.request("chat.send", { sessionKey, message, idempotencyKey });
    }

    chatAbort(sessionKey, runId) {
      return this.request("chat.abort", { sessionKey, runId });
    }
  }

  global.GatewayChat = GatewayChat;
  global.GatewayChatExtractText = extractText;
})(typeof window !== "undefined" ? window : globalThis);
