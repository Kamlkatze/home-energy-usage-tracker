import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { MemoryRouter } from 'react-router';
import Profile from '../pages/Profile';
import { authApi, AUTH_USER } from './mocks/api';

const apiError = (detail: unknown, status = 400): AxiosError =>
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

const SETUP_DATA = { secret: 'JBSWY3DPEHPK3PXP', otpauth_url: 'otpauth://totp/Energy%20Tracker:alice' };

const renderProfile = () =>
  render(
    <MemoryRouter>
      <Profile />
    </MemoryRouter>,
  );

describe('Profile page', () => {
  it('renders the German password and two-factor cards', async () => {
    renderProfile();
    expect(screen.getByRole('heading', { name: 'Passwort ändern' })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Zwei-Faktor-Authentifizierung' }),
    ).toBeInTheDocument();
    // TOTP status is loaded and shows the inactive state
    await waitFor(() =>
      expect(screen.getByText(/nicht aktiviert/)).toBeInTheDocument(),
    );
  });

  it('rejects mismatched password confirmation client-side without an API call', async () => {
    renderProfile();

    await userEvent.type(screen.getByLabelText('Aktuelles Passwort'), 'old password here');
    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'a better new password');
    await userEvent.type(screen.getByLabelText('Neues Passwort wiederholen'), 'different text');
    await userEvent.click(screen.getByRole('button', { name: 'Passwort ändern' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die neuen Passwörter stimmen nicht überein.',
    );
    expect(authApi.changePassword).not.toHaveBeenCalled();
  });

  it('submits the password change and shows the success message', async () => {
    vi.mocked(authApi.changePassword).mockResolvedValue(undefined);
    renderProfile();

    await userEvent.type(screen.getByLabelText('Aktuelles Passwort'), 'old password here');
    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'a better new password');
    await userEvent.type(screen.getByLabelText('Neues Passwort wiederholen'), 'a better new password');
    await userEvent.click(screen.getByRole('button', { name: 'Passwort ändern' }));

    await waitFor(() =>
      expect(authApi.changePassword).toHaveBeenCalledWith('old password here', 'a better new password', false),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Passwort wurde geändert.');
  });

  it('forwards the logout-others checkbox to the API', async () => {
    vi.mocked(authApi.changePassword).mockResolvedValue(undefined);
    renderProfile();

    await userEvent.type(screen.getByLabelText('Aktuelles Passwort'), 'old password here');
    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'a better new password');
    await userEvent.type(screen.getByLabelText('Neues Passwort wiederholen'), 'a better new password');
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: 'Passwort ändern' }));

    await waitFor(() =>
      expect(authApi.changePassword).toHaveBeenCalledWith('old password here', 'a better new password', true),
    );
  });

  it('shows the backend error when the current password is wrong', async () => {
    vi.mocked(authApi.changePassword).mockRejectedValue(
      apiError('Aktuelles Passwort ist falsch.', 401),
    );
    renderProfile();

    await userEvent.type(screen.getByLabelText('Aktuelles Passwort'), 'wrong');
    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'a better new password');
    await userEvent.type(screen.getByLabelText('Neues Passwort wiederholen'), 'a better new password');
    await userEvent.click(screen.getByRole('button', { name: 'Passwort ändern' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Aktuelles Passwort ist falsch.');
  });

  it('shows the password strength error from the backend', async () => {
    vi.mocked(authApi.changePassword).mockRejectedValue(
      apiError('Passwort muss mindestens 15 Zeichen lang sein.'),
    );
    renderProfile();

    await userEvent.type(screen.getByLabelText('Aktuelles Passwort'), 'old password here');
    await userEvent.type(screen.getByLabelText('Neues Passwort'), 'short but ok');
    await userEvent.type(screen.getByLabelText('Neues Passwort wiederholen'), 'short but ok');
    await userEvent.click(screen.getByRole('button', { name: 'Passwort ändern' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Passwort muss mindestens 15 Zeichen lang sein.',
    );
  });

  it('runs the TOTP enrollment flow: setup, QR, code, enable', async () => {
    vi.mocked(authApi.getTotpStatus).mockResolvedValue({ enabled: false, pending_setup: false });
    vi.mocked(authApi.startTotpSetup).mockResolvedValue(SETUP_DATA);
    vi.mocked(authApi.enableTotp).mockResolvedValue({ enabled: true, pending_setup: false });
    renderProfile();

    await userEvent.click(screen.getByRole('button', { name: 'Einrichtung starten' }));
    expect(authApi.startTotpSetup).toHaveBeenCalled();
    expect(await screen.findByTestId('totp-qr')).toBeInTheDocument();
    expect(screen.getByText(SETUP_DATA.secret)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Aus der App generierter Code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Zwei-Faktor aktivieren' }));

    await waitFor(() => expect(authApi.enableTotp).toHaveBeenCalledWith('123456'));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Zwei-Faktor-Authentifizierung ist aktiviert.',
    );
  });

  it('shows the backend error when the TOTP verification code is wrong', async () => {
    vi.mocked(authApi.getTotpStatus).mockResolvedValue({ enabled: false, pending_setup: false });
    vi.mocked(authApi.startTotpSetup).mockResolvedValue(SETUP_DATA);
    vi.mocked(authApi.enableTotp).mockRejectedValue(apiError('Ungültiger Zwei-Faktor-Code.'));
    renderProfile();

    await userEvent.click(screen.getByRole('button', { name: 'Einrichtung starten' }));
    await screen.findByTestId('totp-qr');
    await userEvent.type(screen.getByLabelText('Aus der App generierter Code'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Zwei-Faktor aktivieren' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ungültiger Zwei-Faktor-Code.');
  });

  it('offers the disable form when TOTP is enabled and disables with password and code', async () => {
    vi.mocked(authApi.getTotpStatus).mockResolvedValue({ enabled: true, pending_setup: false });
    vi.mocked(authApi.disableTotp).mockResolvedValue({ enabled: false, pending_setup: false });
    renderProfile();

    expect(
      await screen.findByRole('button', { name: 'Zwei-Faktor deaktivieren' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Aktuelles Passwort')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Passwort zur Bestätigung'), AUTH_USER.username);
    await userEvent.type(screen.getByLabelText('Zwei-Faktor-Code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Zwei-Faktor deaktivieren' }));

    await waitFor(() =>
      expect(authApi.disableTotp).toHaveBeenCalledWith(AUTH_USER.username, '123456'),
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Zwei-Faktor-Authentifizierung wurde deaktiviert.',
    );
  });
});