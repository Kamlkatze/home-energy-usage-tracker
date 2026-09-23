import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import HomePage from '../../pages/Home';

describe('Home page', () => {
  it('renders without throwing and shows the page heading', () => {
    renderWithProviders(<HomePage />);
    expect(
      screen.getByRole('heading', { name: 'Home Energy Usage Tracker' }),
    ).toBeInTheDocument();
  });
});