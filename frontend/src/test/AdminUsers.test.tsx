import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { MemoryRouter, Route, Routes } from 'react-router';
import AdminUsers from '../pages/AdminUsers';
import RequireAdmin from '../components/RequireAdmin';
import { AuthProvider } from '../context/AuthContext';
import { authApi, adminApi, ADMIN_USER_OTHER } from './mocks/api';

const apiError = (detail: string, status = 400): AxiosError =>
  new AxiosError(
    `Request failed with status code ${status}`,
    AxiosError.ERR_BAD_RESPONSE,
    undefined,
    undefined,
    {
      data: { detail },
      status,
      statusText: 'Error',
      headers: {},
      config: { headers: {} },
    } as unknown as AxiosResponse,
  );

const renderAdminUsers = () =>
  render(
    <MemoryRouter initialEntries={['/admin/users']}>
      <AuthProvider>
        <Routes>
          <Route
            path="/admin/users"
            element={
              <RequireAdmin>
                <AdminUsers />
              </RequireAdmin>
            }
          />
          <Route path="/" element={<div data-testid="home-page">Home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );

describe('RequireAdmin', () => {
  it('redirects non-admin users to the home page', async () => {
    vi.mocked(authApi.me).mockResolvedValue({ ...ADMIN_USER_OTHER, totp_enabled: false });
    renderAdminUsers();

    await waitFor(() => expect(screen.getByTestId('home-page')).toBeInTheDocument());
    expect(screen.queryByTestId('admin-users-table')).not.toBeInTheDocument();
  });

  it('renders the admin page for admins', async () => {
    renderAdminUsers();

    expect(await screen.findByTestId('admin-users-table')).toBeInTheDocument();
    expect(screen.getByText('testadmin')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
  });
});

describe('AdminUsers page', () => {
  it('lists users with role, status and two-factor columns', async () => {
    renderAdminUsers();

    const table = await screen.findByTestId('admin-users-table');
    expect(table).toHaveTextContent('Administrator');
    expect(table).toHaveTextContent('Benutzer');
    expect(table).toHaveTextContent('Aktiviert');
  });

  it('hides the self-demotion and self-deactivation buttons for the own row', async () => {
    renderAdminUsers();

    await screen.findByTestId('admin-users-table');
    // The "Sie" marker row (testadmin) has no Demote/Deactivate buttons
    const rows = screen.getAllByRole('row');
    const selfRow = rows.find((row) => row.textContent?.includes('(Sie)'));
    expect(selfRow).toBeDefined();
    expect(selfRow!.textContent).not.toContain('Deaktivieren');
    expect(selfRow!.textContent).not.toContain('Zum Benutzer machen');
    // The other user's row offers both actions
    const otherRow = rows.find((row) => row.textContent?.includes('bob'));
    expect(otherRow!.textContent).toContain('Deaktivieren');
    expect(otherRow!.textContent).toContain('Zum Admin machen');
  });

  it('creates a user through the dialog and refreshes the list', async () => {
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    await userEvent.click(screen.getByRole('button', { name: 'Benutzer anlegen' }));
    expect(screen.getByTestId('create-user-form')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'carol');
    await userEvent.type(screen.getByLabelText('Passwort'), 'a strong new password');
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));

    await waitFor(() =>
      expect(adminApi.createUser).toHaveBeenCalledWith('carol', 'a strong new password', 'user'),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Benutzer wurde angelegt.');
    // Dialog closed again
    await waitFor(() =>
      expect(screen.queryByTestId('create-user-form')).not.toBeInTheDocument(),
    );
  });

  it('shows backend validation errors from the create dialog', async () => {
    vi.mocked(adminApi.createUser).mockRejectedValue(
      apiError('Dieser Benutzername ist bereits vergeben.', 409),
    );
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    await userEvent.click(screen.getByRole('button', { name: 'Benutzer anlegen' }));
    await userEvent.type(screen.getByLabelText('Benutzername'), 'bob');
    await userEvent.type(screen.getByLabelText('Passwort'), 'a strong new password');
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Dieser Benutzername ist bereits vergeben.',
    );
  });

  it('toggles the active state of another user', async () => {
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    const otherRow = screen
      .getAllByRole('row')
      .find((row) => row.textContent?.includes('bob'))!;
    await userEvent.click(within(otherRow).getByRole('button', { name: 'Deaktivieren' }));

    await waitFor(() =>
      expect(adminApi.updateUser).toHaveBeenCalledWith(ADMIN_USER_OTHER.id, {
        is_active: false,
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Benutzer wurde deaktiviert.');
  });

  it('toggles the role of another user', async () => {
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    const otherRow = screen
      .getAllByRole('row')
      .find((row) => row.textContent?.includes('bob'))!;
    await userEvent.click(within(otherRow).getByRole('button', { name: 'Zum Admin machen' }));

    await waitFor(() =>
      expect(adminApi.updateUser).toHaveBeenCalledWith(ADMIN_USER_OTHER.id, {
        role: 'admin',
      }),
    );
  });

  it('resets a password through the dialog', async () => {
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    const otherRow = screen
      .getAllByRole('row')
      .find((row) => row.textContent?.includes('bob'))!;
    await userEvent.click(within(otherRow).getByRole('button', { name: 'Passwort' }));
    expect(screen.getByTestId('reset-password-form')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'a reset password here');
    await userEvent.click(screen.getByRole('button', { name: 'Zurücksetzen' }));

    await waitFor(() =>
      expect(adminApi.updateUser).toHaveBeenCalledWith(ADMIN_USER_OTHER.id, {
        new_password: 'a reset password here',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Passwort wurde zurückgesetzt, Sitzungen abgemeldet.',
    );
  });

  it('resets TOTP through the confirmation dialog', async () => {
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    await userEvent.click(screen.getByRole('button', { name: '2FA zurücksetzen' }));
    expect(screen.getByTestId('reset-totp-dialog')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Zurücksetzen' }));
    await waitFor(() =>
      expect(adminApi.updateUser).toHaveBeenCalledWith(ADMIN_USER_OTHER.id, {
        reset_totp: true,
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Zwei-Faktor wurde zurückgesetzt.',
    );
  });

  it('shows backend protection errors (last admin rule)', async () => {
    vi.mocked(adminApi.updateUser).mockRejectedValue(
      apiError('Der letzte aktive Administrator kann nicht entfernt werden.'),
    );
    renderAdminUsers();
    await screen.findByTestId('admin-users-table');

    const otherRow = screen
      .getAllByRole('row')
      .find((row) => row.textContent?.includes('bob'))!;
    // bob is a user, so the other active admin (self) is the last one
    await userEvent.click(within(otherRow).getByRole('button', { name: 'Zum Admin machen' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Der letzte aktive Administrator kann nicht entfernt werden.',
    );
  });
});

// the fixture data contract).
