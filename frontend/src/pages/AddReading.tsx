import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { readingsApi, metersApi } from '../api/client';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter, Reading } from '../types';
import { ArrowLeft, CheckCircle, XCircle, Loader2 } from 'lucide-react';

const LS_KEY = 'reading-form-selected-meters';
const LS_SEEN_KEY = 'reading-form-seen-meters';

interface MeterEntry {
  checked: boolean;
  value: string;
  note: string;
}

interface SubmitResult {
  meterId: number;
  meterLabel: string;
  success: boolean;
  error?: string;
}

const formatDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const AddReading: React.FC = () => {
  const navigate = useNavigate();
  const [meters, setMeters] = useState<Meter[]>([]);
  const meterTypes = useMeterTypes();
  const [readingDate, setReadingDate] = useState(new Date().toISOString().split('T')[0]);
  const [entries, setEntries] = useState<Record<number, MeterEntry>>({});
  const [lastReadings, setLastReadings] = useState<Record<number, Reading | null>>({});
  const [loadingMeters, setLoadingMeters] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<SubmitResult[] | null>(null);

  useEffect(() => {
    fetchMeters();
  }, []);

  const loadLastReading = useCallback(async (meterId: number) => {
    try {
      const reading = await metersApi.getLastReading(meterId);
      setLastReadings(prev => ({ ...prev, [meterId]: reading }));
    } catch {
      // silently ignore — last reading is optional info
    }
  }, []);

  const fetchMeters = async () => {
    try {
      setLoadingMeters(true);
      const data = await metersApi.getCurrent();
      setMeters(data);

      // Load localStorage: selectedIds = meters checked last time,
      // seenIds = all meter IDs that have ever been displayed on this page.
      let selectedIds: number[] = [];
      let seenIds: number[] = [];
      try {
        const rawSelected = localStorage.getItem(LS_KEY);
        if (rawSelected) {
          selectedIds = JSON.parse(rawSelected);
        }
        const rawSeen = localStorage.getItem(LS_SEEN_KEY);
        if (rawSeen) {
          seenIds = JSON.parse(rawSeen);
        }
      } catch {
        // ignore invalid localStorage data
      }

      // Build entries:
      // - New meters (not in seenIds) default to checked
      // - Previously seen meters follow the saved selection
      const initialEntries: Record<number, MeterEntry> = {};
      data.forEach((meter: Meter) => {
        const isNew = !seenIds.includes(meter.id);
        initialEntries[meter.id] = {
          checked: isNew || selectedIds.includes(meter.id),
          value: '',
          note: '',
        };
      });
      setEntries(initialEntries);

      // Persist updated seenIds
      const currentIds = data.map((m: Meter) => m.id);
      const mergedSeen = Array.from(new Set([...seenIds, ...currentIds]));
      localStorage.setItem(LS_SEEN_KEY, JSON.stringify(mergedSeen));

      // Fetch last reading for each meter
      await Promise.all(data.map((meter: Meter) => loadLastReading(meter.id)));
    } catch (err) {
      console.error('Error fetching current meters:', err);
    } finally {
      setLoadingMeters(false);
    }
  };

  const persistSelection = (updatedEntries: Record<number, MeterEntry>) => {
    const selectedIds = Object.entries(updatedEntries)
      .filter(([, entry]) => entry.checked)
      .map(([id]) => Number(id));
    localStorage.setItem(LS_KEY, JSON.stringify(selectedIds));
  };

  const handleCheckChange = (meterId: number, checked: boolean) => {
    setEntries(prev => {
      const updated = {
        ...prev,
        [meterId]: { ...prev[meterId], checked },
      };
      persistSelection(updated);
      return updated;
    });
  };

  const handleValueChange = (meterId: number, value: string) => {
    setEntries(prev => ({ ...prev, [meterId]: { ...prev[meterId], value } }));
  };

  const handleNoteChange = (meterId: number, note: string) => {
    setEntries(prev => ({ ...prev, [meterId]: { ...prev[meterId], note } }));
  };

  const hasValidEntries = Object.values(entries).some(
    entry => entry.checked && entry.value.trim() !== ''
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const selectedEntries = Object.entries(entries).filter(
      ([, entry]) => entry.checked && entry.value.trim() !== ''
    );

    if (selectedEntries.length === 0) {
      return;
    }

    setSubmitting(true);
    setResults(null);

    const results: SubmitResult[] = [];
    const meterMap = new Map(meters.map(m => [m.id, m]));

    for (const [meterIdStr, entry] of selectedEntries) {
      const meterId = Number(meterIdStr);
      const meter = meterMap.get(meterId);
      try {
        await readingsApi.create({
          meter_id: meterId,
          value: parseFloat(entry.value),
          reading_date: readingDate,
          note: entry.note || null,
        });
        results.push({ meterId, meterLabel: meter?.label ?? `#${meterId}`, success: true });
      } catch (err: any) {
        console.error(`Error creating reading for meter ${meterId}:`, err);
        results.push({
          meterId,
          meterLabel: meter?.label ?? `#${meterId}`,
          success: false,
          error: err?.response?.data?.detail ?? err.message ?? 'Unknown error',
        });
      }
    }

    setResults(results);
    setSubmitting(false);
  };

  const successCount = results?.filter(r => r.success).length ?? 0;
  const failureCount = results?.filter(r => !r.success).length ?? 0;
  const allSuccess = results && failureCount === 0;

  return (
    <div className="p-6">
      <Button variant="outline" className="mb-6 gap-2" onClick={() => navigate('/meters')}>
        <ArrowLeft className="h-4 w-4" />
        Zurück zu den Zählern
      </Button>

      <div className="max-w-3xl mx-auto">
        {results && allSuccess ? (
          <Card>
            <CardContent className="p-8 text-center">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Zählerstände gespeichert</h2>
              <p className="text-muted-foreground mb-4">
                {successCount} Zählerstand{successCount !== 1 ? 'stände' : ''} erfolgreich gespeichert.
              </p>
              <div className="flex justify-center gap-4">
                <Button onClick={() => {
                  setResults(null);
                  setEntries(prev => {
                    const reset = Object.fromEntries(
                      Object.entries(prev).map(([id, entry]) => [id, { ...entry, value: '', note: '' }])
                    );
                    return reset;
                  });
                  setReadingDate(new Date().toISOString().split('T')[0]);
                }}>
                  Weitere Eingaben
                </Button>
                <Button variant="outline" onClick={() => navigate('/meters')}>
                  Zu den Zählern
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : results && !allSuccess ? (
          <Card>
            <CardHeader>
              <CardTitle>Ergebnis der Eingabe</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-muted-foreground">
                {successCount} von {successCount + failureCount} Zählerständen erfolgreich gespeichert.
              </p>
              <ul className="space-y-2">
                {results.map(r => (
                  <li key={r.meterId} className="flex items-start gap-2">
                    {r.success ? (
                      <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 shrink-0" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                    )}
                    <span>
                      <strong>{r.meterLabel}</strong>
                      {r.success ? ' — Erfolgreich' : ` — Fehler: ${r.error}`}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="flex justify-end gap-4 pt-4">
                <Button onClick={() => setResults(null)}>
                  Zurück
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <form onSubmit={handleSubmit}>
            {/* Loading state */}
            {loadingMeters ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                  <p className="text-muted-foreground">Lade Zähler…</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Common date */}
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle>Zählerstände eingeben</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <Label htmlFor="reading_date">Datum *</Label>
                      <Input
                        id="reading_date"
                        name="reading_date"
                        type="date"
                        required
                        value={readingDate}
                        onChange={(e) => setReadingDate(e.target.value)}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Meter list */}
                <div className="space-y-4">
                  {meters.length === 0 ? (
                    <Card>
                      <CardContent className="p-8 text-center text-muted-foreground">
                        Keine Zähler vorhanden. Bitte legen Sie zuerst einen Zähler an.
                      </CardContent>
                    </Card>
                  ) : (
                    meters.map(meter => {
                      const entry = entries[meter.id];
                      const lastReading = lastReadings[meter.id];
                      if (!entry) return null;
                      return (
                        <Card key={meter.id} className={entry.checked ? '' : 'opacity-60'}>
                          <CardContent className="p-4">
                            <div className="flex items-start gap-3">
                              {/* Checkbox */}
                              <Checkbox
                                id={`check-${meter.id}`}
                                checked={entry.checked}
                                onChange={(e) => handleCheckChange(meter.id, e.target.checked)}
                                className="mt-1"
                              />

                              {/* Meter info + inputs */}
                              <div className="flex-1 min-w-0 space-y-3">
                                <div className="flex justify-between items-baseline gap-2">
                                  <Label
                                    htmlFor={`value-${meter.id}`}
                                    className="text-base font-medium cursor-pointer"
                                    onClick={() => handleCheckChange(meter.id, !entry.checked)}
                                  >
                                    {meter.label}
                                    <span className="text-sm text-muted-foreground font-normal ml-2">
                                      ({meterTypeLabel(meterTypes, meter.meter_type)} • {meter.unit})
                                    </span>
                                  </Label>
                                </div>

                                {/* Last reading reference */}
                                {lastReading && (
                                  <p className="text-xs text-muted-foreground">
                                    Letzter Stand: {lastReading.value} {meter.unit} am {formatDate(lastReading.reading_date)}
                                  </p>
                                )}

                                {/* Value input */}
                                <div>
                                  <Input
                                    id={`value-${meter.id}`}
                                    type="number"
                                    step="0.001"
                                    value={entry.value}
                                    onChange={(e) => handleValueChange(meter.id, e.target.value)}
                                    placeholder="Zählerstand"
                                    disabled={!entry.checked}
                                  />
                                </div>

                                {/* Note */}
                                <div>
                                  <Textarea
                                    value={entry.note}
                                    onChange={(e) => handleNoteChange(meter.id, e.target.value)}
                                    placeholder="Notiz (optional)"
                                    rows={1}
                                    disabled={!entry.checked}
                                    className="min-h-[2.5rem]"
                                  />
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })
                  )}
                </div>

                {/* Submit */}
                <div className="flex justify-end gap-4 pt-6">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/meters')}
                    disabled={submitting}
                  >
                    Abbrechen
                  </Button>
                  <Button type="submit" disabled={submitting || !hasValidEntries}>
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Speichere…
                      </>
                    ) : (
                      'Zählerstände speichern'
                    )}
                  </Button>
                </div>
              </>
            )}
          </form>
        )}
      </div>
    </div>
  );
};

export default AddReading;
