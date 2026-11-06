import { useState } from 'react';
import type { FormEvent } from 'react';
import axios from 'axios';
import { ShieldCheck, UserPlus, KeyRound } from 'lucide-react';
import { adminApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { useAuth } from '../hooks/useAuth';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Dialog,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectItem,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import type { AdminUser } from '../types';

function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrator',
  user: 'Benutzer',
};

// Inner form of the "create user" dialog. Mounted only while the dialog
// is open (keyed remount convention) so the fields start empty every time.
function CreateUserForm({
  onDone,
  onCancel,
  onError,
}: {
  onDone: () => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await adminApi.createUser(username, password, role === 'admin' ? 'admin' : 'user');
      onDone();
    } catch (err) {
      onError(extractErrorMessage(err, 'Benutzer konnte nicht angelegt werden.'));
      onCancel();
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" data-testid="create-user-form">
      <h2 className="text-lg font-semibold">Benutzer anlegen</h2>
      <div className="space-y-2">
        <Label htmlFor="admin-new-username">Benutzername</Label>
        <Input
          id="admin-new-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="admin-new-password">Passwort</Label>
        <Input
          id="admin-new-password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <p className="text-xs text-muted-foreground">Mindestens 15 Zeichen.</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="admin-new-role">Rolle</Label>
        <Select
          id="admin-new-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <SelectItem value="user">Benutzer</SelectItem>
          <SelectItem value="admin">Administrator</SelectItem>
        </Select>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" disabled={saving}>
          Anlegen
        </Button>
      </div>
    </form>
  );
}

// Inner form of the "password reset" dialog.
function ResetPasswordForm({
  target,
  onDone,
  onCancel,
  onError,
}: {
  target: AdminUser;
  onDone: () => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await adminApi.updateUser(target.id, { new_password: newPassword });
      onDone();
    } catch (err) {
      onError(extractErrorMessage(err, 'Passwort konnte nicht zurückgesetzt werden.'));
      onCancel();
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" data-testid="reset-password-form">
      <h2 className="text-lg font-semibold">
        Passwort für {target.username} zurücksetzen
      </h2>
      <p className="text-sm text-muted-foreground">
        Alle aktiven Sitzungen dieses Benutzers werden abgemeldet.
      </p>
      <div className="space-y-2">
        <Label htmlFor="admin-reset-password">Neues Passwort</Label>
        <Input
          id="admin-reset-password"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
        <p className="text-xs text-muted-foreground">Mindestens 15 Zeichen.</p>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" disabled={saving}>
          Zurücksetzen
        </Button>
      </div>
    </form>
  );
}

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const [reloadKey, setReloadKey] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [totpTarget, setTotpTarget] = useState<AdminUser | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const { data: users, loading, error } = useFetch(() => adminApi.listUsers(), [reloadKey]);

  const refresh = () => {
    setReloadKey((key) => key + 1);
  };

  const runAction = async (action: () => Promise<unknown>, message: string) => {
    setActionError(null);
    setActionMessage(null);
    try {
      await action();
      setActionMessage(message);
      refresh();
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Aktion fehlgeschlagen.'));
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <Card>
        <CardHeader className="flex flex-col gap-2">
          <div className="flex justify-between items-center gap-4">
            <CardTitle className="text-lg flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Benutzerverwaltung
            </CardTitle>
            <Button size="sm" className="gap-2" onClick={() => setCreateOpen(true)}>
              <UserPlus className="h-4 w-4" />
              Benutzer anlegen
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="text-sm text-destructive mb-4" role="alert">
              {error}
            </p>
          )}
          {actionError && (
            <p className="text-sm text-destructive mb-4" role="alert">
              {actionError}
            </p>
          )}
          {actionMessage && (
            <p className="text-sm text-green-600 mb-4" role="status">
              {actionMessage}
            </p>
          )}
          {loading ? (
            <p className="text-sm text-muted-foreground">Lade Benutzer …</p>
          ) : (
            <Table data-testid="admin-users-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Benutzername</TableHead>
                  <TableHead>Rolle</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Zwei-Faktor</TableHead>
                  <TableHead className="text-right">Aktionen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(users ?? []).map((user) => {
                  const isSelf = user.id === currentUser?.id;
                  return (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">
                        {user.username}
                        {isSelf && <span className="text-xs text-muted-foreground"> (Sie)</span>}
                      </TableCell>
                      <TableCell>{ROLE_LABELS[user.role] ?? user.role}</TableCell>
                      <TableCell>
                        {user.is_active ? 'Aktiv' : 'Deaktiviert'}
                      </TableCell>
                      <TableCell>{user.totp_enabled ? 'Aktiviert' : '—'}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2 flex-wrap">
                          {!isSelf && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                void runAction(
                                  () =>
                                    adminApi.updateUser(user.id, {
                                      role: user.role === 'admin' ? 'user' : 'admin',
                                    }),
                                  'Rolle wurde geändert.',
                                )
                              }
                            >
                              {user.role === 'admin' ? 'Zum Benutzer machen' : 'Zum Admin machen'}
                            </Button>
                          )}
                          {!isSelf && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                void runAction(
                                  () =>
                                    adminApi.updateUser(user.id, {
                                      is_active: !user.is_active,
                                    }),
                                  user.is_active
                                    ? 'Benutzer wurde deaktiviert.'
                                    : 'Benutzer wurde aktiviert.',
                                )
                              }
                            >
                              {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            onClick={() => setResetTarget(user)}
                          >
                            <KeyRound className="h-4 w-4" />
                            Passwort
                          </Button>
                          {user.totp_enabled && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setTotpTarget(user)}
                            >
                              2FA zurücksetzen
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {createOpen && (
        <Dialog open onOpenChange={setCreateOpen}>
          <CreateUserForm
            onDone={() => {
              setCreateOpen(false);
              setActionMessage('Benutzer wurde angelegt.');
              refresh();
            }}
            onCancel={() => setCreateOpen(false)}
            onError={(message) => setActionError(message)}
          />
        </Dialog>
      )}

      {resetTarget && (
        <Dialog open onOpenChange={() => setResetTarget(null)}>
          <ResetPasswordForm
            target={resetTarget}
            onDone={() => {
              setResetTarget(null);
              setActionMessage('Passwort wurde zurückgesetzt, Sitzungen abgemeldet.');
              refresh();
            }}
            onCancel={() => setResetTarget(null)}
            onError={(message) => {
              setResetTarget(null);
              setActionError(message);
            }}
          />
        </Dialog>
      )}

      {totpTarget && (
        <Dialog open onOpenChange={() => setTotpTarget(null)}>
          <div className="space-y-4" data-testid="reset-totp-dialog">
            <h2 className="text-lg font-semibold">
              Zwei-Faktor für {totpTarget.username} zurücksetzen?
            </h2>
            <p className="text-sm text-muted-foreground">
              Die Zwei-Faktor-Einrichtung wird gelöscht. Der Benutzer kann die
              Zwei-Faktor-Authentifizierung anschließend neu einrichten.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setTotpTarget(null)}>
                Abbrechen
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  void runAction(
                    () => adminApi.updateUser(totpTarget.id, { reset_totp: true }),
                    'Zwei-Faktor wurde zurückgesetzt.',
                  );
                  setTotpTarget(null);
                }}
              >
                Zurücksetzen
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}