import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import YearDetail from '../../pages/YearDetail';

describe('YearDetail page', () => {
  it('renders without throwing and shows the empty state', async () => {
    renderWithProviders(<YearDetail />, {
      path: '/years/:year',
      initialEntries: ['/years/2024'],
    });
    expect(
      await screen.findByText(/Keine Zählerdaten für das Jahr 2024/),
    ).toBeInTheDocument();
  });
});