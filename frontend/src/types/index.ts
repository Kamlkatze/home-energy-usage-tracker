export type MeterType =
  | 'gas'
  | 'water_cold'
  | 'water_garden'
  | 'electricity_import'
  | 'electricity_export'
  | 'electricity_production';

export type TariffKind = 'consumption' | 'feed_in' | 'self_consumption' | 'wastewater' | 'feed_in_eeg2009';

// One entry of GET /api/meters/types: the unit is server-derived from
// the meter type and not configurable by the client.
export interface MeterTypeInfo {
  value: MeterType;
  label: string;
  unit: string;
}

export interface MeterUpdateData {
  meter_type?: MeterType;
  label?: string;
  meter_number?: string | null;
  replaces_meter_id?: number | null;
}

export interface Meter {
  id: number;
  meter_type: MeterType;
  label: string;
  meter_number: string | null;
  unit: string;
  created_at: string;
  // ID des Vorgänger-Zählers, den dieser Zähler ersetzt (null = kein Vorgänger)
  replaces_meter_id: number | null;
}

export interface Reading {
  id: number;
  meter_id: number;
  value: string;
  reading_date: string;
  note: string | null;
  created_at: string;
}

export interface TariffPeriod {
  id: number;
  meter_id: number;
  tariff_kind: TariffKind;
  valid_from: string;
  valid_to: string | null;
  price_per_unit: string;
  base_fee_monthly: string | null;
  metering_fee_monthly: string | null;
  gas_z_zahl: string | null;
  gas_brennwert: string | null;
  eeg_tier1_rate: string | null;
  eeg_tier2_rate: string | null;
  metering_point_fee_yearly: string | null;
  created_at: string;
}

export interface TariffUsage {
  tariff_id: number;
  meter_id: number;
  reading_count: number;
  first_reading_date: string | null;
  last_reading_date: string | null;
  in_use: boolean;
}

export interface YearEntry {
  year: number;
  consumption: string | null;
  cost: string | null;
  cost_basis: 'actual' | 'projected' | null;
}

export interface YearsOverviewItem {
  meter_id: number;
  meter_label: string;
  meter_type: string;
  unit: string;
  years: YearEntry[];
}

export interface YearlyProjection {
  meter_id: number;
  year: number;
  unit: string;
  as_of_date: string;
  actual_consumption_to_date: string | null;
  projected_annual_consumption: string | null;
  basis: 'linear_from_prev_year_end' | 'linear_from_first_reading_of_year' | 'actual_full_year' | 'insufficient_data';
  actual_cost_to_date: string | null;
  projected_annual_cost: string | null;
  message: string | null;
}

export interface FeedInCompensation {
  production_meter_id: number;
  export_meter_id: number;
  from_date: string;
  to_date: string;
  production_consumption: string;
  export_consumption: string;
  self_consumption: string;
  tier1_kwh: string;
  tier2_kwh: string;
  total_compensation: string;
}

export interface WastewaterCosts {
  water_cold_meter_id: number;
  water_garden_meter_id: number | null;
  from_date: string;
  to_date: string;
  cold_consumption: string;
  garden_consumption: string;
  wastewater_consumption: string;
  unit: string;
  price_per_unit: string;
  base_fee_total: string;
  total_cost: string;
}