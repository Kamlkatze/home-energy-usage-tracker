import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { metersApi } from '../api/client';
import { Meter, Reading } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowLeft } from 'lucide-react';

const MeterDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [meter, setMeter] = useState<Meter | null>(null);
  const [readings, setReadings] = useState<Reading[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      fetchData();
    }
  }, [id]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const meterData = await metersApi.getById(parseInt(id!));
      const readingsData = await metersApi.getReadings(parseInt(id!));
      
      setMeter(meterData);
      setReadings(readingsData);
      setError(null);
    } catch (err) {
      setError('Failed to load meter data. Please try again.');
      console.error('Error fetching meter data:', err);
    } finally {
      setLoading(false);
    }
  };

  const chartData = readings.map(reading => ({
    date: new Date(reading.reading_date).toLocaleDateString(),
    value: parseFloat(reading.value),
    note: reading.note,
  }));

  if (loading) {
    return <div className="p-8 text-center">Loading meter details...</div>;
  }

  if (error || !meter) {
    return (
      <div className="p-8">
        <Link to="/meters">
          <Button variant="outline" className="mb-4 gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Meters
          </Button>
        </Link>
        <Card>
          <CardContent className="p-8 text-center text-destructive">
            {error || 'Meter not found'}
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
            Back to Meters
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">{meter.label}</h1>
        <span className="text-sm font-medium bg-primary/10 text-primary px-3 py-1 rounded-full capitalize">
          {meter.meter_type} • {meter.unit}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Consumption Chart</CardTitle>
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
                      formatter={(value) => [`${value} ${meter.unit}`, 'Value']}
                      labelFormatter={(label) => `Date: ${label}`}
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
                  No readings available. Add your first reading to see the chart.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Meter Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Type</h3>
                <p className="text-lg capitalize">{meter.meter_type}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Unit</h3>
                <p className="text-lg">{meter.unit}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Created</h3>
                <p className="text-lg">{new Date(meter.created_at).toLocaleDateString()}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">Total Readings</h3>
                <p className="text-lg">{readings.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex justify-between items-center">
              <span>Recent Readings</span>
              <Link to="/readings/new">
                <Button size="sm">Add Reading</Button>
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {readings.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Value ({meter.unit})</TableHead>
                    <TableHead>Note</TableHead>
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
                No readings yet. Add your first reading!
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MeterDetail;