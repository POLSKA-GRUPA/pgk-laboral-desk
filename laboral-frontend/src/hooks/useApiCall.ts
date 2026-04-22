import { useState, useCallback, useRef, useEffect } from 'react';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyApiFn = (...args: any[]) => Promise<{ data: any }>;

type ApiData<F extends AnyApiFn> = Awaited<ReturnType<F>>['data'];

export function useApiCall<F extends AnyApiFn>(apiFn: F) {
  type T = ApiData<F>;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args: Parameters<F>): Promise<T | null> => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFn(...args);
        if (mountedRef.current) {
          setData(res.data as T);
        }
        return res.data as T;
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
