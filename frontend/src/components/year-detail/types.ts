import { YearsOverviewItem, Reading, YearlyProjection, AdvancePaymentDiffByCategory } from '../../types';
import { Meter } from '../../types';

export interface MeterSection {
  overviewItem: YearsOverviewItem;
  chain: Meter[];
  readings: Reading[];
  projection: YearlyProjection | null;
  projectionLoading: boolean;
  projectionError: string | null;
}

export type AdvancePaymentDiffs = Record<
  'gas' | 'cold_water' | 'wastewater' | 'power_import',
  AdvancePaymentDiffByCategory | null
>;