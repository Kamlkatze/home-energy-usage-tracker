import { describe, expect, it, vi } from 'vitest';
import { screen, within, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import YearDetail from '../pages/YearDetail';
import {
  costsApi,
  metersApi,
  readingsApi,
  electricityApi,
} from './mocks/api';
import type {
  Meter,
  Reading,
  YearsOverviewItem,
  YearlyProjection,
  FeedInCompensation,
  WastewaterCosts,
} from '../types';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const IMPORT = (id = 1): Meter => ({
  id, meter_type: 'electricity_import', label: 'Strom Bezug',
  meter_number: null, unit: 'kWh', created_at: '2020-01-01T00:00:00Z',
  replaces_meter_id: null,
});
const PROD = (id = 2): Meter => ({
  id, meter_type: 'electricity_production', label: 'PV-Anlage',
  meter_number: null, unit: 'kWh', created_at: '2020-01-01T00:00:00Z',
  replaces_meter_id: null,
});
const EXPORT = (id = 3): Meter => ({
  id, meter_type: 'electricity_export', label: 'Netzeinspeisung',
  meter_number: null, unit: 'kWh', created_at: '2020-01-01T00:00:00Z',
  replaces_meter_id: null,
});
const GAS_OLD = (id = 5): Meter => ({
  id, meter_type: 'gas', label: 'Gas Alter Zähler',
  meter_number: null, unit: 'm³', created_at: '2019-01-01T00:00:00Z',
  replaces_meter_id: null,
});
const GAS_NEW = (id = 4): Meter => ({
  id, meter_type: 'gas', label: 'Gas-Hauptzähler',
  meter_number: null, unit: 'm³', created_at: '2023-01-01T00:00:00Z',
  replaces_meter_id: 5,
});
const COLD = (id = 6): Meter => ({
  id, meter_type: 'water_cold', label: 'Kaltwasser',
  meter_number: null, unit: 'm³', created_at: '2020-06-01T00:00:00Z',
  replaces_meter_id: null,
});
const GARDEN = (id = 7): Meter => ({
  id, meter_type: 'water_garden', label: 'Gartenwasser',
  meter_number: null, unit: 'm³', created_at: '2021-06-01T00:00:00Z',
  replaces_meter_id: null,
});

const ALL_METERS = [
  IMPORT(), PROD(), EXPORT(), GAS_NEW(), GAS_OLD(), COLD(), GARDEN(),
];

const yearEntry = (year: number, consumption: number, cost: number | null = null): YearsOverviewItem['years'] =>
  [{ year, consumption: consumption.toString(), cost: cost != null ? cost.toFixed(2) : null, cost_basis: cost != null ? 'actual' : null }];

const OVERVIEW: YearsOverviewItem[] = [
  { meter_id: 1, meter_label: 'Strom Bezug', meter_type: 'electricity_import', unit: 'kWh', years: yearEntry(2024, 1234.5, 432.1) },
  { meter_id: 2, meter_label: 'PV-Anlage', meter_type: 'electricity_production', unit: 'kWh', years: yearEntry(2024, 4500) },
  { meter_id: 3, meter_label: 'Netzeinspeisung', meter_type: 'electricity_export', unit: 'kWh', years: yearEntry(2024, 2800) },
  { meter_id: 4, meter_label: 'Gas-Hauptzähler', meter_type: 'gas', unit: 'm³', years: yearEntry(2024, 88.8, 120) },
  { meter_id: 6, meter_label: 'Kaltwasser', meter_type: 'water_cold', unit: 'm³', years: yearEntry(2024, 12.3, 20) },
  { meter_id: 7, meter_label: 'Gartenwasser', meter_type: 'water_garden', unit: 'm³', years: yearEntry(2024, 1.2) },
];

const READINGS_BY_METER: Record<number, Reading[]> = {
  1: [{ id: 101, meter_id: 1, value: '1000', reading_date: '2024-03-10', note: 'Stand nach Wechsel', created_at: '2024-03-10T00:00:00Z' }],
  5: [{ id: 501, meter_id: 5, value: '5000', reading_date: '2024-02-15', note: null, created_at: '2024-02-15T00:00:00Z' }],
  4: [{ id: 502, meter_id: 4, value: '5088.8', reading_date: '2024-09-01', note: 'Zählerwechsel', created_at: '2024-09-01T00:00:00Z' }],
  6: [{ id: 601, meter_id: 6, value: '12.3', reading_date: '2024-04-01', note: null, created_at: '2024-04-01T00:00:00Z' }],
  7: [{ id: 701, meter_id: 7, value: '1.2', reading_date: '2024-05-01', note: null, created_at: '2024-05-01T00:00:00Z' }],
};

const IMPORT_PROJ: YearlyProjection = {
  meter_id: 1, year: 2024, unit: 'kWh', as_of_date: '2024-12-01',
  actual_consumption_to_date: '1234.5', projected_annual_consumption: '2500.0',
  projected_meter_reading_end_of_year: '2500.0', start_reading_value: '1000.0',
  start_reading_date: '2024-01-01', basis: 'linear_from_first_reading_of_year',
  actual_cost_to_date: '432.10', projected_annual_cost: '876.00', message: null,
};
const GAS_PROJ: YearlyProjection = {
  meter_id: 4, year: 2024, unit: 'm³', as_of_date: '2024-12-01',
  actual_consumption_to_date: '88.8', projected_annual_consumption: '180.0',
  projected_meter_reading_end_of_year: '5180.0', start_reading_value: '5000.0',
  start_reading_date: '2024-01-01', basis: 'linear_from_prev_year_end',
  actual_cost_to_date: '120.00', projected_annual_cost: '250.00', message: null,
};
const COLD_PROJ: YearlyProjection = {
  meter_id: 6, year: 2024, unit: 'm³', as_of_date: '2024-12-01',
  actual_consumption_to_date: '12.3', projected_annual_consumption: '15.0',
  projected_meter_reading_end_of_year: '15.0', start_reading_value: null,
  start_reading_date: null, basis: 'linear_from_first_reading_of_year',
  actual_cost_to_date: '20.00', projected_annual_cost: '25.00', message: null,
};
const GARDEN_PROJ: YearlyProjection = {
  meter_id: 7, year: 2024, unit: 'm³', as_of_date: '2024-12-01',
  actual_consumption_to_date: '1.2', projected_annual_consumption: '2.0',
  projected_meter_reading_end_of_year: '2.0', start_reading_value: null,
  start_reading_date: null, basis: 'linear_from_first_reading_of_year',
  actual_cost_to_date: null, projected_annual_cost: null, message: null,
};
const PROJECTIONS: Record<number, YearlyProjection | null> = {
  1: IMPORT_PROJ, 2: null, 3: null, 4: GAS_PROJ, 6: COLD_PROJ, 7: GARDEN_PROJ,
};

const EEG: FeedInCompensation = {
  production_meter_id: 2, export_meter_id: 3, from_date: '2024-01-01',
  to_date: '2024-12-31', production_consumption: '4500.000',
  export_consumption: '2800.000', self_consumption: '1700.000',
  tier1_kwh: '1350.000', tier2_kwh: '350.000', total_compensation: '987.65',
  gross_compensation: '995.87', metering_point_fee_deducted: '8.22',
};

const WASTEWATER: WastewaterCosts = {
  water_cold_meter_id: 6, water_garden_meter_id: 7, from_date: '2024-01-01',
  to_date: '2024-12-31', cold_consumption: '12.3', garden_consumption: '1.2',
  wastewater_consumption: '11.100', unit: 'm³', price_per_unit: '2.10000',
  base_fee_total: '12.00', total_cost: '203.10',
};

// Installs mock data so the page renders a complete, successful view.
function installMockData() {
  metersApi.getAll.mockResolvedValue(ALL_METERS);
  costsApi.getYearsOverview.mockResolvedValue(OVERVIEW);
  metersApi.getReadings.mockImplementation(async (id: number) => READINGS_BY_METER[id] ?? []);
  costsApi.getYearlyProjection.mockImplementation(
    async (meterId: number) => PROJECTIONS[meterId] ?? null,
  );
  electricityApi.getFeedInCompensation.mockResolvedValue(EEG);
  electricityApi.getFeedInCompensationProjection.mockResolvedValue(null);
  costsApi.getWastewaterCosts.mockResolvedValue(WASTEWATER);
  costsApi.getAdvancePaymentDiffByCategory.mockResolvedValue(null);
}

function renderYearDetail(year = 2024) {
  return renderWithProviders(<YearDetail />, {
    path: '/years/:year',
    initialEntries: [`/years/${year}`],
  });
}

// Convenience: the border box that represents a single meter block.
function meterBox(label: string): HTMLElement {
  // The label h4 sits inside the header row; climb one level to the block root.
  const headerRow = screen.getByText(label).closest('div') as HTMLElement;
  return headerRow.parentElement as HTMLElement;
}

// Convenience: open the edit dialog for the imported meter's single reading.
async function openImportReadingDialog() {
  await screen.findByRole('heading', { name: 'Jahresdetail: 2024' });
  const importBox = meterBox('Strom Bezug');
  const row = within(importBox).getByText('Stand nach Wechsel').closest('tr') as HTMLElement;
  fireEvent.click(within(row).getByTitle('Bearbeiten'));
  await screen.findByRole('heading', { name: 'Zählerstand bearbeiten' });
}

describe('YearDetail', () => {
  describe('states', () => {
    it('renders the loading state while the initial request is pending', () => {
      vi.mocked(costsApi.getYearsOverview).mockImplementation(() => new Promise(() => {}));
      renderYearDetail();
      expect(screen.getByText('Lade Jahresdaten...')).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Jahresdetail: 2024' }),
      ).not.toBeInTheDocument();
    });

    it('shows the backend detail message on error', async () => {
      vi.mocked(costsApi.getYearsOverview).mockRejectedValue({
        response: { data: { detail: 'Interner Serverfehler' } },
      });
      renderYearDetail();
      expect(await screen.findByText('Interner Serverfehler')).toBeInTheDocument();
      expect(
        screen.getByRole('link', { name: 'Zurück zur Jahresübersicht' }),
      ).toHaveAttribute('href', '/years-overview');
    });

    it('shows the empty state when no meters have data for the year', async () => {
      renderYearDetail();
      expect(
        await screen.findByText('Keine Zählerdaten für das Jahr 2024 vorhanden.'),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Jahresdetail: 2024' }),
      ).not.toBeInTheDocument();
    });
  });

  describe('successful render', () => {
    it('renders all category sections with correct values', async () => {
      installMockData();
      renderYearDetail();

      expect(
        await screen.findByRole('heading', { name: 'Jahresdetail: 2024' }),
      ).toBeInTheDocument();

      // Section cards for electricity (import+prod+export), water, gas.
      expect(screen.getByRole('heading', { name: 'Strom 2024' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Wasser 2024' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Gas 2024' })).toBeInTheDocument();

      // Import meter: real consumption + cost projection values.
      expect(await screen.findByText('876.00 €')).toBeInTheDocument(); // import projected cost
      expect(screen.getByText('432.10 €')).toBeInTheDocument();        // import actual cost
      expect(screen.getAllByText('1235 kWh').length).toBeGreaterThan(0);
      expect(screen.getAllByText('2500 kWh').length).toBeGreaterThan(0); // import projected consumption

      // Gas meter: chain note + projected cost.
      expect(
        screen.getByText('Ersetzungskette: Gas Alter Zähler → Gas-Hauptzähler'),
      ).toBeInTheDocument();
      expect(screen.getByText('250.00 €')).toBeInTheDocument();        // gas projected cost
      expect(screen.getAllByText('88.8 m³').length).toBeGreaterThan(0);

      // Water: actual + projected wastewater consumption and costs.
      expect(screen.getAllByText('11.1 m³').length).toBeGreaterThan(0); // wastewater actual
      expect(screen.getAllByText('13.0 m³').length).toBeGreaterThan(0); // wastewater projected
      expect(screen.getAllByText('203.10 €').length).toBeGreaterThan(0); // wastewater total cost
    });

    it('renders the EEG 2009 breakdown (raw backend tier values, no client math)', async () => {
      installMockData();
      renderYearDetail();

      const eegCard = await screen.findByText('EEG-Einspeisevergütung');
      const card = eegCard.closest('div') as HTMLElement;

      expect(within(card).getByText('4500 kWh')).toBeInTheDocument();  // production (P)
      expect(within(card).getByText('2800 kWh')).toBeInTheDocument();  // export (E)
      expect(within(card).getByText('1700 kWh')).toBeInTheDocument();  // self-consumption
      expect(
        within(card).getByText('Tier 1: 1350.0 • Tier 2: 350 kWh'),
      ).toBeInTheDocument();
      expect(within(card).getByText('987.65 €')).toBeInTheDocument();  // total compensation
      expect(within(card).getByText('Vergütung (brutto): 995.87 €')).toBeInTheDocument();  // gross
      expect(
        within(card).getByText('abzüglich Messstellenbetrieb: −8.22 €'),  // metering fee deduction
      ).toBeInTheDocument();
    });
  });

  describe('meter-chain replacement (Zählerwechsel)', () => {
    it('merges and sorts readings from the full chain into one block', async () => {
      installMockData();
      renderYearDetail();
      await screen.findByRole('heading', { name: 'Jahresdetail: 2024' });

      // The gas section is a single block that carries the chain note.
      const gasBox = meterBox('Gas-Hauptzähler');
      expect(
        within(gasBox).getByText('Ersetzungskette: Gas Alter Zähler → Gas-Hauptzähler'),
      ).toBeInTheDocument();

      // Rows are merged from both meters (id 5 + id 4) and sorted by date.
      const rows = within(gasBox).getAllByRole('row');
      expect(rows).toHaveLength(3); // header + 2 readings
      expect(rows[1].textContent).toContain('5000');      // Feb reading (old meter)
      expect(rows[1].textContent).not.toContain('5088.8');
      expect(rows[2].textContent).toContain('5088.8');    // Sep reading (new meter)
      expect(rows[2].textContent).toContain('Zählerwechsel');
    });
  });

  describe('reading edit dialog', () => {
    it('opens the edit dialog (not a direct delete) when the trash icon is used', async () => {
      installMockData();
      renderYearDetail();
      await screen.findByRole('heading', { name: 'Jahresdetail: 2024' });

      const importBox = meterBox('Strom Bezug');
      const row = within(importBox).getByText('Stand nach Wechsel').closest('tr') as HTMLElement;
      fireEvent.click(within(row).getByTitle('Löschen'));

      expect(
        await screen.findByRole('heading', { name: 'Zählerstand bearbeiten' }),
      ).toBeInTheDocument();
      expect(readingsApi.delete).not.toHaveBeenCalled();
    });

    it('pre-fills the selected reading and saves the correct payload', async () => {
      installMockData();
      readingsApi.update.mockResolvedValue({});
      renderYearDetail();
      await openImportReadingDialog();

      // Pre-filled values.
      const dateInput = screen.getByLabelText('Datum') as HTMLInputElement;
      const valueInput = screen.getByLabelText('Wert (kWh)') as HTMLInputElement;
      const noteInput = screen.getByLabelText('Notiz') as HTMLInputElement;
      expect(dateInput.value).toBe('2024-03-10');
      expect(valueInput.value).toBe('1000');
      expect(noteInput.value).toBe('Stand nach Wechsel');

      // Edit and submit.
      const readingsFor1Before = metersApi.getReadings.mock.calls.filter((c) => c[0] === 1).length;
      fireEvent.change(valueInput, { target: { value: '1250.5' } });
      fireEvent.change(noteInput, { target: { value: 'Neue Notiz' } });
      fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

      await waitFor(() =>
        expect(readingsApi.update).toHaveBeenCalledWith(101, {
          reading_date: '2024-03-10',
          value: '1250.5',
          note: 'Neue Notiz',
        }),
      );

      // Success closes the dialog and triggers a refetch of the section.
      await waitFor(() =>
        expect(screen.queryByRole('heading', { name: 'Zählerstand bearbeiten' })).toBeNull(),
      );
      const readingsFor1After = metersApi.getReadings.mock.calls.filter((c) => c[0] === 1).length;
      expect(readingsFor1After).toBe(readingsFor1Before + 1);
    });

    it('shows the backend detail message when saving fails', async () => {
      installMockData();
      readingsApi.update.mockRejectedValue({
        response: { data: { detail: 'Zählerstand darf nicht unter dem letzten Wert liegen' } },
      });
      renderYearDetail();
      await openImportReadingDialog();

      fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

      expect(
        await screen.findByText('Zählerstand darf nicht unter dem letzten Wert liegen'),
      ).toBeInTheDocument();
      // Dialog stays open to let the user correct the input.
      expect(
        screen.getByRole('heading', { name: 'Zählerstand bearbeiten' }),
      ).toBeInTheDocument();
    });

    it('deletes the reading after confirmation and refreshes the section', async () => {
      installMockData();
      readingsApi.delete.mockResolvedValue({});
      renderYearDetail();
      await openImportReadingDialog();

      const editWrapper = screen.getByRole('heading', { name: 'Zählerstand bearbeiten' }).closest('div') as HTMLElement;
      fireEvent.click(within(editWrapper).getByRole('button', { name: 'Löschen' }));

      // Confirmation view.
      const confirmWrapper = await screen.findByRole('heading', { name: 'Zählerstand löschen' }).then((h) => h.closest('div')) as HTMLElement;
      expect(within(confirmWrapper).getByText(/Möchten Sie den Zählerstand vom/)).toBeInTheDocument();

      const readingsFor1Before = metersApi.getReadings.mock.calls.filter((c) => c[0] === 1).length;
      fireEvent.click(within(confirmWrapper).getByRole('button', { name: 'Löschen' }));

      await waitFor(() => expect(readingsApi.delete).toHaveBeenCalledWith(101));
      await waitFor(() =>
        expect(screen.queryByRole('heading', { name: 'Zählerstand löschen' })).toBeNull(),
      );
      const readingsFor1After = metersApi.getReadings.mock.calls.filter((c) => c[0] === 1).length;
      expect(readingsFor1After).toBe(readingsFor1Before + 1);
    });
  });

  describe('consumption toggle', () => {
    it('switches a meter block between cumulative and raw meter-value mode', async () => {
      installMockData();
      renderYearDetail();
      await screen.findByRole('heading', { name: 'Jahresdetail: 2024' });

      const importBox = meterBox('Strom Bezug');
      expect(
        within(importBox).getByText('Verbrauch seit 01.01. 2024'),
      ).toBeInTheDocument();
      expect(within(importBox).queryByText('Zählerstand 2024')).toBeNull();

      fireEvent.click(within(importBox).getByRole('button', { name: 'seit 01.01.' }));

      expect(within(importBox).getByText('Zählerstand 2024')).toBeInTheDocument();
      expect(
        within(importBox).queryByText('Verbrauch seit 01.01. 2024'),
      ).toBeNull();
    });
  });
});