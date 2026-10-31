import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from './utils';
import { metaApi, APP_META } from './mocks/api';
import Footer from '../components/Footer';

describe('Footer', () => {
  it('shows the app version and git commit once the metadata is loaded', async () => {
    renderWithProviders(<Footer />);
    expect(await screen.findByText(/v0\.2\.0/)).toBeInTheDocument();
    expect(screen.getByText(/Commit 3d6f19fc27d2/)).toBeInTheDocument();
  });

  it('renders the static lines while the metadata is still loading', async () => {
    vi.mocked(metaApi.getMeta).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<Footer />);
    expect(screen.getByText('Home Energy Usage Tracker • Local deployment • No cloud services')).toBeInTheDocument();
    expect(screen.queryByText(/v0\.2\.0/)).not.toBeInTheDocument();
    // Let the pending promise resolve for test isolation.
    await Promise.resolve();
  });

  it('hides the version line when the metadata request fails', async () => {
    vi.mocked(metaApi.getMeta).mockRejectedValue(new Error('boom'));
    renderWithProviders(<Footer />);
    expect(screen.getByText('Home Energy Usage Tracker • Local deployment • No cloud services')).toBeInTheDocument();
    expect(screen.queryByText(/v0\.2\.0/)).not.toBeInTheDocument();
    await screen.findByText('Data stays on your machine');
    expect(screen.queryByText(/v0\.2\.0/)).not.toBeInTheDocument();
  });

  it('replaces the git commit when it is unknown on the server', async () => {
    vi.mocked(metaApi.getMeta).mockResolvedValue({
      app_version: APP_META.app_version,
      git_commit: 'unknown',
    });
    renderWithProviders(<Footer />);
    expect(await screen.findByText(/v0\.2\.0 • Commit unknown/)).toBeInTheDocument();
  });
});
