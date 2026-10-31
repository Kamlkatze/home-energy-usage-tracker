import { describe, expect, it, beforeEach, vi } from 'vitest';
import { screen, within, fireEvent } from '@testing-library/react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useParams } from 'react-router';
import { renderWithProviders } from './utils';
import YearsOverview from '../pages/YearsOverview';
import { costsApi } from './mocks/api';
import type { YearsOverviewItem } from '../types';

// Fixture: years given in non-ascending order and per-meter year sets that
// differ, so the test can verify the client-side ascending sort.
const ELECTRIC_METER: YearsOverviewItem = {
  meter_id: 1,
  meter_label: 'Strom Bezug',
  meter_type: 'electricity_import',
  unit: 'kWh',
  years: [
    { year: 2024, consumption: '2345.6789', cost: '123.45', cost_basis: 'actual' },
    { year: 2023, consumption: '1234.56', cost: '98.76', cost_basis: 'actual' },
  ],
};

// No 2024 entry on purpose -> that cell must render '—'.
const GAS_METER: YearsOverviewItem = {
  meter_id: 2,
  meter_label: 'Gas-Hauptzähler',
  meter_type: 'gas',
  unit: 'm³',
  years: [{ year: 2023, consumption: '12.3', cost: null, cost_basis: null }],
};

const FIXTURE = [ELECTRIC_METER, GAS_METER];

const StubYearDetail = () => <div>Jahresansicht für {useParams().year}</div>;

describe('YearsOverview', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the loading state while the request is pending', () => {
    vi.mocked(costsApi.getYearsOverview).mockImplementation(
      () => new Promise<YearsOverviewItem[]>(() => {}),
    );
    renderWithProviders(<YearsOverview />);

    expect(screen.getByText('Lade Jahresübersicht...')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Jahresübersicht' }),
    ).not.toBeInTheDocument();
  });

  it('renders all years with the correct summary data after a successful fetch', async () => {
    vi.mocked(costsApi.getYearsOverview).mockResolvedValue(FIXTURE);
    renderWithProviders(<YearsOverview />);

    expect(
      await screen.findByRole('heading', { name: 'Jahresübersicht' }),
    ).toBeInTheDocument();

    // Column headers: one per meter, label + unit.
    expect(
      screen.getByRole('columnheader', { name: 'Jahr' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: 'Strom Bezug (kWh)' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: 'Gas-Hauptzähler (m³)' }),
    ).toBeInTheDocument();

    // 2023 row: kWh rounded to integer, m³ with one decimal.
    const row2023 = screen.getByRole('row', { name: /2023/ });
    expect(within(row2023).getByText('2023')).toBeInTheDocument();
    expect(within(row2023).getByText('1235 kWh')).toBeInTheDocument();
    expect(within(row2023).getByText('12.3 m³')).toBeInTheDocument();

    // 2024 row: gas has no entry -> '—' placeholder.
    const row2024 = screen.getByRole('row', { name: /2024/ });
    expect(within(row2024).getByText('2346 kWh')).toBeInTheDocument();
    expect(within(row2024).getByText('—')).toBeInTheDocument();

    // Years are sorted ascending despite the fixture order.
    expect(
      screen.getAllByRole('link').map((link) => link.textContent),
    ).toEqual(['2023', '2024']);

    // Charts: only for meter types present in the data.
    expect(screen.getByText('Stromverbrauch')).toBeInTheDocument();
    expect(screen.getByText('Gasverbrauch')).toBeInTheDocument();
    expect(screen.queryByText('Wasserverbrauch')).not.toBeInTheDocument();
  });

  it('renders the empty state when there are no meters with data', async () => {
    vi.mocked(costsApi.getYearsOverview).mockResolvedValue([]);
    renderWithProviders(<YearsOverview />);

    expect(
      await screen.findByText('Keine Zählerstände vorhanden.'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Jahresübersicht' }),
    ).not.toBeInTheDocument();
  });

  it('shows the backend detail message on failure', async () => {
    vi.mocked(costsApi.getYearsOverview).mockRejectedValue({
      response: { data: { detail: 'Datenbank nicht erreichbar' } },
    });
    renderWithProviders(<YearsOverview />);

    expect(
      await screen.findByText('Datenbank nicht erreichbar'),
    ).toBeInTheDocument();
  });

  it('shows the thrown error message when there is no backend detail', async () => {
    vi.mocked(costsApi.getYearsOverview).mockRejectedValue(
      new Error('Network request failed'),
    );
    renderWithProviders(<YearsOverview />);

    expect(
      await screen.findByText('Network request failed'),
    ).toBeInTheDocument();
  });

  it('shows the generic fallback message for unexpected rejections', async () => {
    vi.mocked(costsApi.getYearsOverview).mockRejectedValue('kaputt');
    renderWithProviders(<YearsOverview />);

    expect(
      await screen.findByText('Fehler beim Laden der Jahresübersicht.'),
    ).toBeInTheDocument();
  });

  it('links every year to its YearDetail route', async () => {
    vi.mocked(costsApi.getYearsOverview).mockResolvedValue(FIXTURE);
    renderWithProviders(<YearsOverview />);
    await screen.findByRole('heading', { name: 'Jahresübersicht' });

    expect(screen.getByRole('link', { name: '2023' })).toHaveAttribute(
      'href',
      '/years/2023',
    );
    expect(screen.getByRole('link', { name: '2024' })).toHaveAttribute(
      'href',
      '/years/2024',
    );
  });

  it('navigates to the correct YearDetail route when a year is clicked', async () => {
    vi.mocked(costsApi.getYearsOverview).mockResolvedValue(FIXTURE);
    render(
      <MemoryRouter
        initialEntries={['/years-overview']}
       
      >
        <Routes>
          <Route path="/years-overview" element={<YearsOverview />} />
          <Route path="/years/:year" element={<StubYearDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByRole('heading', { name: 'Jahresübersicht' });
    fireEvent.click(screen.getByRole('link', { name: '2024' }));

    expect(
      await screen.findByText('Jahresansicht für 2024'),
    ).toBeInTheDocument();
  });
});