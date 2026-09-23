import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import AdvancePaymentList from '../../pages/AdvancePaymentList';

describe('AdvancePaymentList page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<AdvancePaymentList />);
    expect(
      await screen.findByRole('heading', { name: /Abschlagszahlungen/ }),
    ).toBeInTheDocument();
  });
});