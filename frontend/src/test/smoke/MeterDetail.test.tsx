import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import MeterDetail from '../../pages/MeterDetail';

describe('MeterDetail page', () => {
  it('renders without throwing and shows a stable section', async () => {
    renderWithProviders(<MeterDetail />, {
      path: '/meters/:id',
      initialEntries: ['/meters/1'],
    });
    expect(
      await screen.findByRole('heading', { name: 'Zählerdetails' }),
    ).toBeInTheDocument();
  });
});