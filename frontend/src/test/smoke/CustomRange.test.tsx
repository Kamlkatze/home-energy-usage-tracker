import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import CustomRange from '../../pages/CustomRange';

describe('CustomRange page', () => {
  it('renders without throwing and shows the filter form', async () => {
    renderWithProviders(<CustomRange />);
    expect(screen.getByText('Individueller Zeitraum')).toBeInTheDocument();
    expect(screen.getByLabelText('Von')).toBeInTheDocument();
    expect(await screen.findByText('Anwenden')).toBeInTheDocument();
  });

  it('shows the empty state for every active area', async () => {
    renderWithProviders(<CustomRange />);
    expect(
      await screen.findAllByText(/Keine Messpunkte im gew\u00e4hlten Zeitraum/)
    ).toHaveLength(3);
  });
});
