import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

// Route guard for admin-only pages: redirects non-admin users to the
// home page. The backend enforces the same rule server-side (403).
// While the initial /me check runs, a spinner is shown so the redirect
// does not fire before the user is known.
export default function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-label="Lade Sitzung" />
      </div>
    );
  }
  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}