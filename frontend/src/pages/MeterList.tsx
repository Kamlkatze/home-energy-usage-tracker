import React, { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter } from '../types';
import { Dialog } from '../components/ui/dialog';
import { Pencil, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import EditMeterModal from '../components/EditMeterModal';

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

  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex justify-between items-center">
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
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {meters.map((meter) => {
                const predecessor = meter.replaces_meter_id !== null
                  ? metersById.get(meter.replaces_meter_id)
                  : undefined;
                const successor = successorOf.get(meter.id);
                const isReplaced = !!successor;

                return (
                  <Card key={meter.id} className={isReplaced ? 'opacity-60' : undefined}>
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h3 className="font-semibold text-lg">{meter.label}</h3>
                          <p className="text-sm text-muted-foreground">
                            {meterTypeLabel(meterTypes, meter.meter_type)}
                          </p>
                        </div>
                        <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                          {meter.unit}
                        </span>
                      </div>

                      {predecessor && (
                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                          Ersetzt Zähler #{predecessor.id} „{predecessor.label}&quot;
                        </p>
                      )}
                      {successor && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                          Ersetzt durch Zähler #{successor.id} „{successor.label}&quot;
                        </p>
                      )}

                      <div className="flex justify-between items-center mt-4">
                        <div className="text-xs text-muted-foreground">
                          Erstellt: {new Date(meter.created_at).toLocaleDateString()}
                        </div>
                        <div className="flex gap-2">
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
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
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