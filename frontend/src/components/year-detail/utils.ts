import { YearlyProjection } from '../../types';

export function formatEuro(value: string | null): string {
  if (value === null) return '—';
  return `${parseFloat(value).toFixed(2)} €`;
}

export function basisLabel(basis: YearlyProjection['basis']): string {
  switch (basis) {
    case 'actual_full_year':
      return 'Tatsächlicher Jahresverbrauch';
    case 'linear_from_prev_year_end':
      return 'Hochrechnung (linear ab Vorjahresende)';
    case 'linear_from_first_reading_of_year':
      return 'Hochrechnung (linear ab erstem Stand im Jahr)';
    case 'insufficient_data':
      return 'Unzureichende Daten';
  }
}