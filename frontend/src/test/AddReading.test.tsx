import { describe, expect, it, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
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
    for (const meter of TEST_METERS) {
      expect(
        container.querySelector<HTMLInputElement>(`#note-${meter.id}`),
      ).toBeInTheDocument();
    }

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
    fireEvent.change(
      container.querySelector<HTMLInputElement>('#note-1')!,
      { target: { value: 'Abgelesen am Morgen' } },
    );

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

  it('moves a meter up with the move buttons and persists the new order', async () => {
    const { container } = renderPage();
    await screen.findByText('Gas-Hauptzähler');

    const rows = () =>
      Array.from(container.querySelectorAll<HTMLElement>('tbody tr'));
    const rowFor = (label: string) =>
      rows().find(r => r.textContent?.includes(label))!;

    // Initial order follows the API: Gas first, Strom second.
    expect(rows()[0].textContent).toContain('Gas-Hauptzähler');
    expect(rows()[1].textContent).toContain('Strom-Bezugszähler');

    const upButton = within(rowFor('Strom-Bezugszähler')).getByRole('button', {
      name: 'Nach oben',
    });
    fireEvent.click(upButton);

    // Strom-Bezugszähler is now the first row and the order was persisted.
    expect(rows()[0].textContent).toContain('Strom-Bezugszähler');
    expect(rows()[1].textContent).toContain('Gas-Hauptzähler');
    expect(localStorage.getItem('reading-form-meter-order')).toBe(
      JSON.stringify([2, 1]),
    );

    // The first row's up button is disabled at the top edge.
    expect(
      within(rows()[0]).getByRole('button', { name: 'Nach oben' }),
    ).toBeDisabled();
    // The last row's down button is disabled at the bottom edge.
    expect(
      within(rows()[1]).getByRole('button', { name: 'Nach unten' }),
    ).toBeDisabled();
  });

  it('restores a previously saved meter order on load', async () => {
    localStorage.setItem('reading-form-meter-order', JSON.stringify([2, 1]));
    const { container } = renderPage();

    await screen.findByText('Strom-Bezugszähler');
    const rows = Array.from(
      container.querySelectorAll<HTMLElement>('tbody tr'),
    );

    expect(rows[0].textContent).toContain('Strom-Bezugszähler');
    expect(rows[1].textContent).toContain('Gas-Hauptzähler');
  });

  it('rounds the last reading to whole kWh for electricity and 3 decimals for m³', async () => {
    vi.mocked(metersApi.getLastReading).mockImplementation((meterId: number) => {
      if (meterId === 1) {
        return Promise.resolve({
          id: 11,
          meter_id: 1,
          value: '123.4567',
          reading_date: '2025-03-01',
          note: null,
        });
      }
      return Promise.resolve({
        id: 12,
        meter_id: 2,
        value: '12345.67',
        reading_date: '2025-03-01',
        note: null,
      });
    });

    const { container } = renderPage();
    await screen.findByText('Gas-Hauptzähler');

    const gasRow = Array.from(container.querySelectorAll('tbody tr')).find(r =>
      r.textContent?.includes('Gas-Hauptzähler'),
    )!;
    expect(gasRow.textContent).toContain('123.457 m³');

    const stromRow = Array.from(container.querySelectorAll('tbody tr')).find(r =>
      r.textContent?.includes('Strom-Bezugszähler'),
    )!;
    expect(stromRow.textContent).toContain('12346 kWh');
  });
});