import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter, Reading } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowLeft } from 'lucide-react';

const MeterDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const meterTypes = useMeterTypes();

  const {
    data,
    loading,
    error,
  } = useFetch<{ meterData: Meter; readingsData: Reading[] }>(async () => {
    const meterId = id !== undefined ? parseInt(id, 10) : NaN;
    if (isNaN(meterId)) {
      throw new Error('Ungültige Zähler-ID');
    }
    try {
      const meterData = await metersApi.getById(meterId);
      const readingsData = await metersApi.getReadings(meterId);
      return { meterData, readingsData };
    } catch {
      throw new Error('Fehler beim Laden der Zählerdaten. Bitte erneut versuchen.');
    }
  }, [id]);

  const meter = data?.meterData ?? null;
  const readings = data?.readingsData ?? [];


  const chartData = readings.map(reading => ({
    date: new Date(reading.reading_date).toLocaleDateString(),
    value: parseFloat(reading.value),
    note: reading.note,
  }));

  if (loading) {
    return <div className="p-8 text-center">Lade Zählerdetails...</div>;
  }

  if (error || !meter) {
    return (
      <div className="p-8">
        <Link to="/meters">
          <Button variant="outline" className="mb-4 gap-2">
            <ArrowLeft className="h-4 w-4" />
            Zurück zu den Zählern
          </Button>
        </Link>
        <Card>
          <CardContent className="p-8 text-center text-destructive">
            {error || 'Zähler nicht gefunden'}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/meters">
          <Button variant="outline" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Zurück zu den Zählern
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">{meter.label}</h1>
        <span className="text-sm font-medium bg-primary/10 text-primary px-3 py-1 rounded-full">
          {meterTypeLabel(meterTypes, meter.meter_type)} &bull; {meter.unit}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Verbrauchsdiagramm</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              {readings.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis label={{ value: meter.unit, angle: -90, position: 'insideLeft' }} />
                    <Tooltip
                      formatter={(value) => [`${value} ${meter.unit}`, 'Wert']}
                      labelFormatter={(label) => `Datum: ${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-muted-foreground">
                  Keine Zählerstände vorhanden. Füge den ersten Zählerstand hinzu, um das Diagramm zu sehen.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Zählerdetails</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Typ</h3>
                <p className="text-lg">{meterTypeLabel(meterTypes, meter.meter_type)}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Einheit</h3>
                <p className="text-lg">{meter.unit}</p>
              </div>
              {meter.meter_number && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">Zählernummer</h3>
                  <p className="text-lg font-mono">{meter.meter_number}</p>
                </div>
              )}
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Erstellt</h3>
                <p className="text-lg">{new Date(meter.created_at).toLocaleDateString()}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Zählerstände</h3>
                <p className="text-lg">{readings.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex justify-between items-center">
              <span>Letzte Zählerstände</span>
              <Link to="/readings/new">
                <Button size="sm">Zählerstand erfassen</Button>
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {readings.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Datum</TableHead>
                    <TableHead>Wert ({meter.unit})</TableHead>
                    <TableHead>Notiz</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {readings.slice(-5).reverse().map((reading) => (
                    <TableRow key={reading.id}>
                      <TableCell>{new Date(reading.reading_date).toLocaleDateString()}</TableCell>
                      <TableCell>{reading.value}</TableCell>
                      <TableCell>{reading.note || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Noch keine Zählerstände. Erfasse den ersten Zählerstand!
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MeterDetail;