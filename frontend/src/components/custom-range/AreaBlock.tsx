import React from 'react';
import { ConsumptionTimeseriesItem } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  COLORS, niceAxisBounds, formatConsumption, formatReadingValue, formatEuro,
} from '../shared/chartHelpers';
import ChartTooltip from '../shared/ChartTooltip';

interface AreaChartPoint {
  timestamp: number;
  [meterKey: string]: number | undefined;
}

// Merges each meter's real reading points into a single date-sorted array.
// One key per meter (`m_<meter_id>`) holds its consumption since the
// previous reading; only actually entered readings are included.
function buildAreaChartData(items: ConsumptionTimeseriesItem[]): AreaChartPoint[] {
  const map = new Map<number, AreaChartPoint>();

  for (const item of items) {
    const meterKey = `m_${item.meter_id}`;
    for (const point of item.points) {
      const timestamp = new Date(`${point.date}T00:00:00`).getTime();
      const row = map.get(timestamp) ?? { timestamp };
      if (point.consumption_since_previous != null) {
        row[meterKey] = parseFloat(point.consumption_since_previous);
      }
      map.set(timestamp, row);
    }
  }

  return Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);
}

interface AreaBlockProps {
  title: string;
  icon: React.ReactNode;
  items: ConsumptionTimeseriesItem[];
}

const AreaBlock: React.FC<AreaBlockProps> = ({ title, icon, items }) => {
  const unit = items.length > 0 ? items[0].unit : '';

  const chartData = buildAreaChartData(items);
  const numericValues = chartData.flatMap((row) =>
    items.map((item) => row[`m_${item.meter_id}`])
  ).filter((v): v is number => v !== undefined);
  const bounds = niceAxisBounds(
    numericValues.length > 0 ? Math.min(...numericValues) : 0,
    numericValues.length > 0 ? Math.max(...numericValues) : 1,
    true
  );

  const tableRows = items.flatMap((item) =>
    item.points.map((point) => ({
      key: `${item.meter_id}-${point.date}`,
      date: point.date,
      meterLabel: item.meter_label,
      value: point.value,
      consumption: point.consumption_since_previous,
      cost: point.cost_since_previous,
    }))
  ).sort((a, b) => a.date.localeCompare(b.date) || a.meterLabel.localeCompare(b.meterLabel));

  const hasChartData = numericValues.length > 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Keine Messpunkte im gewählten Zeitraum vorhanden.
          </p>
        ) : (
          <>
            <div>
              <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                Verbrauch in {unit}
              </h5>
              <div className="h-64">
                {hasChartData ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        type="number"
                        dataKey="timestamp"
                        domain={['dataMin', 'dataMax']}
                        tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                        tickFormatter={(ts: number) => {
                          const d = new Date(ts);
                          return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.`;
                        }}
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <YAxis
                        domain={[bounds.min, bounds.max]}
                        label={{ value: unit, angle: -90, position: 'insideLeft', fill: 'hsl(var(--muted-foreground))' }}
                        tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                        tickFormatter={(v: number) => Math.round(v).toString()}
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <Tooltip content={<ChartTooltip unit={unit} />} />
                      {items.map((item, idx) => (
                        <Line
                          key={item.meter_id}
                          type="monotone"
                          dataKey={`m_${item.meter_id}`}
                          name={item.meter_label}
                          stroke={COLORS[idx % COLORS.length]}
                          strokeWidth={1.5}
                          dot={{ r: 2 }}
                          activeDot={{ r: 4 }}
                          connectNulls
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                    Keine Verbrauchswerte im gewählten Zeitraum vorhanden.
                  </div>
                )}
              </div>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-muted-foreground mb-1">Messpunkte</h5>
              <div className="max-h-72 overflow-y-auto">
                {tableRows.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Datum</TableHead>
                        <TableHead className="text-xs">Zähler</TableHead>
                        <TableHead className="text-xs">Zählerstand ({unit})</TableHead>
                        <TableHead className="text-xs">Verbrauch</TableHead>
                        <TableHead className="text-xs">Kosten</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tableRows.map((row) => (
                        <TableRow key={row.key}>
                          <TableCell className="text-xs py-1">
                            {new Date(`${row.date}T00:00:00`).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-xs py-1">{row.meterLabel}</TableCell>
                          <TableCell className="text-xs py-1">
                            {formatReadingValue(row.value, unit)}
                          </TableCell>
                          <TableCell className="text-xs py-1">
                            {row.consumption != null ? formatConsumption(row.consumption, unit) : '\u2014'}
                          </TableCell>
                          <TableCell className="text-xs py-1">
                            {row.cost != null ? formatEuro(row.cost) : '\u2014'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Keine Messpunkte im gewählten Zeitraum vorhanden.
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default AreaBlock;
