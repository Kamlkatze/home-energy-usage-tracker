import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import HomePage from '../../pages/Home';

describe('Home page', () => {
  it('renders without throwing and shows the media type section', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByRole('heading', { name: 'Strom' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Gas' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Wasser' })).toBeInTheDocument();
  });

  it('shows navigation cards for all entry types including Abschläge', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByRole('link', { name: /Zähler Verwalte deine/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Zählerstände Gib neue/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Tarife Verwalte Tarife/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Abschläge Verwalte monatliche/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Jahresübersicht Verbrauch und Kosten/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Zeitraum Verbrauch und Kosten in einem/ })).toBeInTheDocument();
  });
});