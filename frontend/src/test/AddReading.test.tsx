import { describe, expect, it, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import AddReading from '../pages/AddReading';
import { metersApi, readingsApi } from './mocks/api';
import type { Meter } from '../types';

const TEST_METERS: Meter[] = [
  {
    id: 1,
    meter_type: 'gas',
    label: 'Gas-Hauptzähler',
    meter_number: '123456789',
    unit: 'm³',
    created_at: '2024-01-01T00:00:00Z',
    replaces_meter_id: null,
  },
  {
    id: 2,
    meter_type: 'electricity_import',
    label: 'Strom-Bezugszähler',
    meter_number: null,
    unit: 'kWh',
    created_at: '2024-01-01T00:00:00Z',
    replaces_meter_id: null,
  },
];

// Exact match on the leaf text `<type> • <unit>` (its parent label has more text,
// so a substring/regex match would find two elements).
const typeAndUnit = (text: string) => (content: string) => content === text;

describe('AddReading (Zählerstände eintragen)', () => {
  beforeEach(() => {
    vi.mocked(metersApi.getAll).mockResolvedValue(TEST_METERS);
    vi.mocked(metersApi.getLastReading).mockResolvedValue(null);
    localStorage.clear();
  });

  // Meters are new (not in localStorage.seenIds), so they default to checked.
  const renderPage = () => renderWithProviders(<AddReading />);
  const submitButton = () =>
    screen.getByRole('button', { name: 'Zählerstände speichern' });

  it('renders a date selector and one value/note input block per meter with type and unit labels', async () => {
    const { container } = renderPage();

    expect(await screen.findByLabelText('Datum *')).toBeInTheDocument();

    expect(container.querySelectorAll('input[type="number"]')).toHaveLength(
      TEST_METERS.length,
    );
    expect(container.querySelectorAll('textarea')).toHaveLength(
      TEST_METERS.length,
    );

    for (const meter of TEST_METERS) {
      expect(screen.getByText(meter.label)).toBeInTheDocument();
    }
    expect(screen.getByText(typeAndUnit('(Gas • m³)'))).toBeInTheDocument();
    expect(
      screen.getByText(typeAndUnit('(Strom Bezug • kWh)')),
    ).toBeInTheDocument();
  });

  it('submits the entered value and chosen date for the filled meter only', async () => {
    const { container } = renderPage();
    await screen.findByLabelText('Datum *');

    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-1')!,
      { target: { value: '1234.5' } },
    );
    fireEvent.change(screen.getByLabelText('Datum *'), {
      target: { value: '2025-03-15' },
    });

    fireEvent.click(submitButton());

    await waitFor(() => expect(readingsApi.create).toHaveBeenCalled());
    expect(readingsApi.create).toHaveBeenCalledTimes(1);
    expect(readingsApi.create).toHaveBeenCalledWith({
      meter_id: 1,
      value: 1234.5,
      reading_date: '2025-03-15',
      note: null,
    });

    expect(
      await screen.findByText('Zählerstände gespeichert'),
    ).toBeInTheDocument();
  });

  it('submits all filled meters, including notes, in one payload each', async () => {
    const { container } = renderPage();
    await screen.findByLabelText('Datum *');

    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-1')!,
      { target: { value: '10' } },
    );
    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-2')!,
      { target: { value: '20' } },
    );
    fireEvent.change(container.querySelectorAll('textarea')[0], {
      target: { value: 'Abgelesen am Morgen' },
    });

    fireEvent.click(submitButton());

    await waitFor(() =>
      expect(readingsApi.create).toHaveBeenCalledTimes(2),
    );
    expect(readingsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ meter_id: 1, value: 10, note: 'Abgelesen am Morgen' }),
    );
    expect(readingsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ meter_id: 2, value: 20, note: null }),
    );
  });

  it('disables the submit button until a selected meter has a value', async () => {
    const { container } = renderPage();
    const submit = await screen.findByRole('button', {
      name: 'Zählerstände speichern',
    });

    expect(submit).toBeDisabled();

    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-1')!,
      { target: { value: '55' } },
    );
    expect(submit).toBeEnabled();

    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-1')!,
      { target: { value: '' } },
    );
    expect(submit).toBeDisabled();
  });

  it('shows the backend error message when creating a reading fails', async () => {
    vi.mocked(readingsApi.create).mockRejectedValue({
      response: { data: { detail: 'Zählerstand darf nicht unter dem letzten Wert liegen' } },
    });
    const { container } = renderPage();
    await screen.findByLabelText('Datum *');

    fireEvent.change(
      container.querySelector<HTMLInputElement>('#value-1')!,
      { target: { value: '5' } },
    );
    fireEvent.click(submitButton());

    expect(
      await screen.findByText('Ergebnis der Eingabe'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Fehler: Zählerstand darf nicht unter dem letzten Wert liegen/),
    ).toBeInTheDocument();
  });
});