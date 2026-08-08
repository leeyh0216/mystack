/** React Effect synchronization guidance: https://react.dev/learn/synchronizing-with-effects */
import {useCallback, useEffect, useRef, useState} from "react";

export function usePollingResource<T>(load: () => Promise<T>, intervalMilliseconds: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const mounted = useRef(true);
  const active = useRef(false);

  const refresh = useCallback(async () => {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    try {
      const value = await load();
      if (!mounted.current) return;
      setData(value);
      setError(null);
      setUpdatedAt(new Date());
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught : new Error(String(caught)));
    } finally {
      active.current = false;
      if (mounted.current) setBusy(false);
    }
  }, [load]);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, intervalMilliseconds);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [intervalMilliseconds, refresh]);

  return {data, error, busy, updatedAt, refresh, setData};
}
