import React from 'react';
import { MeterSection, AdvancePaymentDiffs } from './types';
import { formatEuro, basisLabel } from './utils';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Flame } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316',
];

const ChartTooltip: React.FC<{ active?: boolean; payload?: any[]; label?: any; unit: string }> = ({ active, payload, label, unit }) => {
  if (!active || !payload || payload.length === 0) return null;
  const isFuture = typeof label === 'number' ? label > Date.now() : false;
  const filteredPayload = isFuture
    ? payload
    : payload.filter((p: any) => p.name !== 'Hochrechnung');
  if (filteredPayload.length === 0) return null;
  return (
    <div style={{
      backgroundColor: 'hsl(var(--popover))',
      color: 'hsl(var(--popover-foreground))',
      border: '1px solid hsl(var(--border))',
      borderRadius: 'var(--radius)',
      padding: '8px 12px',
      fontSize: '12px',
    }}>
      <p style={{ marginBottom: 4, fontWeight: 600 }}>
        Datum: {label ? new Date(label).toLocaleDateString() : '—'}
      </p>
      {filteredPayload.map((p: any, idx: number) => (
        <p key={idx} style={{ color: p.color, margin: 0 }}>
          {p.name}: {typeof p.value === 'number' ? `${p.value} ${unit}` : p.value}
        </p>
      ))}
    </div>
  );
};

interface GasMeterViewProps {
  section: MeterSection;
  meterIdx: number;
  advancePaymentDiffs: AdvancePaymentDiffs;
  year: number;
}

const GasMeterView: React.FC<GasMeterViewProps> = ({ section, meterIdx, advancePaymentDiffs, year }) => {
  const item = section.overviewItem;
  const unit = item.unit;
  const chartColor = COLORS[meterIdx % COLORS.length];

  const formatConsumption = (value: string | null): string => {
    if (value === null) return '—';
    const num = parseFloat(value);
    return unit === 'kWh' ? `${Math.round(num)} ${unit}` : `${num.toFixed(1)} ${unit}`;
  };

  const formatReadingValue = (value: string): string =>
    unit === 'kWh' ? Math.round(parseFloat(value)).toString() : value;

  const startOfYear = new Date(year, 0, 1).getTime();
  const startOfNextYear = new Date(year + 1, 0, 1).getTime();

  const chartData = section.readings.map((r) => ({
    date: new Date(r.reading_date).toLocaleDateString(),
    timestamp: new Date(r.reading_date).getTime(),
    value: parseFloat(r.value),
    note: r.note,
  }));

  const roundValue = (v: number): number =>
    unit.includes('m³') ? Math.round(v * 100) / 100 : Math.round(v);

  const lastPoint = chartData.length > 0 ? chartData[chartData.length - 1] : null;
  const rawProjectionValue = section.projection?.projected_meter_reading_end_of_year;
  const projectionData = rawProjectionValue
    ? [
        lastPoint
          ? { timestamp: lastPoint.timestamp, value: lastPoint.value }
          : { timestamp: startOfYear, value: 0 },
        { timestamp: startOfNextYear, value: roundValue(parseFloat(rawProjectionValue)) },
      ]
    : [];

  const showProjection = projectionData.length > 0
    && section.projection
    && section.projection.basis !== 'actual_full_year'
    && section.projection.basis !== 'insufficient_data';

  const combinedData: Array<{
    timestamp: number;
    date: string;
    value: number | undefined;
    note: string | null;
    projectedValue: number | undefined;
    isProjectionEnd: boolean;
  }> = (() => {
    const data = chartData.map(d => ({ ...d, projectedValue: undefined as number | undefined, isProjectionEnd: false }));
    if (showProjection && projectionData.length >= 2) {
      if (data.length > 0) {
        data[data.length - 1].projectedValue = data[data.length - 1].value;
      } else {
        data.push({
          timestamp: startOfYear,
          date: '',
          value: 0,
          note: null,
          projectedValue: 0,
          isProjectionEnd: false,
        });
      }
      data.push({
        timestamp: startOfNextYear,
        date: '',
        value: undefined as any,
        note: null,
        projectedValue: projectionData[1].value,
        isProjectionEnd: true,
      });
      data.sort((a, b) => a.timestamp - b.timestamp);
    }
    return data;
  })();

  const yValues = [
    ...chartData.map(d => d.value),
    ...(showProjection ? projectionData.map(d => d.value) : []),
  ];
  const yMin = yValues.length > 0 ? Math.min(...yValues) : 0;
  const yMax = yValues.length > 0 ? Math.max(...yValues) : 1;
  const yPadding = (yMax - yMin) * 0.1 || 1;

  const projection = section.projection;
  const actualCons = projection?.actual_consumption_to_date ?? null;
  const projCons = projection?.projected_annual_consumption ?? null;
  const actualCost = projection?.actual_cost_to_date ?? null;
  const projCost = projection?.projected_annual_cost ?? null;

  const gasDiff = advancePaymentDiffs['gas'];

  return (
    <div className="border rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold text-sm">{item.meter_label}</h4>
        <span className="text-xs font-medium bg-primary/10 text-primary px-2 py-0.5 rounded-full">
          {item.meter_type}
        </span>
      </div>
      {section.chain.length > 1 && (
        <p className="text-xs text-muted-foreground">
          Ersetzungskette: {section.chain.map((m) => m.label).join(' → ')}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="bg-muted rounded p-2">
          <p className="text-xs text-muted-foreground">Verbrauch tatsächlich {year}</p>
          <p className="text-sm font-semibold">{formatConsumption(actualCons)}</p>
        </div>
        <div className="bg-muted rounded p-2">
          <p className="text-xs text-muted-foreground">Verbrauch prognostiziert {year}</p>
          <p className="text-sm font-semibold">{formatConsumption(projCons)}</p>
          {projection && projection.basis !== 'actual_full_year' && projCons != null && (
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Basis: {basisLabel(projection.basis)}
            </p>
          )}
        </div>
      </div>

      <div>
        <h5 className="text-xs font-semibold text-muted-foreground mb-1">Verbrauchsverlauf {year}</h5>
        <div className="h-48">
          {combinedData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={combinedData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="timestamp"
                  domain={[startOfYear, startOfNextYear]}
                  tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                  tickFormatter={(ts: number) => {
                    const d = new Date(ts);
                    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.`;
                  }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <YAxis
                  domain={[yMin - yPadding, yMax + yPadding]}
                  label={{ value: unit, angle: -90, position: 'insideLeft', fill: 'hsl(var(--muted-foreground))' }}
                  tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                  tickFormatter={(v: number) => Math.round(v).toString()}
                  stroke="hsl(var(--muted-foreground))"
                />
                <Tooltip content={<ChartTooltip unit={unit} />} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={chartColor}
                  strokeWidth={1.5}
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                  name="Zählerstand"
                />
                {showProjection && (
                  <Line
                    type="monotone"
                    dataKey="projectedValue"
                    stroke={chartColor}
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={(props: any) =>
                      props.payload.isProjectionEnd
                        ? <circle cx={props.cx} cy={props.cy} r={3} fill={chartColor} />
                        : <></>
                    }
                    activeDot={false}
                    name="Hochrechnung"
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              Keine Zählerstände für {year} vorhanden.
            </div>
          )}
        </div>
      </div>

      <div>
        <h5 className="text-xs font-semibold text-muted-foreground mb-1">Zählerstände {year}</h5>
        <div className="max-h-36 overflow-y-auto">
          {section.readings.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Datum</TableHead>
                  <TableHead className="text-xs">Wert ({unit})</TableHead>
                  <TableHead className="text-xs">Notiz</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {section.readings.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-xs py-1">{new Date(r.reading_date).toLocaleDateString()}</TableCell>
                    <TableCell className="text-xs py-1">{formatReadingValue(r.value)}</TableCell>
                    <TableCell className="text-xs py-1">{r.note || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-4 text-xs text-muted-foreground">
              Keine Zählerstände für {year} vorhanden.
            </div>
          )}
        </div>
      </div>

      <div className="border rounded-lg p-3 bg-muted/20">
        <h5 className="text-xs font-semibold text-muted-foreground mb-1">Kosten {year}</h5>
<div className="grid grid-cols-2 gap-1">
          <div className="bg-muted rounded p-1.5">
            <p className="text-[10px] text-muted-foreground">Verbrauch tatsächlich</p>
            <p className="text-xs font-semibold">{formatConsumption(actualCons)}</p>
          </div>
          <div className="bg-muted rounded p-1.5">
            <p className="text-[10px] text-muted-foreground">Kosten tatsächlich</p>
            <p className="text-xs font-semibold">{actualCost != null ? formatEuro(actualCost) : '—'}</p>
          </div>
          <div className="bg-muted rounded p-1.5">
            <p className="text-[10px] text-muted-foreground">Verbrauch prognostiziert</p>
            <p className="text-xs font-semibold">{formatConsumption(projCons)}</p>
          </div>
          <div className="bg-muted rounded p-1.5">
            <p className="text-[10px] text-muted-foreground">Kosten prognostiziert</p>
            <p className="text-xs font-semibold">{projCost != null ? formatEuro(projCost) : '—'}</p>
          </div>
          {gasDiff ? (
            <>
              <div className="bg-muted rounded p-1.5">
                <p className="text-[10px] text-muted-foreground">Abschlagszahlungen hochgerechnet</p>
                <p className="text-xs font-semibold">
                  {gasDiff.total_advance_payments != null ? formatEuro(gasDiff.total_advance_payments) : '—'}
                </p>
              </div>
              <div className="bg-muted rounded p-1.5">
                <p className="text-[10px] text-muted-foreground">Differenz Abschläge zu Kosten</p>
                <p className="text-xs font-semibold" style={{
                  color: gasDiff.difference != null
                    ? (parseFloat(gasDiff.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                    : undefined,
                }}>
                  {gasDiff.difference != null ? formatEuro(gasDiff.difference) : '—'}
                </p>
              </div>
            </>
          ) : (
            <div className="col-span-2 bg-muted rounded p-1.5">
              <p className="text-xs text-muted-foreground">Kein Abschlag für Gas hinterlegt.</p>
            </div>
          )}
        </div>
        {projection && (
          <p className="text-[10px] text-muted-foreground mt-1">
            Basis: {basisLabel(projection.basis)}
          </p>
        )}
        {projection?.message && (
          <p className="text-[10px] text-muted-foreground mt-0.5">{projection.message}</p>
        )}
      </div>
    </div>
  );
};

interface GasSectionProps {
  sections: MeterSection[];
  advancePaymentDiffs: AdvancePaymentDiffs;
  year: number;
}

const GasSection: React.FC<GasSectionProps> = ({ sections, advancePaymentDiffs, year }) => {
  if (sections.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Flame className="h-4 w-4" />
          Gas {year}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {sections.map((section, idx) => (
          <GasMeterView
            key={section.overviewItem.meter_id}
            section={section}
            meterIdx={idx}
            advancePaymentDiffs={advancePaymentDiffs}
            year={year}
          />
        ))}
      </CardContent>
    </Card>
  );
};

export default GasSection;