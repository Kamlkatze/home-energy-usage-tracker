import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import CustomRange from '../../pages/CustomRange';
import { costsApi, electricityApi } from '../mocks/api';

describe('CustomRange page', () => {
  it('renders without throwing and shows the filter form', async () => {
    renderWithProviders(<CustomRange />);
    expect(screen.getByText('Individueller Zeitraum')).toBeInTheDocument();
    expect(screen.getByLabelText('Von')).toBeInTheDocument();
    expect(await screen.findByText('Anwenden')).toBeInTheDocument();
  });

  it('shows the empty state for every active area', async () => {
    renderWithProviders(<CustomRange />);
    expect(
      await screen.findAllByText(/Keine Messpunkte im gew\u00e4hlten Zeitraum/)
    ).toHaveLength(3);
  });

  it('renders one table per meter, labelling feed-in/generation as Vergütung and others as Kosten', async () => {
    const meter = (id: number, label: string, meter_type: 'electricity_export' | 'electricity_production' | 'electricity_import', cost: string | null) => ({
      meter_id: id,
      meter_label: label,
      meter_type,
      unit: 'kWh',
      points: [{
        date: '2025-04-01',
        value: '1000.000',
        consumption_since_previous: '100.000',
        cost_since_previous: cost,
      }],
    });
    vi.mocked(costsApi.getConsumptionTimeseries).mockResolvedValue([
      meter(1, 'Strom Einspeisung', 'electricity_export', '60.31'),
      meter(2, 'Strom Erzeugung', 'electricity_production', '75.60'),
      meter(3, 'Strom Bezug', 'electricity_import', '88.00'),
    ]);
    vi.mocked(electricityApi.getFeedInCompensation).mockResolvedValue({
      production_meter_id: 2,
      export_meter_id: 1,
      from_date: '2025-01-01',
      to_date: '2025-12-31',
      production_consumption: '900.000',
      export_consumption: '300.000',
      self_consumption: '600.000',
      tier1_kwh: '270.000',
      tier2_kwh: '330.000',
      total_compensation: '50.25',
      gross_compensation: '54.50',
      metering_point_fee_deducted: '4.25',
    });

    renderWithProviders(<CustomRange />);

    expect(await screen.findByText('Strom Einspeisung')).toBeInTheDocument();
    expect(screen.getByText('Strom Erzeugung')).toBeInTheDocument();
    expect(screen.getByText('Strom Bezug')).toBeInTheDocument();
    expect(screen.getAllByText('Verg\u00fctung')).toHaveLength(2);
    expect(screen.getAllByText('Kosten')).toHaveLength(1);
    expect(
      screen.getAllByText(
        'Verg\u00fctungsberechnung nur f\u00fcr fixe Verg\u00fctungsmodelle (fester Satz)'
      )
    ).toHaveLength(2);
    expect(screen.getByText('EEG-Einspeiseverg\u00fctung (EEG 2009)')).toBeInTheDocument();
    expect(await screen.findByText('50.25 \u20AC')).toBeInTheDocument();
    expect(screen.getByText('Verg\u00fctung (brutto): 54.50 \u20AC')).toBeInTheDocument();
    expect(screen.getByText('abz\u00fcglich Messstellenbetrieb: \u22124.25 \u20AC')).toBeInTheDocument();
  });
});
