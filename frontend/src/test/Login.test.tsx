import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { MemoryRouter, Route, Routes } from 'react-router';
import Login from '../pages/Login';
import { AuthProvider } from '../context/AuthContext';
import { authApi, AUTH_USER } from './mocks/api';

// Builds an AxiosError with the backend's login error payload shape.
const loginError = (detail: unknown, status = 401): AxiosError =>
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

const renderLoginPage = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<div data-testid="home-page">Home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );

describe('Login page', () => {
  it('renders the German login form', () => {
    renderLoginPage();
    expect(screen.getByRole('heading', { name: 'Anmeldung' })).toBeInTheDocument();
    expect(screen.getByLabelText('Benutzername')).toBeInTheDocument();
    expect(screen.getByLabelText('Passwort')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Anmelden' })).toBeInTheDocument();
  });

  it('submits username and password and navigates to the home page on success', async () => {
    vi.mocked(authApi.login).mockResolvedValue(AUTH_USER);
    renderLoginPage();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'alice');
    await userEvent.type(screen.getByLabelText('Passwort'), 'pw');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));

    await waitFor(() => expect(authApi.login).toHaveBeenCalledWith('alice', 'pw', undefined));
    await waitFor(() => expect(screen.getByTestId('home-page')).toBeInTheDocument());
  });

  it('shows the generic credential error message on wrong credentials', async () => {
    vi.mocked(authApi.login).mockRejectedValue(
      loginError('Ungültiger Benutzername oder Passwort.'),
    );
    renderLoginPage();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'alice');
    await userEvent.type(screen.getByLabelText('Passwort'), 'pw');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ungültiger Benutzername oder Passwort.',
    );
  });

  it('shows the TOTP field when the backend requires the second factor', async () => {
    vi.mocked(authApi.login).mockRejectedValue(
      loginError({ message: 'Zwei-Faktor-Code erforderlich.', totp_required: true }),
    );
    renderLoginPage();

    expect(screen.queryByLabelText('Zwei-Faktor-Code')).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'alice');
    await userEvent.type(screen.getByLabelText('Passwort'), 'pw');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));

    const totpField = await screen.findByLabelText('Zwei-Faktor-Code');
    expect(totpField).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Zwei-Faktor-Code erforderlich.');
  });

  it('retries login with the TOTP code once the second factor is filled in', async () => {
    vi.mocked(authApi.login)
      .mockRejectedValueOnce(
        loginError({ message: 'Zwei-Faktor-Code erforderlich.', totp_required: true }),
      )
      .mockResolvedValueOnce(AUTH_USER);
    renderLoginPage();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'alice');
    await userEvent.type(screen.getByLabelText('Passwort'), 'pw');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));
    await screen.findByLabelText('Zwei-Faktor-Code');

    await userEvent.type(screen.getByLabelText('Zwei-Faktor-Code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));

    await waitFor(() =>
      expect(authApi.login).toHaveBeenLastCalledWith('alice', 'pw', '123456'),
    );
    await waitFor(() => expect(screen.getByTestId('home-page')).toBeInTheDocument());
  });

  it('shows a generic error for non-axios failures', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new Error('Network Error'));
    renderLoginPage();

    await userEvent.type(screen.getByLabelText('Benutzername'), 'alice');
    await userEvent.type(screen.getByLabelText('Passwort'), 'pw');
    await userEvent.click(screen.getByRole('button', { name: 'Anmelden' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.',
    );
  });
});