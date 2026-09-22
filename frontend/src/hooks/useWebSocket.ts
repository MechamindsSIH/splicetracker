import { useState, useEffect, useCallback } from 'react';
import { wsClient } from '../services/websocket';

export function useWebSocket() {
  const [connected, setConnected] = useState(wsClient.isConnected);
  const [lastMessage, setLastMessage] = useState<any>(null);

  useEffect(() => {
    wsClient.connect();
    const unsub1 = wsClient.on('_connected', () => setConnected(true));
    const unsub2 = wsClient.on('_disconnected', () => setConnected(false));
    const unsub3 = wsClient.on('_message', (msg: any) => setLastMessage(msg));
    return () => { unsub1(); unsub2(); unsub3(); };
  }, []);

  const subscribe = useCallback((event: string, cb: (payload: any) => void) => {
    return wsClient.on(event, cb);
  }, []);

  return { connected, lastMessage, subscribe };
}
