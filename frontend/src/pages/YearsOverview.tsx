import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { costsApi } from '../api/client';
import { YearsOverviewItem } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table';
import { Loader2 } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316',
];

const YearsOverview: React.FC = () => {
  const [items, setItems] = useState<YearsOverviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await costsApi.getYearsOverview();
      setItems(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err?.message || 'Fehler beim Laden der Jahresübersicht.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const allYears = [...new Set(items.flatMap((item) => item.years.map((y) => y.year)))].sort(
    (a, b) => b - a
  );

  const tableData = allYears.map((year) => {
    const row: Record<string, any> = { year };
    items.forEach((item) => {
      const entry = item.years.find((y) => y.year === year);
      row[`meter_${item.meter_id}`] = entry?.consumption ?? null;
    });
    return row;
  });

  const chartData = allYears.map((year) => {
    const row: Record<string, any> = { year: String(year) };
    items.forEach((item) => {
      const entry = item.years.find((y) => y.year === year);
      row[item.meter_label] = entry?.consumption ? parseFloat(entry.consumption) : null;
    });
    return row;
  });

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Jahresübersicht...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center text-destructive">
            {error}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Keine Zählerstände vorhanden.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">Jahresübersicht</h2>

      <Card>
        <CardHeader>
          <CardTitle>Verbrauch pro Jahr</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Jahr</TableHead>
                {items.map((item) => (
                  <TableHead key={item.meter_id}>
                    {item.meter_label} ({item.unit})
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {tableData.map((row) => (
                <TableRow key={row.year}>
                  <TableCell className="font-medium">
                    <Link to={`/years/${row.year}`} className="text-primary underline">
                      {row.year}
                    </Link>
                  </TableCell>
                  {items.map((item) => {
                    const val = row[`meter_${item.meter_id}`];
                    return (
                      <TableCell key={item.meter_id}>
                        {val != null
                          ? `${item.unit === 'kWh' ? Math.round(parseFloat(val)) : parseFloat(val).toFixed(1)} ${item.unit}`
                          : '—'}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verbrauchsverlauf</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis />
                <Tooltip />
                <Legend />
                {items.map((item, idx) => (
                  <Line
                    key={item.meter_id}
                    type="monotone"
                    dataKey={item.meter_label}
                    name={`${item.meter_label} (${item.unit})`}
                    stroke={COLORS[idx % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default YearsOverview;