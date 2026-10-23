import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import BackupRestore from '../../pages/BackupRestore';

describe('BackupRestore page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<BackupRestore />);
    expect(
      await screen.findByText('Backup & Wiederherstellung'),
    ).toBeInTheDocument();
  });

  it('shows the current alembic revision from the API', async () => {
    renderWithProviders(<BackupRestore />);
    const revisions = await screen.findAllByText('3d6f19fc27d2');
    expect(revisions.length).toBeGreaterThanOrEqual(2);
  });
});
