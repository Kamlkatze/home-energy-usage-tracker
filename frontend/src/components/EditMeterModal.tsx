import React, { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Dialog } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectItem } from './ui/select';
import { metersApi } from '../api/client';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter } from '../types';
import { Loader2 } from 'lucide-react';

interface EditMeterModalProps {
  meter: Meter | null;
  allMeters: Meter[];
  onClose: () => void;
  onSaved: () => void;
}

const EditMeterModal: React.FC<EditMeterModalProps> = ({ meter, allMeters, onClose, onSaved }) => {
  const meterTypes = useMeterTypes();
  const [label, setLabel] = useState('');
  const [meterNumber, setMeterNumber] = useState('');
  const [replacesMeterId, setReplacesMeterId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (meter) {
      setLabel(meter.label);
      setMeterNumber(meter.meter_number ?? '');
      setReplacesMeterId(meter.replaces_meter_id?.toString() ?? '');
    }
  }, [meter]);

  const replacedMeterIds = new Set(
    allMeters
      .filter((m) => m.replaces_meter_id !== null && m.id !== (meter?.id ?? -1))
      .map((m) => m.replaces_meter_id as number)
  );
  const currentPredecessorId = meter?.replaces_meter_id ?? null;
  const eligiblePredecessors = allMeters.filter(
    (m) =>
      m.meter_type === meter?.meter_type &&
      (currentPredecessorId === m.id || !replacedMeterIds.has(m.id))
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!meter) return;

    if (!label.trim()) {
      setError('Bitte einen Namen angeben.');
      return;
    }

    try {
      setSaving(true);
      setError(null);

      const payload: Record<string, unknown> = {
        label: label.trim(),
        meter_number: meterNumber.trim() || null,
      };

      if (replacesMeterId !== '') {
        payload.replaces_meter_id = parseInt(replacesMeterId, 10);
      } else {
        payload.replaces_meter_id = null;
      }

      await metersApi.update(meter.id, payload);
      onSaved();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Fehler beim Speichern des Zählers. Bitte erneut versuchen.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!meter} onOpenChange={(open) => { if (!open) onClose(); }}>
      {meter && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <h2 className="text-lg font-semibold">Zähler bearbeiten</h2>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="edit-label">Name</Label>
            <Input
              id="edit-label"
              type="text"
              required
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-meter-number">Zählernummer</Label>
            <Input
              id="edit-meter-number"
              type="text"
              value={meterNumber}
              onChange={(e) => setMeterNumber(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label>Zählertyp</Label>
            <p className="text-lg">{meterTypeLabel(meterTypes, meter.meter_type)}</p>
          </div>

          <div className="space-y-2">
            <Label>Einheit</Label>
            <p className="text-lg">{meter.unit}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-replaces">Vorgänger-Zähler</Label>
            <Select
              id="edit-replaces"
              value={replacesMeterId}
              onChange={(e) => setReplacesMeterId(e.target.value)}
            >
              <SelectItem value="">— Kein Vorgänger —</SelectItem>
              {eligiblePredecessors.map((m) => (
                <SelectItem key={m.id} value={m.id.toString()}>
                  #{m.id} {m.label}
                  {m.meter_number ? ` (${m.meter_number})` : ''}
                </SelectItem>
              ))}
            </Select>
          </div>

          <div className="flex justify-end gap-4 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Abbrechen
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Speichern...
                </>
              ) : (
                'Speichern'
              )}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
};

export default EditMeterModal;