import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';
import { Dialog } from '../components/ui/dialog';
import { tariffsApi, metersApi } from '../api/client';
import { Meter, TariffPeriod, TariffUsage } from '../types';
import { Loader2, Pencil, Trash2, AlertTriangle } from 'lucide-react';
import { TARIFF_KIND_LABELS, getTariffFields, getPriceUnitLabel } from '../lib/tariffFields';

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'offen';
  const [y, m, d] = dateStr.split('-');
  return `${d}.${m}.${y}`;
}

const TariffList: React.FC = () => {
  const [tariffs, setTariffs] = useState<TariffPeriod[]>([]);
  const [meters, setMeters] = useState<Meter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [meterFilter, setMeterFilter] = useState<string>('');

  // Edit modal state
  const [editTariff, setEditTariff] = useState<TariffPeriod | null>(null);
  const [editFormData, setEditFormData] = useState<Record<string, string>>({});
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Delete modal state
  const [deleteTariff, setDeleteTariff] = useState<TariffPeriod | null>(null);
  const [usage, setUsage] = useState<TariffUsage | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageError, setUsageError] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [tariffsData, metersData] = await Promise.all([
        tariffsApi.getAll(),
        metersApi.getAll(),
      ]);
      setTariffs(tariffsData);
      setMeters(metersData);
    } catch (err) {
      setError('Fehler beim Laden der Tarife');
      console.error('Error fetching tariffs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Sort: by meter label, then valid_from descending
  const metersById = new Map(meters.map((m) => [m.id, m]));
  const sortedTariffs = [...tariffs].sort((a, b) => {
    const labelA = metersById.get(a.meter_id)?.label ?? '';
    const labelB = metersById.get(b.meter_id)?.label ?? '';
    const cmp = labelA.localeCompare(labelB);
    if (cmp !== 0) return cmp;
    return b.valid_from.localeCompare(a.valid_from);
  });

  const filteredTariffs = meterFilter
    ? sortedTariffs.filter((t) => t.meter_id === parseInt(meterFilter))
    : sortedTariffs;

  const selectedMeter = editTariff
    ? meters.find((m) => m.id === editTariff.meter_id)
    : null;

  // ---- Edit handlers ----
  const openEdit = (tariff: TariffPeriod) => {
    setEditTariff(tariff);
    setEditFormData({
      valid_from: tariff.valid_from,
      valid_to: tariff.valid_to ?? '',
      price_per_unit: tariff.price_per_unit,
      base_fee_monthly: tariff.base_fee_monthly ?? '',
      metering_fee_monthly: tariff.metering_fee_monthly ?? '',
      gas_z_zahl: tariff.gas_z_zahl ?? '',
      gas_brennwert: tariff.gas_brennwert ?? '',
      eeg_tier1_rate: tariff.eeg_tier1_rate ?? '',
      eeg_tier2_rate: tariff.eeg_tier2_rate ?? '',
      metering_point_fee_yearly: tariff.metering_point_fee_yearly ?? '',
    });
    setEditError(null);
  };

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEditFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTariff) return;

    const fields = getTariffFields(editTariff.tariff_kind, selectedMeter?.meter_type, selectedMeter?.unit);

    if (!editFormData.valid_from || !editFormData.price_per_unit) {
      setEditError('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    const emptyRequired = fields.filter(f => f.required && !editFormData[f.name]);
    if (emptyRequired.length > 0) {
      setEditError('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setEditSaving(true);
      setEditError(null);
      const payload: Record<string, unknown> = {
        valid_from: editFormData.valid_from,
        price_per_unit: editFormData.price_per_unit,
      };
      if (editFormData.valid_to) {
        payload.valid_to = editFormData.valid_to;
      } else {
        payload.valid_to = null;
      }
      for (const field of fields) {
        if (field.name === 'price_per_unit') continue;
        if (editFormData[field.name]) {
          payload[field.name] = editFormData[field.name];
        } else {
          payload[field.name] = null;
        }
      }

      await tariffsApi.update(editTariff.id, payload);
      setEditTariff(null);
      await fetchData();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setEditError(detail || 'Fehler beim Speichern des Tarifs');
    } finally {
      setEditSaving(false);
    }
  };

  // ---- Delete handlers ----
  const openDelete = async (tariff: TariffPeriod) => {
    setDeleteTariff(tariff);
    setUsage(null);
    setUsageError(false);
    setUsageLoading(true);
    try {
      const data = await tariffsApi.getUsage(tariff.id);
      setUsage(data);
    } catch {
      setUsageError(true);
    } finally {
      setUsageLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTariff) return;
    try {
      setDeleting(true);
      await tariffsApi.delete(deleteTariff.id);
      setDeleteTariff(null);
      await fetchData();
    } catch (err) {
      console.error('Error deleting tariff:', err);
      alert('Fehler beim Löschen des Tarifs');
    } finally {
      setDeleting(false);
    }
  };

  // ---- Render helpers ----
  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Tarife...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center text-destructive">{error}</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <span>Tarife</span>
            <Link to="/tariffs/new">
              <Button>Neuer Tarif</Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tariffs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p className="mb-2">Noch keine Tarife angelegt.</p>
              <Link to="/tariffs/new" className="text-primary underline">Neuen Tarif anlegen</Link>
            </div>
          ) : (
            <>
              <div className="mb-4">
                <Select
                  value={meterFilter}
                  onChange={(e) => setMeterFilter(e.target.value)}
                >
                  <SelectItem value="">Alle Zähler</SelectItem>
                  {meters.map((meter) => (
                    <SelectItem key={meter.id} value={meter.id.toString()}>
                      {meter.label}
                    </SelectItem>
                  ))}
                </Select>
              </div>

              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Zähler</TableHead>
                      <TableHead>Tarifart</TableHead>
                      <TableHead>Gültig von</TableHead>
                      <TableHead>Gültig bis</TableHead>
                      <TableHead>Preis/Einheit</TableHead>
                      <TableHead>Grundpreis</TableHead>
                      <TableHead>Messstellenbetrieb</TableHead>
                      <TableHead>Aktionen</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTariffs.map((tariff) => {
                      const meter = metersById.get(tariff.meter_id);
                      const isGas = meter?.meter_type === 'gas';
                      return (
                        <TableRow key={tariff.id}>
                          <TableCell className="font-medium">
                            {meter?.label ?? `Zähler #${tariff.meter_id}`}
                          </TableCell>
                          <TableCell>
                            {TARIFF_KIND_LABELS[tariff.tariff_kind] ?? tariff.tariff_kind}
                          </TableCell>
                          <TableCell>{formatDate(tariff.valid_from)}</TableCell>
                          <TableCell>{formatDate(tariff.valid_to)}</TableCell>
                          <TableCell>
                            {tariff.price_per_unit} {getPriceUnitLabel(tariff.tariff_kind, meter?.meter_type, meter?.unit)}
                            {isGas && (
                              <div className="text-xs text-muted-foreground mt-1">
                                {tariff.gas_z_zahl && `z-Zahl: ${tariff.gas_z_zahl}`}
                                {tariff.gas_z_zahl && tariff.gas_brennwert ? ' · ' : ''}
                                {tariff.gas_brennwert && `Brennwert: ${tariff.gas_brennwert} kWh/m³`}
                              </div>
                            )}
                          </TableCell>
                          <TableCell>{tariff.base_fee_monthly ? `${tariff.base_fee_monthly} €` : '–'}</TableCell>
                          <TableCell>{tariff.metering_fee_monthly ? `${tariff.metering_fee_monthly} €` : '–'}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openEdit(tariff)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => openDelete(tariff)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

{/* ---- Edit Modal ---- */}
      <Dialog open={!!editTariff} onOpenChange={(open) => { if (!open) { setEditTariff(null); setEditError(null); } }}>
        {editTariff && selectedMeter && (() => {
          const fields = getTariffFields(editTariff.tariff_kind, selectedMeter.meter_type, selectedMeter.unit);
          const eegFields = fields.filter(f => f.group === 'eeg');
          const mainFields = fields.filter(f => f.group !== 'eeg');
          return (
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <h2 className="text-lg font-semibold">Tarif bearbeiten</h2>

              <div className="space-y-1">
                <Label>Zähler</Label>
                <p className="text-sm">{selectedMeter.label}</p>
                {editTariff.tariff_kind === 'feed_in_eeg2009' && (
                  <p className="text-xs text-muted-foreground">
                    Dieser Tarif muss auf dem Einspeise-Zähler (Strom Einspeisung) angelegt werden, nicht auf dem Erzeugungszähler.
                  </p>
                )}
              </div>

              <div className="space-y-1">
                <Label>Tarifart</Label>
                <p className="text-sm">{TARIFF_KIND_LABELS[editTariff.tariff_kind]}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-valid_from">Gültig ab *</Label>
                  <Input
                    id="edit-valid_from"
                    name="valid_from"
                    type="date"
                    required
                    value={editFormData.valid_from}
                    onChange={handleEditChange}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-valid_to">Gültig bis</Label>
                  <Input
                    id="edit-valid_to"
                    name="valid_to"
                    type="date"
                    value={editFormData.valid_to}
                    onChange={handleEditChange}
                  />
                  <p className="text-xs text-muted-foreground">Leer = unbefristet</p>
                </div>
              </div>

              {mainFields.length > 0 && (
                <div className="grid grid-cols-2 gap-4">
                  {mainFields.map((field) => (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={`edit-${field.name}`}>
                        {field.label}{field.required ? ' *' : ''}
                      </Label>
                      <Input
                        id={`edit-${field.name}`}
                        name={field.name}
                        type="number"
                        step={field.step}
                        required={field.required}
                        value={editFormData[field.name] ?? ''}
                        onChange={handleEditChange}
                        placeholder={field.placeholder}
                      />
                      {field.helperText && (
                        <p className="text-xs text-muted-foreground">{field.helperText}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {eegFields.length > 0 && (
                <div className="border border-blue-200 rounded-lg p-4 bg-blue-50/50">
                  <h3 className="text-sm font-semibold text-blue-800 mb-3">
                    EEG 2009 Vergütungssätze
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    {eegFields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label htmlFor={`edit-${field.name}`}>
                          {field.label} *
                        </Label>
                        <Input
                          id={`edit-${field.name}`}
                          name={field.name}
                          type="number"
                          step={field.step}
                          required
                          value={editFormData[field.name] ?? ''}
                          onChange={handleEditChange}
                          placeholder={field.placeholder}
                        />
                        {field.helperText && (
                          <p className="text-xs text-muted-foreground">{field.helperText}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {editError && (
                <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                  {editError}
                </div>
              )}

              <div className="flex justify-end gap-4 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { setEditTariff(null); setEditError(null); }}
                  disabled={editSaving}
                >
                  Abbrechen
                </Button>
                <Button type="submit" disabled={editSaving}>
                  {editSaving ? 'Speichern...' : 'Speichern'}
                </Button>
              </div>
            </form>
          );
        })()}
      </Dialog>

      {/* ---- Delete Modal ---- */}
      <Dialog open={!!deleteTariff} onOpenChange={(open) => { if (!open) setDeleteTariff(null); }}>
        {deleteTariff && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Tarif löschen</h2>

            <div className="text-sm space-y-1">
              <p><strong>Zähler:</strong> {metersById.get(deleteTariff.meter_id)?.label ?? `#${deleteTariff.meter_id}`}</p>
              <p><strong>Tarifart:</strong> {TARIFF_KIND_LABELS[deleteTariff.tariff_kind]}</p>
              <p><strong>Gültigkeit:</strong> {formatDate(deleteTariff.valid_from)} – {formatDate(deleteTariff.valid_to)}</p>
            </div>

            {usageLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Prüfe Verwendung...
              </div>
            ) : usageError ? (
              <div className="text-sm text-muted-foreground">
                Die Verwendung konnte nicht geprüft werden.
              </div>
            ) : usage && usage.in_use ? (
              <div className="text-sm bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
                  <div>
                    <p>Dieser Tarif deckt {usage.reading_count} Zählerstände ab
                    ({formatDate(usage.first_reading_date)} – {formatDate(usage.last_reading_date)}).</p>
                    <p>Nach dem Löschen können für diesen Zeitraum keine Kosten mehr berechnet werden.</p>
                  </div>
                </div>
              </div>
            ) : usage && !usage.in_use ? (
              <div className="text-sm text-muted-foreground">
                Für diesen Tarif liegen keine Zählerstände im Gültigkeitszeitraum vor.
              </div>
            ) : null}

            <div className="flex justify-end gap-4 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeleteTariff(null)}
                disabled={deleting}
              >
                Abbrechen
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleting || usageLoading}
              >
                {deleting ? 'Lösche...' : 'Löschen'}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
};

export default TariffList;