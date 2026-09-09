export type MeterType =
  | 'gas'
  | 'water_cold'
  | 'water_garden'
  | 'electricity_import'
  | 'electricity_export'
  | 'electricity_production';

export type TariffKind = 'consumption' | 'base_fee' | 'feed_in' | 'self_consumption' | 'metering_fee';

// One entry of GET /api/meters/types: the unit is server-derived from
// the meter type and not configurable by the client.
export interface MeterTypeInfo {
  value: MeterType;
  label: string;
  unit: string;
}

export interface Meter {
  id: number;
  meter_type: MeterType;
  label: string;
  meter_number: string | null;
  unit: string;
  created_at: string;
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
  created_at: string;
}