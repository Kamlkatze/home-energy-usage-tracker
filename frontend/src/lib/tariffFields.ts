import { TariffKind } from '../types';

export const TARIFF_KIND_LABELS: Record<TariffKind, string> = {
  consumption: 'Arbeitspreis (mit optionalen Grund- und Messentgelten)',
  feed_in: 'Einspeisevergütung (fester Satz)',
  self_consumption: 'Selbstverbrauchsvergütung',
  wastewater: 'Abwasserkosten',
  feed_in_eeg2009: 'Einspeisevergütung nach EEG 2009 (mit Eigenverbrauch)',
};

export const TARIFF_KINDS = Object.keys(TARIFF_KIND_LABELS) as TariffKind[];

export interface FieldConfig {
  name: string;
  label: string;
  required: boolean;
  helperText?: string;
  placeholder?: string;
  step: string;
  group?: 'eeg';
}

export function getTariffFields(
  kind: TariffKind,
  meterType?: string | null,
  meterUnit?: string | null,
): FieldConfig[] {
  const isGasConsumption = meterType === 'gas' && kind === 'consumption';

  switch (kind) {
    case 'consumption': {
      const priceUnit = isGasConsumption ? '€/kWh' : `€/${meterUnit ?? ''}`;
      const fields: FieldConfig[] = [
        {
          name: 'price_per_unit',
          label: `Preis pro Einheit (${priceUnit})`,
          required: true,
          step: '0.00001',
          ...(isGasConsumption && {
            helperText: 'Wird aus m³ über Z-Zahl und Brennwert in kWh umgerechnet.',
          }),
        },
      ];
      if (isGasConsumption) {
        fields.push(
          {
            name: 'gas_z_zahl',
            label: 'Zustandszahl (z-Zahl)',
            required: true,
            placeholder: '0.96280',
            step: '0.00001',
          },
          {
            name: 'gas_brennwert',
            label: 'Brennwert (kWh/m³)',
            required: true,
            placeholder: '11.42500',
            step: '0.00001',
          },
        );
      }
      fields.push(
        {
          name: 'base_fee_monthly',
          label: 'Grundpreis monatlich',
          required: false,
          placeholder: 'z. B. 12.50',
          step: '0.01',
        },
        {
          name: 'metering_fee_monthly',
          label: 'Messentgelt monatlich',
          required: false,
          placeholder: 'z. B. 5.80',
          step: '0.01',
        },
      );
      return fields;
    }

    case 'feed_in':
      return [
        {
          name: 'price_per_unit',
          label: 'Preis pro Einheit (€/kWh)',
          required: true,
          step: '0.00001',
        },
        {
          name: 'metering_fee_monthly',
          label: 'Messentgelt monatlich',
          required: false,
          placeholder: 'z. B. 5.80',
          step: '0.01',
        },
      ];

    case 'self_consumption':
      return [
        {
          name: 'price_per_unit',
          label: 'Preis pro Einheit (€/kWh)',
          required: true,
          step: '0.00001',
        },
      ];

    case 'wastewater':
      return [
        {
          name: 'price_per_unit',
          label: 'Preis pro Einheit (€/m³)',
          required: true,
          step: '0.00001',
        },
      ];

    case 'feed_in_eeg2009':
      return [
        {
          name: 'price_per_unit',
          label: 'Grundvergütungssatz (€/kWh)',
          required: true,
          helperText: 'Vergütung auf die gesamte PV-Erzeugung.',
          step: '0.00001',
          group: 'eeg',
        },
        {
          name: 'eeg_tier1_rate',
          label: 'Abzug Eigenverbrauch bis 30 % (€/kWh)',
          required: true,
          helperText:
            'Abzug für den Anteil des Eigenverbrauchs bis zu 30 % der Gesamterzeugung.',
          step: '0.00001',
          group: 'eeg',
        },
        {
          name: 'eeg_tier2_rate',
          label: 'Abzug Eigenverbrauch über 30 % (€/kWh)',
          required: true,
          helperText:
            'Abzug für den Anteil des Eigenverbrauchs, der 30 % der Gesamterzeugung übersteigt.',
          step: '0.00001',
          group: 'eeg',
        },
        {
          name: 'metering_point_fee_yearly',
          label: 'Messstellenbetrieb (€/Jahr)',
          required: true,
          helperText: 'Jährliche Pauschale, wird taggenau anteilig berechnet.',
          step: '0.01',
          group: 'eeg',
        },
      ];
  }
}

export function getPriceUnitLabel(
  kind: TariffKind,
  meterType?: string | null,
  meterUnit?: string | null,
): string {
  if (kind === 'wastewater') return '€/m³';
  if (kind === 'consumption' && meterType === 'gas') return '€/kWh';
  return `€/${meterUnit ?? ''}`;
}