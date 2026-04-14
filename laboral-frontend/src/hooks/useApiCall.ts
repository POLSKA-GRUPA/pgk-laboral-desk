import { useState, useCallback, useRef, useEffect } from 'react';

export function useApiCall<T>(apiFn: (...args: unknown[]) => Promise<{ data: T }>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args: unknown[]) => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFn(...args);
        if (mountedRef.current) {
          setData(res.data);
        }
        return res.data;
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ||
          (err as Error).message ||
          'Error desconocido';
        if (mountedRef.current) {
          setError(msg);
        }
        return null;
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [apiFn]
  );

  return { data, loading, error, execute };
}
