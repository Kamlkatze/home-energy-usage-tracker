import { describe, expect, it, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import MeterForm from '../pages/MeterForm';
import { metersApi } from './mocks/api';
import type { Meter } from '../types';

// A gas meter that is a valid predecessor for a new gas meter (same type,
// not itself already replaced by another meter).
const EXISTING_GAS_METER: Meter = {
  id: 2,
  meter_type: 'gas',
  label: 'Bestehender Gashauptzähler',
  meter_number: 'GAS-100',
  unit: 'm³',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

// An electricity meter, not eligible as a predecessor of a gas meter.
const EXISTING_ELECTRICITY_METER: Meter = {
  id: 3,
  meter_type: 'electricity_import',
  label: 'Stromzähler Keller',
  meter_number: null,
  unit: 'kWh',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

describe('MeterForm (Neuer Zähler)', () => {
  let alertSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.mocked(metersApi.getAll).mockResolvedValue([
      EXISTING_GAS_METER,
      EXISTING_ELECTRICITY_METER,
    ]);
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    localStorage.clear();
  });

  const renderPage = () => renderWithProviders(<MeterForm />);
  const createButton = () =>
    screen.getByRole('button', { name: 'Zähler erstellen' });

  it('renders all expected fields and the eligible predecessor dropdown', async () => {
    const { container } = renderPage();

    expect(
      screen.getByRole('heading', { name: 'Neuer Zähler' }),
    ).toBeInTheDocument();
    // Types load asynchronously; the first type (gas) is auto-selected.
    await screen.findByText('Gas');

    expect(screen.getByLabelText('Name *')).toBeInTheDocument();
    expect(screen.getByLabelText('Zählernummer')).toBeInTheDocument();
    expect(screen.getByLabelText('Zählertyp *')).toBeInTheDocument();
    expect(createButton()).toBeInTheDocument();

    // Unit is derived from the selected meter type (gas -> m³).
    expect(screen.getByText('m³')).toBeInTheDocument();

    // Predecessor selector lists the same-type un-replaced meter only.
    const predecessor = container.querySelector<HTMLSelectElement>(
      '#replaces_meter_id',
    )!;
    expect(
      Array.from(predecessor.options).map((o) => o.textContent),
    ).toEqual([
      '— Kein Vorgänger —',
      '#2 Bestehender Gashauptzähler (GAS-100)',
    ]);
  });

  it('submits the form and calls metersApi.create with the correct payload', async () => {
    renderPage();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name *'), {
      target: { value: '  Neuer Wasserzähler  ' },
    });
    fireEvent.change(screen.getByLabelText('Zählernummer'), {
      target: { value: 'W-9-1' },
    });

    fireEvent.click(createButton());

    await waitFor(() => expect(metersApi.create).toHaveBeenCalledTimes(1));
    expect(metersApi.create).toHaveBeenCalledWith({
      meter_type: 'gas',
      label: 'Neuer Wasserzähler',
      meter_number: 'W-9-1',
    });

    expect(
      await screen.findByText('Zähler hinzugefügt!'),
    ).toBeInTheDocument();
  });

  it('submits meter_number as null and no predecessor when empty', async () => {
    renderPage();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name *'), {
      target: { value: 'Ohne Nummer' },
    });

    fireEvent.click(createButton());

    await waitFor(() => expect(metersApi.create).toHaveBeenCalledTimes(1));
    expect(metersApi.create).toHaveBeenCalledWith({
      meter_type: 'gas',
      label: 'Ohne Nummer',
      meter_number: null,
    });
  });

  it('includes the selected predecessor id and current meter type in the payload', async () => {
    const { container } = renderPage();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name *'), {
      target: { value: 'Ersatzzähler' },
    });
    fireEvent.change(
      container.querySelector<HTMLSelectElement>('#replaces_meter_id')!,
      { target: { value: '2' } },
    );

    fireEvent.click(createButton());

    await waitFor(() => expect(metersApi.create).toHaveBeenCalledTimes(1));
    expect(metersApi.create).toHaveBeenCalledWith({
      meter_type: 'gas',
      label: 'Ersatzzähler',
      meter_number: null,
      replaces_meter_id: 2,
    });
  });

  it('shows a validation alert and does not submit when the name is empty', async () => {
    const { container } = renderPage();
    await screen.findByText('Gas');

    fireEvent.submit(container.querySelector('form')!);

    expect(alertSpy).toHaveBeenCalledWith('Bitte alle Pflichtfelder ausfüllen');
    expect(metersApi.create).not.toHaveBeenCalled();
  });

  it('shows an error alert when the API create request fails', async () => {
    vi.mocked(metersApi.create).mockRejectedValue(new Error('network'));
    renderPage();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name *'), {
      target: { value: 'Fehlversuch' },
    });
    fireEvent.click(createButton());

    await waitFor(() =>
      expect(alertSpy).toHaveBeenCalledWith(
        'Fehler beim Erstellen des Zählers. Bitte erneut versuchen.',
      ),
    );
  });
});