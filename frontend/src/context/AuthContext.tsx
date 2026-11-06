import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { authApi } from '../api/client';
import { AuthContext } from './authContext';
import type { AuthUser } from '../types';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Initial session check: a valid session cookie makes /me return the
  // user, otherwise the app starts unauthenticated. The 401 from /me is
  // exempt from the global unauthorized event (see client.ts).
  useEffect(() => {
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A 401 on any non-auth endpoint means the session expired or was
  // revoked server-side. The interceptor in client.ts dispatches this
  // event; dropping the user makes the route guard redirect to /login.
  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, []);

  const login = useCallback(
    async (username: string, password: string, totpCode?: string) => {
      const loggedIn = await authApi.login(username, password, totpCode);
      setUser(loggedIn);
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      navigate('/login');
    }
  }, [navigate]);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}