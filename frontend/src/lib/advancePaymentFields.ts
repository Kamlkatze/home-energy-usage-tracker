import { AdvancePaymentCategory } from '../types';
import { Meter } from '../types';

export const ADVANCE_PAYMENT_CATEGORY_LABELS: Record<AdvancePaymentCategory, string> = {
  gas: 'Gas',
  cold_water: 'Kaltwasser',
  wastewater: 'Abwasser',
  power_import: 'Strombezug',
};

export const ADVANCE_PAYMENT_CATEGORIES = Object.keys(ADVANCE_PAYMENT_CATEGORY_LABELS) as AdvancePaymentCategory[];

export interface MeterField {
  name: string;
  label: string;
  required: boolean;
  meterType: string;
  allowNull?: boolean;
  nullLabel?: string;
}

export function getMeterFieldsForCategory(category: AdvancePaymentCategory): MeterField[] {
  switch (category) {
    case 'gas':
      return [{ name: 'meter_id', label: 'Gas-Zähler', required: true, meterType: 'gas' }];
    case 'cold_water':
      return [{ name: 'meter_id', label: 'Kaltwasser-Zähler', required: true, meterType: 'water_cold' }];
    case 'power_import':
      return [{ name: 'meter_id', label: 'Strombezugs-Zähler', required: true, meterType: 'electricity_import' }];
    case 'wastewater':
      return [
        { name: 'water_cold_meter_id', label: 'Kaltwasserzähler', required: true, meterType: 'water_cold' },
        { name: 'water_garden_meter_id', label: 'Gartenwasserzähler', required: false, meterType: 'water_garden', allowNull: true, nullLabel: 'kein Gartenzähler vorhanden' },
      ];
  }
}

export function filterMetersForCategory(meters: Meter[], field: MeterField): Meter[] {
  return meters.filter((m) => m.meter_type === field.meterType);
}