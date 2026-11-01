import React, { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';
import { Dialog } from '../components/ui/dialog';
import { metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { sortRows, type ColumnSort } from '../hooks/useColumnSort';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter } from '../types';
import { Pencil, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import EditMeterModal from '../components/EditMeterModal';
import { SortableHeader } from '../components/SortableHeader';
import { TableSearch } from '../components/TableSearch';

function formatDate(iso: string): string {
  const datePart = iso.split('T')[0] ?? iso;
  const [y, m, d] = datePart.split('-');
  return `${d}.${m}.${y}`;
}

function getMeterValue(meter: Meter, key: string): string | null {
  switch (key) {
    case 'label':
      return meter.label;
    case 'number':
      return meter.meter_number;
    case 'type':
      return meter.meter_type;
    case 'unit':
      return meter.unit;
    case 'created':
      return meter.created_at.split('T')[0] ?? meter.created_at;
    default:
      return null;
  }
}

const MeterList: React.FC = () => {
  // Bumping reloadKey re-triggers the useFetch effect to refetch after mutations.
  const [reloadKey, setReloadKey] = useState(0);
  const {
    data,
    loading,
    error,
  } = useFetch<Meter[]>(async () => {
    try {
      return await metersApi.getAll();
    } catch {
      throw new Error('Fehler beim Laden der Zähler. Bitte erneut versuchen.');
    }
  }, [reloadKey]);

  const meters = data ?? [];
  const meterTypes = useMeterTypes();

  // Type filter + free-text search + optional column sort. Default keeps the
  // newest meters first; a chosen column overrides it.
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [manualSort, setManualSort] = useState<ColumnSort | null>(null);
  const handleSort = (key: string) =>
    setManualSort((prev) =>
      prev && prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'desc' }
    );

  // Edit modal state
  const [editMeter, setEditMeter] = useState<Meter | null>(null);

  // Delete modal state
  const [deleteMeter, setDeleteMeter] = useState<Meter | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteConfirm = async () => {
    if (!deleteMeter) return;
    try {
      setDeleting(true);
      await metersApi.delete(deleteMeter.id);
      setDeleteMeter(null);
      setReloadKey((k) => k + 1);
    } catch (err) {
      console.error('Error deleting meter:', err);
      alert('Fehler beim Löschen des Zählers. Bitte erneut versuchen.');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center">Lade Zähler...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-destructive">{error}</div>;
  }

  const metersById = new Map(meters.map((m) => [m.id, m]));
  const successorOf = new Map<number, Meter>();
  for (const m of meters) {
    if (m.replaces_meter_id !== null) {
      successorOf.set(m.replaces_meter_id, m);
    }
  }

  const filteredMeters = activeFilter
    ? meters.filter((m) => m.meter_type === activeFilter)
    : meters;

  const searchedMeters = searchQuery
    ? filteredMeters.filter((m) => {
        const haystack = [
          m.label,
          m.meter_number ?? '',
          meterTypeLabel(meterTypes, m.meter_type),
          m.unit,
        ].join(' ').toLowerCase();
        return haystack.includes(searchQuery.toLowerCase());
      })
    : filteredMeters;

  const displayedMeters = manualSort
    ? sortRows(searchedMeters, manualSort, getMeterValue)
    : searchedMeters;

  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <span>Alle Zähler</span>
            <Link to="/meters/new">
              <Button>Neuer Zähler</Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {meters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Keine Zähler gefunden. Füge deinen ersten Zähler hinzu!
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-3 mb-6">
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant={activeFilter === null ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setActiveFilter(null)}
                  >
                    Alle
                  </Button>
                  {meterTypes.map((mt) => (
                    <Button
                      key={mt.value}
                      variant={activeFilter === mt.value ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setActiveFilter(mt.value)}
                    >
                      {mt.label}
                    </Button>
                  ))}
                </div>
                <div className="flex justify-end">
                  <TableSearch
                    value={searchQuery}
                    onChange={setSearchQuery}
                    placeholder="Suchen (Bezeichnung, Zählernummer, Typ)"
                  />
                </div>
              </div>

              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortableHeader label="Zähler" sortKey="label" sort={manualSort ?? { key: 'created', dir: 'desc' }} onSort={handleSort} />
                      <SortableHeader label="Nummer" sortKey="number" sort={manualSort ?? { key: 'created', dir: 'desc' }} onSort={handleSort} />
                      <SortableHeader label="Typ" sortKey="type" sort={manualSort ?? { key: 'created', dir: 'desc' }} onSort={handleSort} />
                      <SortableHeader label="Einheit" sortKey="unit" sort={manualSort ?? { key: 'created', dir: 'desc' }} onSort={handleSort} />
                      <SortableHeader label="Erstellt" sortKey="created" sort={manualSort ?? { key: 'created', dir: 'desc' }} onSort={handleSort} />
                      <TableHead>Aktionen</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {displayedMeters.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          Keine Treffer für die aktuelle Suche.
                        </TableCell>
                      </TableRow>
                    ) : (
                      displayedMeters.map((meter) => {
                        const predecessor = meter.replaces_meter_id !== null
                          ? metersById.get(meter.replaces_meter_id)
                          : undefined;
                        const successor = successorOf.get(meter.id);
                        const isReplaced = !!successor;

                        return (
                          <TableRow key={meter.id} className={isReplaced ? 'opacity-60' : undefined}>
                            <TableCell className="font-medium">
                              {meter.label}
                              {predecessor && (
                                <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                                  Ersetzt Zähler #{predecessor.id} „{predecessor.label}&quot;
                                </div>
                              )}
                              {successor && (
                                <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                                  Ersetzt durch Zähler #{successor.id} „{successor.label}&quot;
                                </div>
                              )}
                            </TableCell>
                            <TableCell>{meter.meter_number ?? '–'}</TableCell>
                            <TableCell>{meterTypeLabel(meterTypes, meter.meter_type)}</TableCell>
                            <TableCell>{meter.unit}</TableCell>
                            <TableCell>{formatDate(meter.created_at)}</TableCell>
                            <TableCell>
                              <div className="flex gap-1">
                                <Link to={`/meters/${meter.id}`}>
                                  <Button variant="outline" size="sm">
                                    Anzeigen
                                  </Button>
                                </Link>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setEditMeter(meter)}
                                >
                                  <Pencil className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={() => setDeleteMeter(meter)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit modal */}
      <EditMeterModal
        meter={editMeter}
        allMeters={meters}
        onClose={() => setEditMeter(null)}
        onSaved={() => { setEditMeter(null); setReloadKey((k) => k + 1); }}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteMeter} onOpenChange={(open) => { if (!open) setDeleteMeter(null); }}>
        {deleteMeter && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Zähler löschen</h2>
            <p>
              Bist du sicher, dass du den Zähler <strong>„{deleteMeter.label}&quot;</strong> löschen möchtest?
            </p>
            <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-800 flex gap-2 items-start">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                Dieser Vorgang löscht auch alle zugehörigen Zählerstände, Tarife und Abschläge.
              </span>
            </div>
            <div className="flex justify-end gap-4 pt-2">
              <Button variant="outline" onClick={() => setDeleteMeter(null)} disabled={deleting}>
                Abbrechen
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm} disabled={deleting}>
                {deleting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Lösche...
                  </>
                ) : (
                  'Löschen'
                )}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
};

export default MeterList;
