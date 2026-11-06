import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { AuthProvider } from '../context/AuthContext';
import { useAuth } from '../hooks/useAuth';
import { authApi, AUTH_USER } from './mocks/api';

// Probes the auth context value and the current router location so tests
// can assert both state and navigation side effects.
function renderWithAuth() {
  let current: ReturnType<typeof useAuth> | undefined;

  // Probe inside the catch-all route (business pages)
  function Probe() {
    current = useAuth();
    return <div data-testid="probe">{current.user ? current.user.username : 'anon'}</div>;
  }

  // Probe inside the /login route: after a logout the catch-all probe
  // unmounts (react-router switches to the /login match), so the
  // post-logout auth state must be read here.
  function LoginProbe() {
    current = useAuth();
    return <div data-testid="login-page">{current.user ? current.user.username : 'anon'}</div>;
  }

  render(
    <MemoryRouter initialEntries={['/meters']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route path="*" element={<Probe />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );

  return {
    get current() {
      return current;
    },
  };
}

describe('AuthContext', () => {
  it('starts in loading state and resolves the user from /me', async () => {
    const harness = renderWithAuth();
    expect(harness.current?.loading).toBe(true);
    expect(harness.current?.user).toBeNull();

    await waitFor(() => expect(harness.current?.loading).toBe(false));
    expect(harness.current?.user).toEqual(AUTH_USER);
    expect(screen.getByTestId('probe')).toHaveTextContent('testadmin');
  });

  it('ends up unauthenticated when /me fails (401)', async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error('401'));
    const harness = renderWithAuth();

    await waitFor(() => expect(harness.current?.loading).toBe(false));
    expect(harness.current?.user).toBeNull();
  });

  it('drops the user when the auth:unauthorized event fires', async () => {
    const harness = renderWithAuth();
    await waitFor(() => expect(harness.current?.user).toEqual(AUTH_USER));

    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    await waitFor(() => expect(harness.current?.user).toBeNull());
  });

  it('login resolves and stores the user', async () => {
    vi.mocked(authApi.login).mockResolvedValue(AUTH_USER);
    const harness = renderWithAuth();
    await waitFor(() => expect(harness.current?.loading).toBe(false));

    await harness.current!.login('alice', 'pw');
    expect(harness.current?.user).toEqual(AUTH_USER);
    expect(authApi.login).toHaveBeenCalledWith('alice', 'pw', undefined);
  });

  it('logout clears the user and redirects to /login', async () => {
    const harness = renderWithAuth();
    await waitFor(() => expect(harness.current?.user).toEqual(AUTH_USER));

    await harness.current!.logout();
    // The /login route now renders and shows the cleared auth state
    await waitFor(() => expect(screen.getByTestId('login-page')).toHaveTextContent('anon'));
  });

  it('logout still clears the user when the logout call fails', async () => {
    vi.mocked(authApi.logout).mockRejectedValue(new Error('network down'));
    const harness = renderWithAuth();
    await waitFor(() => expect(harness.current?.user).toEqual(AUTH_USER));

    await expect(harness.current!.logout()).rejects.toThrow('network down');
    await waitFor(() => expect(screen.getByTestId('login-page')).toHaveTextContent('anon'));
  });
});