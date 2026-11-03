import { useState } from 'react';
import type { FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router';
import axios from 'axios';
import { Loader2, LogIn } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { useAuth } from '../hooks/useAuth';

interface LoginErrorDetail {
  message?: string;
  totp_required?: boolean;
}

// Extracts the German error message from the backend response. The login
// endpoint returns either a string detail (generic credential error,
// lockout) or an object when only the second factor is missing.
function extractLoginError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string | LoginErrorDetail } | undefined)
      ?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (detail?.message) {
      return detail.message;
    }
  }
  return 'Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.';
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [showTotp, setShowTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? '/';

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password, showTotp && totpCode ? totpCode : undefined);
      navigate(from, { replace: true });
    } catch (err) {
      const detail = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: LoginErrorDetail | string } | undefined)?.detail
        : null;
      if (detail && typeof detail === 'object' && detail.totp_required) {
        setShowTotp(true);
      }
      setError(extractLoginError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl flex items-center gap-2">
            <LogIn className="h-5 w-5 text-primary" />
            Anmeldung
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="login-username">Benutzername</Label>
              <Input
                id="login-username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password">Passwort</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {showTotp && (
              <div className="space-y-2">
                <Label htmlFor="login-totp">Zwei-Faktor-Code</Label>
                <Input
                  id="login-totp"
                  inputMode="numeric"
                  placeholder="6-stelliger Code"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                />
              </div>
            )}
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              Anmelden
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}