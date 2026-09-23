import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import MeterList from '../../pages/MeterList';

describe('MeterList page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<MeterList />);
    expect(
      await screen.findByRole('heading', { name: /Alle Zähler/ }),
    ).toBeInTheDocument();
  });
});