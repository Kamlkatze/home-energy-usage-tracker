import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import MeterForm from '../../pages/MeterForm';

describe('MeterForm page', () => {
  it('renders without throwing and shows the page heading', () => {
    renderWithProviders(<MeterForm />);
    expect(
      screen.getByRole('heading', { name: 'Neuer Zähler' }),
    ).toBeInTheDocument();
  });
});