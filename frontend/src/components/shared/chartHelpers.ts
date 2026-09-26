// Shared formatting and chart-scaling helpers used by the year-bound
// sections (MeterBlock, GasSection, WaterSection) and the custom-range page.

export const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316',
];

export function formatEuro(value: string | null): string {
  if (value === null) return '\u2014';
  return `${parseFloat(value).toFixed(2)} \u20AC`;
}

export function formatConsumption(value: string | null, unit: string): string {
  if (value === null) return '\u2014';
  const num = parseFloat(value);
  return unit === 'kWh' ? `${Math.round(num)} ${unit}` : `${num.toFixed(1)} ${unit}`;
}

export function formatReadingValue(value: string, unit: string): string {
  return unit === 'kWh' ? Math.round(parseFloat(value)).toString() : value;
}

export function niceAxisBounds(
  dataMin: number,
  dataMax: number,
  forceMinZero: boolean
): { min: number; max: number } {
  const minVal = forceMinZero ? 0 : Math.max(0, dataMin);
  const maxVal = Math.max(dataMax, minVal + 0.1);
  const range = maxVal - minVal;

  const niceSteps = [2, 4, 10, 20, 40, 100, 200, 400, 1000, 2000, 4000, 10000];
  let step = niceSteps[0];
  for (const s of niceSteps) {
    if (range / s <= 8) {
      step = s;
      break;
    }
    step = s;
  }

  return {
    min: Math.floor(minVal / step) * step,
    max: Math.ceil(maxVal / step) * step,
  };
}
