import { YearlyProjection } from '../../types';

export function formatEuro(value: string | null): string {
  if (value === null) return '\u2014';
  return `${parseFloat(value).toFixed(2)} \u20AC`;
}

export function basisLabel(basis: YearlyProjection['basis']): string {
  switch (basis) {
    case 'actual_full_year':
      return 'Tats\u00e4chlicher Jahresverbrauch';
    case 'linear_from_prev_year_end':
      return 'Hochrechnung (linear ab Vorjahresende)';
    case 'linear_from_first_reading_of_year':
      return 'Hochrechnung (linear ab erstem Stand im Jahr)';
    case 'insufficient_data':
      return 'Unzureichende Daten';
  }
}

export function niceAxisBounds(dataMin: number, dataMax: number, forceMinZero: boolean): { min: number; max: number } {
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