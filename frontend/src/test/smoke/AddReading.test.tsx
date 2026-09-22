import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import AddReading from '../../pages/AddReading';

describe('AddReading page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<AddReading />);
    expect(
      await screen.findByRole('heading', { name: 'Zählerstände eingeben' }),
    ).toBeInTheDocument();
  });
});