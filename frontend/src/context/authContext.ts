import { createContext } from 'react';
import type { AuthUser } from '../types';

export interface AuthContextValue {
  user: AuthUser | null;
  // True while the initial /me check has not resolved yet
  loading: boolean;
  login: (username: string, password: string, totpCode?: string) => Promise<void>;
  logout: () => Promise<void>;
}

// Context object lives in its own module so that AuthContext.tsx exports
// only the provider component (react-refresh/only-export-components) and
// the useAuth hook can live in src/hooks/ (src/hooks/useAuth.ts).
export const AuthContext = createContext<AuthContextValue | null>(null);