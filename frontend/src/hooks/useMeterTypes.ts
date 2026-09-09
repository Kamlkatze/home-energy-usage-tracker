import { useEffect, useState } from 'react';
import { metersApi } from '../api/client';
import { MeterType, MeterTypeInfo } from '../types';

// Module-level cache: meter types are static, so they are fetched once
// per session and reused across all components.
let cachedTypes: MeterTypeInfo[] | null = null;

export const useMeterTypes = (): MeterTypeInfo[] => {
  const [meterTypes, setMeterTypes] = useState<MeterTypeInfo[]>(
    cachedTypes ?? []
  );

  useEffect(() => {
    if (cachedTypes) {
      return;
    }
    metersApi
      .getTypes()
      .then((data) => {
        cachedTypes = data;
        setMeterTypes(data);
      })
      .catch((err) => {
        console.error('Error fetching meter types:', err);
      });
  }, []);

  return meterTypes;
};

// German display label for a meter type; falls back to the raw value
// while types are still loading or if the request failed.
export const meterTypeLabel = (
  meterTypes: MeterTypeInfo[],
  value: MeterType
): string => meterTypes.find((type) => type.value === value)?.label ?? value;
