import { useEffect, useMemo, useState } from 'react';
import { useWS } from '../contexts/WebSocketContext';

export function useChartData<T>(fetcher: (page: number, pageSize: number) => Promise<T[]>, topic: string, event: string, pageSize = 200) {
  const ws = useWS();
  const [data, setData] = useState<T[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const rows = await fetcher(page, pageSize);
      setData(rows);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'load failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, pageSize]);

  useEffect(() => {
    const handler = (payload: any) => setData((prev) => [...prev.slice(-pageSize + 1), payload]);
    ws.subscribe(topic);
    ws.on(event, handler);
    return () => {
      ws.off(event, handler);
      ws.unsubscribe(topic);
    };
  }, [ws, topic, event, pageSize]);

  return {
    data,
    loading,
    error,
    empty: !loading && !error && data.length === 0,
    page,
    setPage,
    retry: load,
  };
}
