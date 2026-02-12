import { useEffect, useState } from 'react';
import { useWS } from '../contexts/WebSocketContext';

export function useRealTimeData<T>(topic: string, event: string, initial: T) {
  const ws = useWS();
  const [data, setData] = useState<T>(initial);

  useEffect(() => {
    const handler = (payload: any) => setData(payload as T);
    ws.subscribe(topic);
    ws.on(event, handler);
    return () => {
      ws.off(event, handler);
      ws.unsubscribe(topic);
    };
  }, [ws, topic, event]);

  return data;
}
