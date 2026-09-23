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

interface ReadingEditFormProps {
  reading: Reading;
  unit: string;
  onClose: () => void;
  onSaved: () => void;
}

// Inner form rendered with key={reading.id}, so it is freshly mounted for
// every selected reading. The form state is therefore initialized from the
// props instead of being synced via setState in an effect.
const ReadingEditForm: React.FC<ReadingEditFormProps> = ({ reading, unit, onClose, onSaved }) => {
  const [date, setDate] = useState(reading.reading_date);
  const [value, setValue] = useState(reading.value);
  const [note, setNote] = useState(reading.note ?? '');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

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
  );
};

const ReadingEditDialog: React.FC<ReadingEditDialogProps> = ({ reading, unit, onClose, onSaved }) => {
  return (
    <Dialog open={!!reading} onOpenChange={(open) => { if (!open) onClose(); }}>
      {reading && (
        <ReadingEditForm
          key={reading.id}
          reading={reading}
          unit={unit}
          onClose={onClose}
          onSaved={onSaved}
        />
      )}
    </Dialog>
  );
};

export default ReadingEditDialog;
