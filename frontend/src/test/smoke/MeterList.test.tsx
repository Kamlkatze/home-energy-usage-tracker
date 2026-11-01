import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import MeterList from '../../pages/MeterList';
import { metersApi, METER_TYPE_INFO } from '../mocks/api';

describe('MeterList page', () => {
  it('renders without throwing and shows the page heading', async () => {
    renderWithProviders(<MeterList />);
    expect(
      await screen.findByRole('heading', { name: /Alle Zähler/ }),
    ).toBeInTheDocument();
  });

  it('renders a table with sortable headers, type filters and search', async () => {
    vi.mocked(metersApi.getAll).mockResolvedValue([
      {
        id: 1,
        meter_type: 'gas',
        label: 'Gaswohnung',
        meter_number: 'G-100',
        unit: 'm³',
        created_at: '2025-02-01T00:00:00Z',
        replaces_meter_id: null,
      },
      {
        id: 2,
        meter_type: 'electricity_import',
        label: 'Strombezug',
        meter_number: null,
        unit: 'kWh',
        created_at: '2025-01-01T00:00:00Z',
        replaces_meter_id: null,
      },
    ]);
    renderWithProviders(<MeterList />);
    expect(await screen.findByText('Gaswohnung')).toBeInTheDocument();
    expect(screen.getByText('Strombezug')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Zähler/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Nummer/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Typ/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Einheit/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Erstellt/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Aktionen' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Alle' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: METER_TYPE_INFO[0].label })).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('Suchen (Bezeichnung, Zählernummer, Typ)'),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Anzeigen' })).toHaveLength(2);
    expect(screen.getByText('G-100')).toBeInTheDocument();
    expect(screen.getAllByText('m³').length).toBeGreaterThan(0);
  });
});
