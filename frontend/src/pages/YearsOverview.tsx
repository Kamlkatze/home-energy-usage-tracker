import React from 'react';
import { Link } from 'react-router-dom';
import { costsApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
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

const ELECTRIC_TYPES = ['electricity_import', 'electricity_export', 'electricity_production'];
const WATER_TYPES = ['water_cold', 'water_garden'];

const ChartTooltip: React.FC<{ active?: boolean; payload?: any[], label?: any; items: YearsOverviewItem[] }> = ({ active, payload, label, items }) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{
      backgroundColor: 'hsl(var(--popover))',
      color: 'hsl(var(--popover-foreground))',
      border: '1px solid hsl(var(--border))',
      borderRadius: 'var(--radius)',
      padding: '8px 12px',
      fontSize: '12px',
    }}>
      <p style={{ marginBottom: 4, fontWeight: 600 }}>Jahr: {label}</p>
      {payload.map((p: any, idx: number) => {
        const unit = items.find(i => i.meter_label === p.name)?.unit || '';
        const value = typeof p.value === 'number'
          ? (unit === 'kWh' ? `${Math.round(p.value)} ${unit}` : `${p.value.toFixed(2)} ${unit}`)
          : p.value;
        return (
          <p key={idx} style={{ color: p.color, margin: 0 }}>
            {p.name}: {value}
          </p>
        );
      })}
    </div>
  );
};

interface ChartCardProps {
  title: string;
  items: YearsOverviewItem[];
  chartData: Record<string, any>[];
}

const ChartCard: React.FC<ChartCardProps> = ({ title, items, chartData }) => {
  if (items.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="year"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={(v: number) => Math.round(v).toString()}
                label={{ value: 'Verbrauch', angle: -90, position: 'insideLeft', fill: 'hsl(var(--muted-foreground))' }}
              />
              <Tooltip content={<ChartTooltip items={items} />} />
              <Legend
                content={({ payload }) => (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', padding: '8px 0' }}>
                    {payload?.map((entry: any, idx: number) => {
                      const item = items.find(i => i.meter_label === entry.value);
                      const unit = item?.unit || '';
                      return (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <div style={{ width: 12, height: 12, backgroundColor: entry.color, borderRadius: 2 }} />
                          <span style={{ color: 'hsl(var(--foreground))', fontSize: 12 }}>{entry.value} ({unit})</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              />
              {items.map((item, idx) => (
                <Line
                  key={item.meter_id}
                  type="monotone"
                  dataKey={item.meter_label}
                  name={item.meter_label}
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
  );
};

const YearsOverview: React.FC = () => {
  const {
    data,
    loading,
    error,
  } = useFetch<YearsOverviewItem[]>(async () => {
    try {
      return await costsApi.getYearsOverview();
    } catch (err: any) {
      throw new Error(
        err?.response?.data?.detail || err?.message || 'Fehler beim Laden der Jahresübersicht.'
      );
    }
  }, []);

  const items = data ?? [];

  const allYears = [...new Set(items.flatMap((item) => item.years.map((y) => y.year)))].sort(
    (a, b) => a - b
  );

  const tableData = allYears.map((year) => {
    const row: Record<string, any> = { year };
    items.forEach((item) => {
      const entry = item.years.find((y) => y.year === year);
      row[`meter_${item.meter_id}`] = entry?.consumption ?? null;
    });
    return row;
  });

  const buildChartData = (meterItems: YearsOverviewItem[]) =>
    allYears.map((year) => {
      const row: Record<string, any> = { year: String(year) };
      meterItems.forEach((item) => {
        const entry = item.years.find((y) => y.year === year);
        row[item.meter_label] = entry?.consumption ? parseFloat(entry.consumption) : null;
      });
      return row;
    });

  const electricItems = items.filter((i) => ELECTRIC_TYPES.includes(i.meter_type));
  const waterItems = items.filter((i) => WATER_TYPES.includes(i.meter_type));
  const gasItems = items.filter((i) => i.meter_type === 'gas');

  const electricChartData = buildChartData(electricItems);
  const waterChartData = buildChartData(waterItems);
  const gasChartData = buildChartData(gasItems);

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
                          ? `${item.unit === 'kWh' ? Math.round(parseFloat(val)) : parseFloat(val).toFixed(2)} ${item.unit}`
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

      <ChartCard title="Stromverbrauch" items={electricItems} chartData={electricChartData} />
      <ChartCard title="Wasserverbrauch" items={waterItems} chartData={waterChartData} />
      <ChartCard title="Gasverbrauch" items={gasItems} chartData={gasChartData} />
    </div>
  );
};

export default YearsOverview;