export type MeterType = 'electricity' | 'gas' | 'water';

export interface Meter {
  id: number;
  meter_type: MeterType;
  label: string;
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
  valid_from: string;
  valid_to: string | null;
  price_per_unit: string;
  base_fee_monthly: string | null;
  created_at: string;
}