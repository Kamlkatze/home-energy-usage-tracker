import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { metersApi } from '../api/client';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter } from '../types';

const MeterList: React.FC = () => {
  const [meters, setMeters] = useState<Meter[]>([]);
  const meterTypes = useMeterTypes();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMeters();
  }, []);

  const fetchMeters = async () => {
    try {
      setLoading(true);
      const data = await metersApi.getAll();
      setMeters(data);
      setError(null);
    } catch (err) {
      setError('Failed to load meters. Please try again.');
      console.error('Error fetching meters:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this meter?')) {
      try {
        await metersApi.delete(id);
        await fetchMeters();
      } catch (err) {
        console.error('Error deleting meter:', err);
        alert('Failed to delete meter. Please try again.');
      }
    }
  };

  if (loading) {
    return <div className="p-8 text-center">Loading meters...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-destructive">{error}</div>;
  }

  // Build a lookup: which meter is replaced by which successor
  const metersById = new Map(meters.map((m) => [m.id, m]));
  // successorOf[id] = the meter that replaces meter id
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
            <span>All Meters</span>
            <Link to="/meters/new">
              <Button>Add New Meter</Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {meters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No meters found. Add your first meter!
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

                      {/* Zählerwechsel-Kette anzeigen */}
                      {predecessor && (
                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                          Ersetzt Zähler #{predecessor.id} „{predecessor.label}"
                        </p>
                      )}
                      {successor && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                          Ersetzt durch Zähler #{successor.id} „{successor.label}"
                        </p>
                      )}

                      <div className="flex justify-between items-center mt-4">
                        <div className="text-xs text-muted-foreground">
                          Created: {new Date(meter.created_at).toLocaleDateString()}
                        </div>
                        <div className="flex gap-2">
                          <Link to={`/meters/${meter.id}`}>
                            <Button variant="outline" size="sm">
                              View
                            </Button>
                          </Link>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDelete(meter.id)}
                          >
                            Delete
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
    </div>
  );
};

export default MeterList;
