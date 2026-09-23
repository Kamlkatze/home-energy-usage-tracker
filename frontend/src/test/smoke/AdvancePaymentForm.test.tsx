import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import AdvancePaymentForm from '../../pages/AdvancePaymentForm';

describe('AdvancePaymentForm page', () => {
  it('renders without throwing and shows the page heading', () => {
    renderWithProviders(<AdvancePaymentForm />);
    expect(
      screen.getByRole('heading', { name: 'Neue Abschlagszahlung hinzufügen' }),
    ).toBeInTheDocument();
  });
});