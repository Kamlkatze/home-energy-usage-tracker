import { describe, expect, it } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './utils';
import NavDropdown from '../components/NavDropdown';
import { Euro, FileText } from 'lucide-react';

const items = [
  { to: '/readings/new', label: 'Zählerstände', icon: <FileText className="h-4 w-4" /> },
  { to: '/tariffs', label: 'Tarife', icon: <Euro className="h-4 w-4" /> },
];

describe('NavDropdown', () => {
  it('renders the trigger button and keeps the menu closed initially', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    const trigger = screen.getByRole('button', { name: 'Einträge' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('opens the menu and shows all items when the trigger is clicked', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    const trigger = screen.getByRole('button', { name: 'Einträge' });
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menuitem', { name: 'Zählerstände' })).toHaveAttribute('href', '/readings/new');
    expect(screen.getByRole('menuitem', { name: 'Tarife' })).toHaveAttribute('href', '/tariffs');
  });

  it('toggles the menu closed again on a second click', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    const trigger = screen.getByRole('button', { name: 'Einträge' });
    fireEvent.click(trigger);
    expect(screen.getByRole('menu')).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes the menu when a menu item is clicked', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    fireEvent.click(screen.getByRole('button', { name: 'Einträge' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Tarife' }));
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes the menu on outside click', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    fireEvent.click(screen.getByRole('button', { name: 'Einträge' }));
    expect(screen.getByRole('menu')).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('does not close on mousedown inside the dropdown', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    fireEvent.click(screen.getByRole('button', { name: 'Einträge' }));
    fireEvent.mouseDown(screen.getByRole('menu'));
    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  it('closes the menu on Escape', () => {
    renderWithProviders(<NavDropdown label="Einträge" items={items} />);
    fireEvent.click(screen.getByRole('button', { name: 'Einträge' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
