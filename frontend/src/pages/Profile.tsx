import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import axios from 'axios';
import { QRCodeSVG } from 'qrcode.react';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { authApi } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import type { TotpStatus } from '../types';

function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}

interface TotpSetupData {
  secret: string;
  otpauth_url: string;
}

export default function Profile() {
  // Password change form
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [logoutOthers, setLogoutOthers] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordSaving, setPasswordSaving] = useState(false);

  // TOTP (two-factor) enrollment
  const [totpStatus, setTotpStatus] = useState<TotpStatus | null>(null);
  const [totpSetup, setTotpSetup] = useState<TotpSetupData | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpDisablePassword, setTotpDisablePassword] = useState('');
  const [totpError, setTotpError] = useState<string | null>(null);
  const [totpMessage, setTotpMessage] = useState<string | null>(null);
  const [totpBusy, setTotpBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    authApi
      .getTotpStatus()
      .then((status) => {
        if (!cancelled) setTotpStatus(status);
      })
      .catch(() => {
        if (!cancelled) setTotpStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError('Die neuen Passwörter stimmen nicht überein.');
      return;
    }
    setPasswordSaving(true);
    setPasswordError(null);
    setPasswordMessage(null);
    try {
      await authApi.changePassword(currentPassword, newPassword, logoutOthers);
      setPasswordMessage('Passwort wurde geändert.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setPasswordError(extractErrorMessage(err, 'Passwort konnte nicht geändert werden.'));
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleStartTotpSetup = async () => {
    setTotpBusy(true);
    setTotpError(null);
    setTotpMessage(null);
    try {
      setTotpSetup(await authApi.startTotpSetup());
    } catch (err) {
      setTotpError(extractErrorMessage(err, 'Einrichtung konnte nicht gestartet werden.'));
    } finally {
      setTotpBusy(false);
    }
  };

  const handleEnableTotp = async (event: FormEvent) => {
    event.preventDefault();
    setTotpBusy(true);
    setTotpError(null);
    try {
      const status = await authApi.enableTotp(totpCode);
      setTotpStatus(status);
      setTotpSetup(null);
      setTotpCode('');
      setTotpMessage('Zwei-Faktor-Authentifizierung ist aktiviert.');
    } catch (err) {
      setTotpError(extractErrorMessage(err, 'Code konnte nicht bestätigt werden.'));
    } finally {
      setTotpBusy(false);
    }
  };

  const handleDisableTotp = async (event: FormEvent) => {
    event.preventDefault();
    setTotpBusy(true);
    setTotpError(null);
    try {
      const status = await authApi.disableTotp(totpDisablePassword, totpCode);
      setTotpStatus(status);
      setTotpDisablePassword('');
      setTotpCode('');
      setTotpMessage('Zwei-Faktor-Authentifizierung wurde deaktiviert.');
    } catch (err) {
      setTotpError(extractErrorMessage(err, 'Deaktivierung fehlgeschlagen.'));
    } finally {
      setTotpBusy(false);
    }
  };

  const totpEnabled = totpStatus?.enabled ?? false;
  const totpEnrolling = totpSetup !== null || (totpStatus?.pending_setup ?? false);

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-primary" />
            Passwort ändern
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePasswordChange} className="space-y-4" data-testid="password-form">
            <div className="space-y-2">
              <Label htmlFor="profile-current-password">Aktuelles Passwort</Label>
              <Input
                id="profile-current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-new-password">Neues Passwort</Label>
              <Input
                id="profile-new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                Mindestens 15 Zeichen, oder 8 Zeichen wenn Zwei-Faktor aktiviert ist.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="profile-confirm-password">Neues Passwort wiederholen</Label>
              <Input
                id="profile-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="profile-logout-others"
                checked={logoutOthers}
                onChange={(e) => setLogoutOthers(e.target.checked)}
              />
              <Label htmlFor="profile-logout-others" className="text-sm font-normal">
                Alle anderen Geräte abmelden
              </Label>
            </div>
            {passwordError && (
              <p className="text-sm text-destructive" role="alert">
                {passwordError}
              </p>
            )}
            {passwordMessage && (
              <p className="text-sm text-green-600" role="status">
                {passwordMessage}
              </p>
            )}
            <Button type="submit" disabled={passwordSaving}>
              Passwort ändern
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Zwei-Faktor-Authentifizierung
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4" data-testid="totp-section">
          {totpEnabled ? (
            <>
              <p className="text-sm">
                Zwei-Faktor-Authentifizierung ist <strong>aktiviert</strong>.
              </p>
              <form onSubmit={handleDisableTotp} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="totp-disable-password">Passwort zur Bestätigung</Label>
                  <Input
                    id="totp-disable-password"
                    type="password"
                    autoComplete="current-password"
                    value={totpDisablePassword}
                    onChange={(e) => setTotpDisablePassword(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="totp-disable-code">Zwei-Faktor-Code</Label>
                  <Input
                    id="totp-disable-code"
                    inputMode="numeric"
                    placeholder="6-stelliger Code"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" variant="destructive" disabled={totpBusy}>
                  Zwei-Faktor deaktivieren
                </Button>
              </form>
            </>
          ) : totpEnrolling ? (
            <>
              <p className="text-sm">
                Scannen Sie den QR-Code mit einer Authenticator-App (z. B. Google
                Authenticator) oder tragen Sie den Schlüssel manuell ein.
              </p>
              {totpSetup && (
                <div className="flex flex-col items-center gap-3" data-testid="totp-qr">
                  <QRCodeSVG value={totpSetup.otpauth_url} size={180} />
                  <code className="text-xs break-all bg-muted px-2 py-1 rounded">
                    {totpSetup.secret}
                  </code>
                </div>
              )}
              <form onSubmit={handleEnableTotp} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="totp-enable-code">Aus der App generierter Code</Label>
                  <Input
                    id="totp-enable-code"
                    inputMode="numeric"
                    placeholder="6-stelliger Code"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" disabled={totpBusy}>
                  Zwei-Faktor aktivieren
                </Button>
              </form>
            </>
          ) : (
            <>
              <p className="text-sm">
                Zwei-Faktor-Authentifizierung ist <strong>nicht aktiviert</strong>.
              </p>
              <Button type="button" onClick={() => void handleStartTotpSetup()} disabled={totpBusy}>
                Einrichtung starten
              </Button>
            </>
          )}
          {totpError && (
            <p className="text-sm text-destructive" role="alert">
              {totpError}
            </p>
          )}
          {totpMessage && (
            <p className="text-sm text-green-600" role="status">
              {totpMessage}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}