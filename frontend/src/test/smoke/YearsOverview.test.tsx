import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import YearsOverview from '../../pages/YearsOverview';

describe('YearsOverview page', () => {
  it('renders without throwing and shows the empty state', async () => {
    renderWithProviders(<YearsOverview />);
    expect(
      await screen.findByText(/Keine Zählerstände vorhanden\./),
    ).toBeInTheDocument();
  });
});