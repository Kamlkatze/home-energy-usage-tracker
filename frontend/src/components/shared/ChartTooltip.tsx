import React from 'react';

// Read once at module load instead of calling Date.now() during render
// (forbidden by react-hooks/purity): "future" data points are relative
// to the time the chart module was loaded with the page.
const LOAD_TIME_MS = Date.now();

// Line names that represent projections/estimates rather than real readings.
const PROJECTED_NAME_PATTERN = /(Hochrechnung|\(prog\.\))/;

interface ChartTooltipEntry {
  name?: string | number;
  value?: number | string;
  color?: string;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: ChartTooltipEntry[];
  label?: number | string;
  unit?: string;
}

// Custom tooltips must be defined at module level (not inside the render
// function) so their reference stays stable for Recharts; dynamic values like
// `unit` are passed in as props.
const ChartTooltip: React.FC<ChartTooltipProps> = ({ active, payload, label, unit }) => {
  if (!active || !payload || payload.length === 0) return null;

  // Projection lines are only shown once the hovered date lies in the future
  // (relative to module load); real readings are always shown.
  const isFuture = typeof label === 'number' ? label > LOAD_TIME_MS : false;
  const filteredPayload = isFuture
    ? payload
    : payload.filter((p) => !PROJECTED_NAME_PATTERN.test(String(p.name ?? '')));
  if (filteredPayload.length === 0) return null;

  const fmtValue = (v: number): string =>
    unit === 'kWh' ? Math.round(v).toString() : v.toFixed(1);

  return (
    <div
      style={{
        backgroundColor: 'hsl(var(--popover))',
        color: 'hsl(var(--popover-foreground))',
        border: '1px solid hsl(var(--border))',
        borderRadius: 'var(--radius)',
        padding: '8px 12px',
        fontSize: '12px',
      }}
    >
      <p style={{ marginBottom: 4, fontWeight: 600 }}>
        Datum:{' '}
        {typeof label === 'number' ? new Date(label).toLocaleDateString() : label ?? '—'}
      </p>
      {filteredPayload.map((p, idx) => (
        <p key={idx} style={{ color: p.color, margin: 0 }}>
          {p.name}:{' '}
          {typeof p.value === 'number'
            ? unit
              ? `${fmtValue(p.value)} ${unit}`
              : fmtValue(p.value)
            : p.value}
        </p>
      ))}
    </div>
  );
};

export default ChartTooltip;
