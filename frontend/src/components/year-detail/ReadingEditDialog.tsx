import React, { useState } from 'react';
import { Reading } from '../../types';
import { readingsApi } from '../../api/client';
import { Dialog } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Loader2, AlertTriangle } from 'lucide-react';

interface ReadingEditDialogProps {
  reading: Reading | null;
  unit: string;
  onClose: () => void;
  onSaved: () => void;
}

const ReadingEditDialog: React.FC<ReadingEditDialogProps> = ({ reading, unit, onClose, onSaved }) => {
  const [date, setDate] = useState('');
  const [value, setValue] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (reading) {
      setDate(reading.reading_date);
      setValue(reading.value);
      setNote(reading.note ?? '');
      setShowDeleteConfirm(false);
      setError(null);
    }
  }, [reading]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reading) return;

    if (!date || !value) {
      setError('Datum und Wert sind erforderlich.');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const payload: Record<string, unknown> = {
        reading_date: date,
        value: value,
      };
      if (note !== (reading.note ?? '')) {
        payload.note = note.trim() || null;
      }
      await readingsApi.update(reading.id, payload);
      onSaved();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Fehler beim Speichern des Zählerstands. Bitte erneut versuchen.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!reading) return;

    try {
      setDeleting(true);
      setError(null);
      await readingsApi.delete(reading.id);
      onSaved();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Fehler beim Löschen des Zählerstands. Bitte erneut versuchen.');
      }
      setDeleting(false);
    }
  };

  return (
    <Dialog open={!!reading} onOpenChange={(open) => { if (!open) onClose(); }}>
      {reading && (
        <div className="space-y-4">
          {!showDeleteConfirm ? (
            <form onSubmit={handleSave} className="space-y-4">
              <h2 className="text-lg font-semibold">Zählerstand bearbeiten</h2>

              {error && (
                <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="edit-reading-date">Datum</Label>
                <Input
                  id="edit-reading-date"
                  type="date"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-reading-value">Wert ({unit})</Label>
                <Input
                  id="edit-reading-value"
                  type="number"
                  step="0.001"
                  required
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-reading-note">Notiz</Label>
                <Input
                  id="edit-reading-note"
                  type="text"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={500}
                />
              </div>

              <div className="flex justify-between pt-2">
                <Button type="button" variant="destructive" onClick={() => setShowDeleteConfirm(true)}>
                  Löschen
                </Button>
                <div className="flex gap-2">
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
              </div>
            </form>
          ) : (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Zählerstand löschen</h2>

              <div className="flex items-start gap-2 text-amber-600 bg-amber-50 dark:bg-amber-950/20 p-3 rounded">
                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                <p className="text-sm">
                  Möchten Sie den Zählerstand vom <strong>{new Date(reading.reading_date).toLocaleDateString()}</strong> mit dem Wert <strong>{value} {unit}</strong> wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.
                </p>
              </div>

              {error && (
                <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                  {error}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowDeleteConfirm(false)} disabled={deleting}>
                  Abbrechen
                </Button>
                <Button type="button" variant="destructive" onClick={handleDelete} disabled={deleting}>
                  {deleting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Löschen...
                    </>
                  ) : (
                    'Löschen'
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
};

export default ReadingEditDialog;