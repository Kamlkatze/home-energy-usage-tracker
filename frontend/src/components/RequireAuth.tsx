import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

// Route guard: renders the children only for authenticated users.
// While the initial /me check runs, a spinner is shown. Unauthenticated
// users are redirected to /login; the originally requested path is
// passed along so the login page can navigate back after a successful
// login.
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-label="Lade Sitzung" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}