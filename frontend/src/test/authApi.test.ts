import { describe, expect, it, vi } from 'vitest';
import {
  authApi,
  isAuthExemptUrl,
} from '../api/client';

// setup.ts globally mocks ../api/client so route components never hit the
// network. These unit tests exercise the REAL client implementation instead
// (same pattern as client.test.ts): only the axios module is mocked, its
// create() factory returns a shared instance whose HTTP verbs are vi.fn()s.
vi.unmock('../api/client');

const { mockAxiosInstance } = vi.hoisted(() => ({
  mockAxiosInstance: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios');
  return {
    ...actual,
    default: {
      ...actual.default,
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

const MOCK_USER = {
  id: 1,
  username: 'testadmin',
  role: 'admin',
  totp_enabled: false,
};

describe('authApi', () => {
  it('login posts username and password without a TOTP code by default', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: MOCK_USER });

    await expect(authApi.login('alice', 'secret')).resolves.toEqual(MOCK_USER);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/login', {
      username: 'alice',
      password: 'secret',
    });
  });

  it('login includes the TOTP code when provided', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: MOCK_USER });

    await authApi.login('alice', 'secret', '123456');
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/login', {
      username: 'alice',
      password: 'secret',
      totp_code: '123456',
    });
  });

  it('logout posts to the logout endpoint', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: null });

    await expect(authApi.logout()).resolves.toBeUndefined();
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/logout');
  });

  it('me returns the authenticated user', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: MOCK_USER });

    await expect(authApi.me()).resolves.toEqual(MOCK_USER);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/auth/me');
  });

  it('changePassword sends the snake_case payload with default flags', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: null });

    await authApi.changePassword('old', 'new-long-password');
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/change-password', {
      current_password: 'old',
      new_password: 'new-long-password',
      logout_other_sessions: false,
    });
  });

  it('changePassword forwards logout_other_sessions', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: null });

    await authApi.changePassword('old', 'new-long-password', true);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/change-password', {
      current_password: 'old',
      new_password: 'new-long-password',
      logout_other_sessions: true,
    });
  });

  it('getTotpStatus returns the status payload', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: { enabled: false, pending_setup: true } });

    await expect(authApi.getTotpStatus()).resolves.toEqual({
      enabled: false,
      pending_setup: true,
    });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/auth/totp');
  });

  it('startTotpSetup returns secret and otpauth URL', async () => {
    const setup = { secret: 'JBSWY3DPEHPK3PXP', otpauth_url: 'otpauth://totp/x' };
    mockAxiosInstance.post.mockResolvedValue({ data: setup });

    await expect(authApi.startTotpSetup()).resolves.toEqual(setup);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/totp/setup');
  });

  it('enableTotp posts the verification code', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { enabled: true, pending_setup: false } });

    await expect(authApi.enableTotp('123456')).resolves.toEqual({
      enabled: true,
      pending_setup: false,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/totp/enable', {
      code: '123456',
    });
  });

  it('disableTotp posts password and code', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { enabled: false, pending_setup: false } });

    await expect(authApi.disableTotp('pw', '123456')).resolves.toEqual({
      enabled: false,
      pending_setup: false,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/auth/totp/disable', {
      password: 'pw',
      code: '123456',
    });
  });
});

describe('isAuthExemptUrl', () => {
  it('exempts the auth flow endpoints', () => {
    expect(isAuthExemptUrl('/api/auth/login')).toBe(true);
    expect(isAuthExemptUrl('/api/auth/logout')).toBe(true);
    expect(isAuthExemptUrl('/api/auth/me')).toBe(true);
  });

  it('does not exempt business endpoints', () => {
    expect(isAuthExemptUrl('/api/meters/')).toBe(false);
    expect(isAuthExemptUrl('/api/auth/totp')).toBe(false);
    expect(isAuthExemptUrl('/api/auth/change-password')).toBe(false);
  });

  it('treats a missing URL as not exempt', () => {
    expect(isAuthExemptUrl(undefined)).toBe(false);
  });
});