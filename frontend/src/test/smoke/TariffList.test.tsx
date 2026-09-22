import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import TariffList from '../../pages/TariffList';

describe('TariffList page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<TariffList />);
    expect(
      await screen.findByRole('heading', { name: /Tarife/ }),
    ).toBeInTheDocument();
  });
});