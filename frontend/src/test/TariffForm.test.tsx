import { describe, expect, it, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import TariffForm from '../pages/TariffForm';
import { metersApi, tariffsApi } from './mocks/api';
import type { Meter } from '../types';

const GAS_METER: Meter = {
  id: 1,
  meter_type: 'gas',
  label: 'Gas-Hauptzähler',
  meter_number: 'G-100',
  unit: 'm³',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

const ELECTRICITY_METER: Meter = {
  id: 2,
  meter_type: 'electricity_import',
  label: 'Strom Bezug',
  meter_number: null,
  unit: 'kWh',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

describe('TariffForm (Neuen Tarifzeitraum hinzufügen)', () => {
  let alertSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.mocked(metersApi.getAll).mockResolvedValue([
      GAS_METER,
      ELECTRICITY_METER,
    ]);
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    localStorage.clear();
  });

  const today = () => new Date().toISOString().split('T')[0];
  const renderPage = () => renderWithProviders(<TariffForm />);
  const submitButton = () =>
    screen.getByRole('button', { name: 'Tarifzeitraum hinzufügen' });

  it('renders all create-mode fields and preselects the first meter', async () => {
    const { container } = renderPage();

    expect(
      screen.getByRole('heading', { name: 'Neuen Tarifzeitraum hinzufügen' }),
    ).toBeInTheDocument();

    // The first meter is auto-selected once the list has loaded; the option
    // text with the resolved type label "Gas" proves the types have loaded.
    await screen.findByText('Gas-Hauptzähler (Gas • m³)');

    const meterSelect = container.querySelector<HTMLSelectElement>(
      '#meter_id',
    )!;
    expect(meterSelect.value).toBe('1');
    expect(
      Array.from(meterSelect.options).map((o) => o.textContent),
    ).toEqual([
      'Gas-Hauptzähler (Gas • m³)',
      'Strom Bezug (Strom Bezug • kWh)',
    ]);
    expect(
      screen.getByText(/Ausgewählter Zähler: Gas-Hauptzähler \(Gas\)/),
    ).toBeInTheDocument();

    const kindSelect = screen.getByLabelText('Tarifart *');
    expect(kindSelect).toHaveValue('consumption');
    expect(
      screen.getByText(
        'Arbeitspreis (mit optionalen Grund- und Messentgelten)',
      ),
    ).toBeInTheDocument();

    // valid_from defaults to today, valid_to is optional.
    expect(screen.getByLabelText('Gültig ab *')).toHaveValue(today());
    expect(screen.getByLabelText('Gültig bis (optional)')).toBeInTheDocument();

    // Default kind consumption + gas meter => gas conversion fields are shown.
    expect(screen.getByLabelText('Preis pro Einheit (€/kWh) *')).toBeInTheDocument();
    expect(screen.getByLabelText('Zustandszahl (z-Zahl) *')).toBeInTheDocument();
    expect(screen.getByLabelText('Brennwert (kWh/m³) *')).toBeInTheDocument();
    expect(screen.getByLabelText('Grundpreis monatlich')).toBeInTheDocument();
    expect(screen.getByLabelText('Messentgelt monatlich')).toBeInTheDocument();
    expect(screen.getByLabelText('Anbieter / Kommentar')).toBeInTheDocument();
    expect(submitButton()).toBeInTheDocument();
  });

  it('submits a complete gas tariff and calls tariffsApi.create with the correct payload', async () => {
    renderPage();
    await screen.findByLabelText('Zähler *');

    fireEvent.change(screen.getByLabelText('Preis pro Einheit (€/kWh) *'), {
      target: { value: '0.08450' },
    });
    fireEvent.change(screen.getByLabelText('Zustandszahl (z-Zahl) *'), {
      target: { value: '0.96280' },
    });
    fireEvent.change(screen.getByLabelText('Brennwert (kWh/m³) *'), {
      target: { value: '11.42500' },
    });
    fireEvent.change(screen.getByLabelText('Grundpreis monatlich'), {
      target: { value: '12.50' },
    });
    fireEvent.change(screen.getByLabelText('Messentgelt monatlich'), {
      target: { value: '5.80' },
    });
    fireEvent.change(screen.getByLabelText('Gültig bis (optional)'), {
      target: { value: '2025-12-31' },
    });
    fireEvent.change(screen.getByLabelText('Anbieter / Kommentar'), {
      target: { value: 'Stadtwerke Musterstadt' },
    });

    fireEvent.click(submitButton());

    await waitFor(() => expect(tariffsApi.create).toHaveBeenCalledTimes(1));
    expect(tariffsApi.create).toHaveBeenCalledWith({
      meter_id: 1,
      tariff_kind: 'consumption',
      valid_from: today(),
      price_per_unit: '0.08450',
      valid_to: '2025-12-31',
      gas_z_zahl: '0.96280',
      gas_brennwert: '11.42500',
      base_fee_monthly: '12.50',
      metering_fee_monthly: '5.80',
      comment: 'Stadtwerke Musterstadt',
    });

    expect(
      await screen.findByText('Tarifzeitraum hinzugefügt!'),
    ).toBeInTheDocument();
  });

  it('omits optional fields from the payload when left empty', async () => {
    renderPage();
    await screen.findByLabelText('Zähler *');

    // Switch to the electricity meter so only the price is required.
    fireEvent.change(screen.getByLabelText('Zähler *'), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByLabelText('Preis pro Einheit (€/kWh) *'), {
      target: { value: '1.20' },
    });

    fireEvent.click(submitButton());

    await waitFor(() => expect(tariffsApi.create).toHaveBeenCalledTimes(1));
    expect(tariffsApi.create).toHaveBeenCalledWith({
      meter_id: 2,
      tariff_kind: 'consumption',
      valid_from: today(),
      price_per_unit: '1.20',
    });
  });

  it('blocks submission via alert when a meter-type-specific required field is empty', async () => {
    const { container } = renderPage();
    await screen.findByLabelText('Zähler *');

    // Gas meter preselected; price filled but gas conversion fields missing.
    // fireEvent.submit bypasses native HTML5 constraint validation (jsdom),
    // so the component's own required-field guard in handleSubmit runs.
    fireEvent.change(screen.getByLabelText('Preis pro Einheit (€/kWh) *'), {
      target: { value: '0.08450' },
    });
    fireEvent.submit(container.querySelector('form')!);

    expect(alertSpy).toHaveBeenCalledWith('Bitte alle Pflichtfelder ausfüllen');
    expect(tariffsApi.create).not.toHaveBeenCalled();
  });

  it('blocks submission via alert when the price is missing', async () => {
    const { container } = renderPage();
    await screen.findByLabelText('Zähler *');

    fireEvent.submit(container.querySelector('form')!);

    expect(alertSpy).toHaveBeenCalledWith('Bitte alle Pflichtfelder ausfüllen');
    expect(tariffsApi.create).not.toHaveBeenCalled();
  });

  it('shows the EEG 2009 fee box for the feed_in_eeg2009 kind and submits the tier rates', async () => {
    renderPage();
    await screen.findByLabelText('Zähler *');

    fireEvent.change(screen.getByLabelText('Tarifart *'), {
      target: { value: 'feed_in_eeg2009' },
    });

    expect(
      screen.getByText('EEG 2009 Vergütungssätze'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Dieser Tarif muss auf dem Einspeise-Zähler (Strom Einspeisung) angelegt werden, nicht auf dem Erzeugungszähler.',
      ),
    ).toBeInTheDocument();

    // Standard consumption fields are replaced by the EEG rates.
    expect(
      screen.getByLabelText('Grundvergütungssatz (€/kWh) *'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Abzug Eigenverbrauch bis 30 % (€/kWh) *'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Abzug Eigenverbrauch über 30 % (€/kWh) *'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Messstellenbetrieb (€/Jahr) *'),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText('Grundpreis monatlich'),
    ).not.toBeInTheDocument();

    fireEvent.change(
      screen.getByLabelText('Grundvergütungssatz (€/kWh) *'),
      { target: { value: '0.10' } },
    );
    fireEvent.change(
      screen.getByLabelText('Abzug Eigenverbrauch bis 30 % (€/kWh) *'),
      { target: { value: '0.05' } },
    );
    fireEvent.change(
      screen.getByLabelText('Abzug Eigenverbrauch über 30 % (€/kWh) *'),
      { target: { value: '0.02' } },
    );
    fireEvent.change(
      screen.getByLabelText('Messstellenbetrieb (€/Jahr) *'),
      { target: { value: '15.00' } },
    );

    fireEvent.click(submitButton());

    await waitFor(() => expect(tariffsApi.create).toHaveBeenCalledTimes(1));
    expect(tariffsApi.create).toHaveBeenCalledWith({
      meter_id: 1,
      tariff_kind: 'feed_in_eeg2009',
      valid_from: today(),
      price_per_unit: '0.10',
      eeg_tier1_rate: '0.05',
      eeg_tier2_rate: '0.02',
      metering_point_fee_yearly: '15.00',
    });
  });

  it('shows the backend error detail in an alert when creating fails', async () => {
    vi.mocked(tariffsApi.create).mockRejectedValue({
      response: {
        data: {
          detail:
            'Zeitraum überschneidet sich mit einem bestehenden Tarif derselben Art',
        },
      },
    });
    renderPage();
    await screen.findByLabelText('Zähler *');

    fireEvent.change(screen.getByLabelText('Preis pro Einheit (€/kWh) *'), {
      target: { value: '0.08450' },
    });
    fireEvent.change(screen.getByLabelText('Zustandszahl (z-Zahl) *'), {
      target: { value: '0.96280' },
    });
    fireEvent.change(screen.getByLabelText('Brennwert (kWh/m³) *'), {
      target: { value: '11.42500' },
    });
    fireEvent.click(submitButton());

    await waitFor(() =>
      expect(alertSpy).toHaveBeenCalledWith(
        'Zeitraum überschneidet sich mit einem bestehenden Tarif derselben Art',
      ),
    );
  });

  it('shows an empty state and disables the submit button when no meters exist', async () => {
    vi.mocked(metersApi.getAll).mockResolvedValue([]);
    renderPage();

    expect(
      await screen.findByText(
        'Keine Zähler vorhanden. Bitte zuerst einen Zähler anlegen.',
      ),
    ).toBeInTheDocument();
    expect(submitButton()).toBeDisabled();
  });
});