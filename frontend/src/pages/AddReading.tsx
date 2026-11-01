import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { readingsApi, metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter, Reading } from '../types';
import { ArrowLeft, ArrowUp, ArrowDown, CheckCircle, XCircle, Loader2 } from 'lucide-react';

const LS_KEY = 'reading-form-selected-meters';
const LS_SEEN_KEY = 'reading-form-seen-meters';
const LS_ORDER_KEY = 'reading-form-meter-order';

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

interface MetersLoadResult {
  meters: Meter[];
  baseEntries: Record<number, MeterEntry>;
  lastReadings: Record<number, Reading | null>;
  savedOrder: number[];
}

const formatDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

// Display-only formatting of the last reading: electricity (kWh) is rounded
// to whole kWh, gas/water (m³) keeps 3 decimal places.
const formatLastReading = (value: string, unit: string): string => {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return value;
  if (unit === 'kWh') return num.toFixed(0);
  if (unit === 'm³') return num.toFixed(3);
  return value;
};

const AddReading: React.FC = () => {
  const navigate = useNavigate();
  const meterTypes = useMeterTypes();
  const [readingDate, setReadingDate] = useState(new Date().toISOString().split('T')[0]);
  // User edits on top of the base entries built when the meters loaded.
  const [entryOverrides, setEntryOverrides] = useState<Record<number, Partial<MeterEntry>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<SubmitResult[] | null>(null);

  const [showReplaced, setShowReplaced] = useState(false);
  // Custom row order (meter IDs) set via the move buttons; null = use saved order.
  const [orderState, setOrderState] = useState<number[] | null>(null);

  const {
    data: metersLoad,
    loading: loadingMeters,
  } = useFetch<MetersLoadResult>(async () => {

    try {
      const data = await metersApi.getAll();

      // Load localStorage: selectedIds = meters checked last time,
      // seenIds = all meter IDs that have ever been displayed on this page,
      // savedOrder = custom row order set via the move buttons.
      let selectedIds: number[] = [];
      let seenIds: number[] = [];
      let savedOrder: number[] = [];
      try {
        const rawSelected = localStorage.getItem(LS_KEY);
        if (rawSelected) {
          selectedIds = JSON.parse(rawSelected);
        }
        const rawSeen = localStorage.getItem(LS_SEEN_KEY);
        if (rawSeen) {
          seenIds = JSON.parse(rawSeen);
        }
        const rawOrder = localStorage.getItem(LS_ORDER_KEY);
        if (rawOrder) {
          savedOrder = JSON.parse(rawOrder);
        }
      } catch {
        // ignore invalid localStorage data
      }

      // Build base entries:
      // - New meters (not in seenIds) default to checked
      // - Previously seen meters follow the saved selection
      const baseEntries: Record<number, MeterEntry> = {};
      data.forEach((meter: Meter) => {
        const isNew = !seenIds.includes(meter.id);
        baseEntries[meter.id] = {
          checked: isNew || selectedIds.includes(meter.id),
          value: '',
          note: '',
        };
      });

      // Persist updated seenIds
      const currentIds = data.map((m: Meter) => m.id);
      const mergedSeen = Array.from(new Set([...seenIds, ...currentIds]));
      localStorage.setItem(LS_SEEN_KEY, JSON.stringify(mergedSeen));

      // Fetch last reading for each meter (optional info, failures ignored)
      const lastReadings: Record<number, Reading | null> = {};
      await Promise.all(
        data.map(async (meter: Meter) => {
          try {
            lastReadings[meter.id] = await metersApi.getLastReading(meter.id);
          } catch {
            // silently ignore — last reading is optional info
          }
        })
      );

      return { meters: data, baseEntries, lastReadings, savedOrder };
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : 'Fehler beim Laden der Zähler');
    }
  }, []);

  const meters = metersLoad?.meters ?? [];
  const baseEntries = metersLoad?.baseEntries ?? {};
  const lastReadings = metersLoad?.lastReadings ?? {};
  const savedOrder = metersLoad?.savedOrder ?? [];

  // Row order: user's live order, else the persisted order, else API order.
  const meterMap = new Map(meters.map(m => [m.id, m]));
  const activeOrder = orderState ?? savedOrder;
  const orderedMeters: Meter[] = [
    ...activeOrder.map(id => meterMap.get(id)).filter((m): m is Meter => Boolean(m)),
    ...meters.filter(m => !activeOrder.includes(m.id)),
  ];

  const replacedMeterIds = new Set(
    meters
      .filter(m => m.replaces_meter_id !== null)
      .map(m => m.replaces_meter_id as number)
  );
  const visibleMeters = showReplaced
    ? orderedMeters
    : orderedMeters.filter(m => !replacedMeterIds.has(m.id));
  const visibleIds = visibleMeters.map(m => m.id);

  // Effective entries: base entries from the load + the user's edits.
  const entries: Record<number, MeterEntry> = {};
  for (const idStr of Object.keys(baseEntries)) {
    const id = Number(idStr);
    entries[id] = { ...baseEntries[id], ...(entryOverrides[id] ?? {}) };
  }

  const persistSelection = (updatedEntries: Record<number, MeterEntry>) => {
    const selectedIds = Object.entries(updatedEntries)
      .filter(([, entry]) => entry.checked)
      .map(([id]) => Number(id));
    localStorage.setItem(LS_KEY, JSON.stringify(selectedIds));
  };

  const handleCheckChange = (meterId: number, checked: boolean) => {
    const updated: Record<number, MeterEntry> = {
      ...entries,
      [meterId]: { ...entries[meterId], checked },
    };
    persistSelection(updated);
    setEntryOverrides(prev => ({ ...prev, [meterId]: { ...prev[meterId], checked } }));
  };

  const handleValueChange = (meterId: number, value: string) => {
    setEntryOverrides(prev => ({ ...prev, [meterId]: { ...prev[meterId], value } }));
  };

  const handleNoteChange = (meterId: number, note: string) => {
    setEntryOverrides(prev => ({ ...prev, [meterId]: { ...prev[meterId], note } }));
  };

  const handleMove = (meterId: number, dir: -1 | 1) => {
    const idx = visibleIds.indexOf(meterId);
    const targetIdx = idx + dir;
    if (idx === -1 || targetIdx < 0 || targetIdx >= visibleIds.length) return;
    const targetId = visibleIds[targetIdx];

    // Reorder within the full (ordered) list, relative to the target row.
    const order = orderedMeters.map(m => m.id);
    order.splice(order.indexOf(meterId), 1);
    let to = order.indexOf(targetId);
    if (dir === 1) to += 1;
    order.splice(to, 0, meterId);

    setOrderState(order);
    try {
      localStorage.setItem(LS_ORDER_KEY, JSON.stringify(order));
    } catch {
      // ignore storage failures — ordering is cosmetic
    }
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
          error: err?.response?.data?.detail ?? err.message ?? 'Unbekannter Fehler',
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

      <div className="max-w-5xl mx-auto">
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
                  setEntryOverrides(prev => {
                    const reset: Record<number, Partial<MeterEntry>> = {};
                    for (const [idStr, override] of Object.entries(prev)) {
                      reset[Number(idStr)] = { ...override, value: '', note: '' };
                    }
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

                {/* Meter table */}
                <div className="flex items-center gap-2 mb-3">
                  <Checkbox
                    id="show-replaced"
                    checked={showReplaced}
                    onChange={(e) => setShowReplaced(e.target.checked)}
                  />
                  <Label htmlFor="show-replaced" className="text-sm cursor-pointer text-muted-foreground">
                    Alte Zähler anzeigen
                  </Label>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-3 w-8">
                          <span className="sr-only">Auswählen</span>
                        </th>
                        <th className="py-2 pr-3 font-medium">Zähler</th>
                        <th className="py-2 pr-3 font-medium">Letzter Stand</th>
                        <th className="py-2 pr-3 font-medium">Zählerstand</th>
                        <th className="py-2 pr-3 font-medium">Notiz</th>
                        <th className="py-2 font-medium">
                          <span className="sr-only">Reihenfolge</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleMeters.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">
                            {meters.length === 0
                              ? 'Keine Zähler vorhanden. Bitte legen Sie zuerst einen Zähler an.'
                              : 'Keine Zähler für die aktuelle Ansicht.'}
                          </td>
                        </tr>
                      ) : (
                        visibleMeters.map(meter => {
                          const entry = entries[meter.id];
                          if (!entry) return null;
                          const lastReading = lastReadings[meter.id];
                          const isReplaced = replacedMeterIds.has(meter.id);
                          const visIdx = visibleIds.indexOf(meter.id);
                          return (
                            <tr
                              key={meter.id}
                              className={`border-b last:border-0 ${entry.checked ? '' : 'opacity-60'} ${isReplaced ? 'bg-amber-50/50 dark:bg-amber-950/20' : ''}`}
                            >
                              <td className="py-3 pr-3 align-middle">
                                <Checkbox
                                  id={`check-${meter.id}`}
                                  checked={entry.checked}
                                  onChange={(e) => handleCheckChange(meter.id, e.target.checked)}
                                />
                              </td>
                              <td className="py-3 pr-3 align-middle">
                                <Label
                                  htmlFor={`value-${meter.id}`}
                                  className="font-medium cursor-pointer"
                                  onClick={() => handleCheckChange(meter.id, !entry.checked)}
                                >
                                  {meter.label}
                                  <span className="block text-xs text-muted-foreground font-normal">
                                    ({meterTypeLabel(meterTypes, meter.meter_type)} • {meter.unit})
                                  </span>
                                </Label>
                              </td>
                              <td className="py-3 pr-3 align-middle whitespace-nowrap">
                                {lastReading ? (
                                  <>
                                    {formatLastReading(lastReading.value, meter.unit)} {meter.unit}
                                    <span className="block text-xs text-muted-foreground">
                                      am {formatDate(lastReading.reading_date)}
                                    </span>
                                  </>
                                ) : (
                                  <span className="text-muted-foreground">–</span>
                                )}
                              </td>
                              <td className="py-3 pr-3 align-middle">
                                <Input
                                  id={`value-${meter.id}`}
                                  type="number"
                                  step="0.001"
                                  value={entry.value}
                                  onChange={(e) => handleValueChange(meter.id, e.target.value)}
                                  placeholder="Zählerstand"
                                  disabled={!entry.checked}
                                  className="w-36"
                                />
                              </td>
                              <td className="py-3 pr-3 align-middle">
                                <Input
                                  id={`note-${meter.id}`}
                                  value={entry.note}
                                  onChange={(e) => handleNoteChange(meter.id, e.target.value)}
                                  placeholder="optional"
                                  disabled={!entry.checked}
                                />
                              </td>
                              <td className="py-3 align-middle">
                                <div className="flex gap-1 justify-end">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    aria-label="Nach oben"
                                    disabled={visIdx === 0}
                                    onClick={() => handleMove(meter.id, -1)}
                                  >
                                    <ArrowUp className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    aria-label="Nach unten"
                                    disabled={visIdx === visibleIds.length - 1}
                                    onClick={() => handleMove(meter.id, 1)}
                                  >
                                    <ArrowDown className="h-4 w-4" />
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
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
