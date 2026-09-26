import { describe, expect, it, beforeEach, vi } from 'vitest';
import { useState } from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import EditMeterModal from '../components/EditMeterModal';
import { metersApi } from './mocks/api';
import type { Meter } from '../types';

// Harness that mirrors MeterList's ownership: onClose/onSaved reset the edited
// meter to null, which (via open={!!meter}) closes the modal.
const Harness = ({
  meter,
  allMeters,
  onSaved,
}: {
  meter: Meter | null;
  allMeters: Meter[];
  onSaved?: () => void;
}) => {
  const [current, setCurrent] = useState<Meter | null>(meter);
  return (
    <EditMeterModal
      meter={current}
      allMeters={allMeters}
      onClose={() => setCurrent(null)}
      onSaved={() => {
        onSaved?.();
        setCurrent(null);
      }}
    />
  );
};

// A gas meter whose predecessors are editable; has a current predecessor #5.
const EDITED_GAS_METER: Meter = {
  id: 1,
  meter_type: 'gas',
  label: 'Heizung',
  meter_number: 'G-77',
  unit: 'm³',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: 5,
};

// Same type, currently replacing this meter -> the current predecessor.
const CURRENT_PREDECESSOR: Meter = {
  id: 5,
  meter_type: 'gas',
  label: 'Alter Gashauptzähler',
  meter_number: 'G-50',
  unit: 'm³',
  created_at: '2023-01-01T00:00:00Z',
  replaces_meter_id: null,
};

// Same type, un-replaced -> still eligible as a predecessor.
const ELIGIBLE_GAS_METER: Meter = {
  id: 2,
  meter_type: 'gas',
  label: 'Ersatzreserve',
  meter_number: null,
  unit: 'm³',
  created_at: '2024-02-01T00:00:00Z',
  replaces_meter_id: null,
};

// Same type but already used as predecessor of another meter -> ineligible.
const REPLACED_GAS_METER: Meter = {
  id: 4,
  meter_type: 'gas',
  label: 'Schon ersetzt',
  meter_number: 'G-4',
  unit: 'm³',
  created_at: '2024-03-01T00:00:00Z',
  replaces_meter_id: null,
};
const SUCCESSOR_OF_REPLACED: Meter = {
  id: 6,
  meter_type: 'gas',
  label: 'Nachfolger',
  meter_number: 'G-6',
  unit: 'm³',
  created_at: '2024-04-01T00:00:00Z',
  replaces_meter_id: 4,
};

// Different type -> ineligible regardless of replace state.
const ELECTRICITY_METER: Meter = {
  id: 3,
  meter_type: 'electricity_import',
  label: 'Stromzähler',
  meter_number: 'E-1',
  unit: 'kWh',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

const ALL_METERS = [
  EDITED_GAS_METER,
  CURRENT_PREDECESSOR,
  ELIGIBLE_GAS_METER,
  REPLACED_GAS_METER,
  SUCCESSOR_OF_REPLACED,
  ELECTRICITY_METER,
];

describe('EditMeterModal', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const renderModal = (overrides: {
    onClose?: () => void;
    onSaved?: () => void;
  } = {}) =>
    renderWithProviders(
      <EditMeterModal
        meter={EDITED_GAS_METER}
        allMeters={ALL_METERS}
        onClose={overrides.onClose ?? vi.fn()}
        onSaved={overrides.onSaved ?? vi.fn()}
      />,
    );

  const predecessorSelect = (container: HTMLElement) =>
    container.querySelector<HTMLSelectElement>('#edit-replaces')!;

  it('renders nothing when no meter is selected', () => {
    const { container } = renderWithProviders(
      <EditMeterModal meter={null} allMeters={ALL_METERS} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(container.querySelector('form')).toBeNull();
    expect(
      screen.queryByRole('heading', { name: 'Zähler bearbeiten' }),
    ).not.toBeInTheDocument();
  });

  it('pre-fills all editable fields and shows read-only type and unit', async () => {
    const { container } = renderModal();

    await screen.findByText('Gas');
    expect(
      screen.getByRole('heading', { name: 'Zähler bearbeiten' }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText('Name')).toHaveValue('Heizung');
    expect(screen.getByLabelText('Zählernummer')).toHaveValue('G-77');
    // The current predecessor is preselected (value "5").
    expect(predecessorSelect(container)).toHaveValue('5');

    // Read-only fields.
    expect(screen.getByText('Zählertyp')).toBeInTheDocument();
    expect(screen.getByText('Gas')).toBeInTheDocument();
    expect(screen.getByText('Einheit')).toBeInTheDocument();
    expect(screen.getByText('m³')).toBeInTheDocument();

    // Predecessor list: only same-type, not-already-replaced meters (plus the
    // current predecessor); electricity and already-replaced meters excluded.
    const options = Array.from(predecessorSelect(container).options).map(
      (o) => o.textContent,
    );
    expect(options).toContain('#5 Alter Gashauptzähler (G-50)');
    expect(options).toContain('#2 Ersatzreserve');
    expect(options).not.toContain('#3 Stromzähler (E-1)');
    expect(options).not.toContain('#4 Schon ersetzt (G-4)');
  });

  it('never offers the edited meter itself as its own predecessor', async () => {
    const { container } = renderModal();
    await screen.findByText('Gas');

    const options = Array.from(predecessorSelect(container).options).map(
      (o) => o.textContent,
    );
    expect(options).not.toContain('#1 Heizung (G-77)');
    // Other same-type meters stay available as predecessors.
    expect(options).toContain('#5 Alter Gashauptzähler (G-50)');
    expect(options).toContain('#2 Ersatzreserve');
  });

  it('submits with the correct meter id and trims the payload', async () => {
    const onSaved = vi.fn();
    renderModal({ onSaved });
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: '  Neuer Name  ' },
    });
    fireEvent.change(screen.getByLabelText('Zählernummer'), {
      target: { value: 'G-88' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

    await waitFor(() => expect(metersApi.update).toHaveBeenCalledTimes(1));
    expect(metersApi.update).toHaveBeenCalledWith(1, {
      label: 'Neuer Name',
      meter_number: 'G-88',
      replaces_meter_id: 5,
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it('sends null meter_number and null replaces_meter_id when cleared', async () => {
    const { container } = renderModal();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Ohne Zuordnung' },
    });
    fireEvent.change(screen.getByLabelText('Zählernummer'), {
      target: { value: '' },
    });
    fireEvent.change(predecessorSelect(container), { target: { value: '' } });
    fireEvent.submit(container.querySelector('form')!);

    await waitFor(() => expect(metersApi.update).toHaveBeenCalledTimes(1));
    expect(metersApi.update).toHaveBeenCalledWith(1, {
      label: 'Ohne Zuordnung',
      meter_number: null,
      replaces_meter_id: null,
    });
  });

  it('sets a new predecessor id in the payload', async () => {
    const { container } = renderModal();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Umgehängt' },
    });
    fireEvent.change(predecessorSelect(container), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

    await waitFor(() => expect(metersApi.update).toHaveBeenCalledTimes(1));
    expect(metersApi.update).toHaveBeenCalledWith(1, {
      label: 'Umgehängt',
      meter_number: 'G-77',
      replaces_meter_id: 2,
    });
  });

  it('shows an inline validation error and does not submit when the label is empty', async () => {
    const { container } = renderModal();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: '' } });
    // fireEvent.submit bypasses the native `required` attribute so the
    // component's own guard in handleSubmit runs.
    fireEvent.submit(container.querySelector('form')!);

    expect(screen.getByText('Bitte einen Namen angeben.')).toBeInTheDocument();
    expect(metersApi.update).not.toHaveBeenCalled();
  });

  it('shows the backend detail on failure and keeps the modal open', async () => {
    vi.mocked(metersApi.update).mockRejectedValue({
      response: { data: { detail: 'Zähler mit dieser Nummer existiert bereits' } },
    });
    const onSaved = vi.fn();
    renderModal({ onSaved });
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Konflikt' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

    expect(
      await screen.findByText('Zähler mit dieser Nummer existiert bereits'),
    ).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
    // Modal still open so the user can correct the input.
    expect(
      screen.getByRole('heading', { name: 'Zähler bearbeiten' }),
    ).toBeInTheDocument();
  });

  it('shows the generic error message when the failure has no detail', async () => {
    vi.mocked(metersApi.update).mockRejectedValue(new Error('network'));
    renderModal();
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Fehlversuch' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

    expect(
      await screen.findByText(
        'Fehler beim Speichern des Zählers. Bitte erneut versuchen.',
      ),
    ).toBeInTheDocument();
  });

  it('closes the modal when saving succeeds', async () => {
    const onSaved = vi.fn();
    renderWithProviders(
      <Harness meter={EDITED_GAS_METER} allMeters={ALL_METERS} onSaved={onSaved} />,
    );
    await screen.findByText('Gas');

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Erfolgreich gespeichert' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: 'Zähler bearbeiten' }),
      ).not.toBeInTheDocument(),
    );
  });

  it('closes on cancel without calling the API', async () => {
    renderWithProviders(
      <Harness meter={EDITED_GAS_METER} allMeters={ALL_METERS} />,
    );
    await screen.findByText('Gas');

    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));

    expect(metersApi.update).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: 'Zähler bearbeiten' }),
      ).not.toBeInTheDocument(),
    );
  });
});