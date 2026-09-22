import { useEffect, useRef, useState } from 'react';

export interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches data automatically on mount and whenever `deps` change
 * (same semantics as a useEffect dependency array).
 *
 * - No state is ever set after unmount or after the deps changed while
 *   the request was still running (tracked via an `active` flag).
 * - All state updates happen in async continuations (promise callbacks),
 *   never synchronously in the effect body, so the hook satisfies the
 *   react-hooks/set-state-in-effect rule. `loading` is switched to true
 *   in a microtask (before the next paint) at the start of each run.
 * - Errors are surfaced as `error: string` (err.message) and logged
 *   centrally with console.error in exactly one place: this hook.
 */
export function useFetch<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[] = []
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Always call the most recent fetchFn without making it an effect
  // dependency (writing a ref inside an effect is the allowed pattern).
  const fetchFnRef = useRef(fetchFn);
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  });

  useEffect(() => {
    let active = true;

    // Mark the start of a new request without setting state synchronously
    // in the effect body (the microtask runs before the next paint).
    void Promise.resolve().then(() => {
      if (active) {
        setLoading(true);
        setError(null);
      }
    });

    fetchFnRef.current().then(
      (result) => {
        if (!active) {
          return;
        }
        setData(result);
        setError(null);
        setLoading(false);
      },
      (err: unknown) => {
        // Central error logging for all consumers of this hook.
        console.error('useFetch: request failed:', err);
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      }
    );

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}
