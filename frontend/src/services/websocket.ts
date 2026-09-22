type EventCallback = (payload: any) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 3000;
  private _connected = false;

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/live`;
    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
        this._connected = true;
        this.reconnectDelay = 3000;
        this.emit('_connected', {});
      };
      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.emit(msg.type, msg.payload || msg);
          this.emit('_message', msg);
        } catch {}
      };
      this.ws.onclose = () => {
        this._connected = false;
        this.emit('_disconnected', {});
        this.scheduleReconnect();
      };
      this.ws.onerror = () => {
        this._connected = false;
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this._connected = false;
  }

  on(eventType: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);
    return () => {
      this.listeners.get(eventType)?.delete(callback);
    };
  }

  get isConnected(): boolean {
    return this._connected;
  }

  private emit(type: string, payload: any): void {
    this.listeners.get(type)?.forEach((cb) => {
      try { cb(payload); } catch {}
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000);
  }
}

export const wsClient = new WebSocketClient();
