import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import TariffForm from '../../pages/TariffForm';

describe('TariffForm page', () => {
  it('renders without throwing and shows the page heading', () => {
    renderWithProviders(<TariffForm />);
    expect(
      screen.getByRole('heading', { name: 'Neuen Tarifzeitraum hinzufügen' }),
    ).toBeInTheDocument();
  });
});