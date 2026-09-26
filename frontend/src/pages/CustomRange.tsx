import React, { useState } from 'react';
import { Zap, Droplets, Flame, Loader2, type LucideIcon } from 'lucide-react';
import { costsApi, electricityApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { ConsumptionTimeseriesItem, FeedInCompensation, MeterType } from '../types';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import AreaBlock from '../components/custom-range/AreaBlock';
import { formatEuro } from '../components/shared/chartHelpers';

// Earliest date used by the "Alle Daten" quick select until the actual first
// reading is known (the API omits empty periods, so 2000 is safe).
const EARLIEST_DATA_PLACEHOLDER = '2000-01-01';

// Read once at module load instead of calling Date.now() during render
// (forbidden by react-hooks/purity): the default range is the current year.
const MODULE_LOAD_DATE = new Date();
const DEFAULT_FROM = `${MODULE_LOAD_DATE.getFullYear()}-01-01`;
const DEFAULT_TO = toDateInputValue(MODULE_LOAD_DATE);

const QUICK_SELECTS: { id: QuickSelectId; label: string }[] = [
  { id: 'last_12_months', label: 'Letzte 12 Monate' },
  { id: 'current_year', label: 'Aktuelles Jahr' },
  { id: 'last_year', label: 'Letztes Jahr' },
  { id: 'all_data', label: 'Alle Daten' },
];

const FILTER_TOGGLES = [
  { key: 'electricity', label: 'Strom' },
  { key: 'water', label: 'Wasser' },
  { key: 'gas', label: 'Gas' },
] as const;

type QuickSelectId = 'last_12_months' | 'current_year' | 'last_year' | 'all_data';
type FilterKey = typeof FILTER_TOGGLES[number]['key'];

type FilterState = Record<FilterKey, boolean>;

const INITIAL_FILTERS: FilterState = {
  electricity: true,
  water: true,
  gas: true,
};

// Meter types belonging to each filter area.
const AREA_METER_TYPES: Record<FilterKey, MeterType[]> = {
  electricity: ['electricity_import', 'electricity_export', 'electricity_production'],
  water: ['water_cold', 'water_garden'],
  gas: ['gas'],
};

const AREA_LABELS: Record<FilterKey, string> = {
  electricity: 'Strom',
  water: 'Wasser',
  gas: 'Gas',
};

const AREA_ICONS: Record<FilterKey, LucideIcon> = {
  electricity: Zap,
  water: Droplets,
  gas: Flame,
};

const ALL_METER_TYPES: MeterType[] = [...new Set(Object.values(AREA_METER_TYPES).flat())];

// Formats a Date as the YYYY-MM-DD value used by native <input type="date">.
function toDateInputValue(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, date.getDate());
}

function getErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || (err instanceof Error ? err.message : fallback);
}

function formatDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString();
}

const CustomRange: React.FC = () => {
  const [fromDate, setFromDate] = useState(DEFAULT_FROM);
  const [toDate, setToDate] = useState(DEFAULT_TO);
  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS);
  const [appliedRange, setAppliedRange] = useState({ from: DEFAULT_FROM, to: DEFAULT_TO });

  const { data, loading, error } = useFetch<ConsumptionTimeseriesItem[]>(async () => {
    const activeTypes = (Object.keys(AREA_METER_TYPES) as FilterKey[]).flatMap(
      (area) => (filters[area] ? AREA_METER_TYPES[area] : [])
    );
    if (activeTypes.length === 0) return [];
    try {
      // One unfiltered request when all meter types are requested (cheapest);
      // otherwise parallel per-type requests, following the Promise.all
      // pattern already used across the app (e.g. YearDetail).
      if (activeTypes.length === ALL_METER_TYPES.length) {
        return await costsApi.getConsumptionTimeseries(appliedRange.from, appliedRange.to);
      }
      const results = await Promise.all(
        activeTypes.map((type) =>
          costsApi.getConsumptionTimeseries(appliedRange.from, appliedRange.to, type)
        )
      );
      return results.flat();
    } catch (err: unknown) {
      throw new Error(getErrorMessage(err, 'Fehler beim Laden der Zeitreihen.'));
    }
  }, [appliedRange.from, appliedRange.to, filters.electricity, filters.water, filters.gas]);

  const prodMeter = (data ?? []).find((i) => i.meter_type === 'electricity_production');
  const expMeter = (data ?? []).find((i) => i.meter_type === 'electricity_export');

  // EEG 2009 feed-in compensation for the selected period (a range-based total,
  // not a per-reading value). Only meaningful when both a production and an
  // export meter exist and the electricity area is active.
  const { data: eeg, loading: eegLoading, error: eegError } = useFetch<FeedInCompensation | null>(
    async () => {
      if (!filters.electricity || !prodMeter || !expMeter) return null;
      try {
        return await electricityApi.getFeedInCompensation(
          prodMeter.meter_id,
          expMeter.meter_id,
          appliedRange.from,
          appliedRange.to,
        );
      } catch (err: unknown) {
        throw new Error(getErrorMessage(err, 'Fehler beim Laden der EEG-Einspeisevergütung.'));
      }
    },
    [appliedRange.from, appliedRange.to, filters.electricity, data]
  );

  const handleQuickSelect = (id: QuickSelectId): void => {
    const now = new Date();
    let from = DEFAULT_FROM;
    let to = DEFAULT_TO;
    switch (id) {
      case 'last_12_months':
        from = toDateInputValue(addMonths(now, -12));
        to = toDateInputValue(now);
        break;
      case 'current_year':
        from = `${now.getFullYear()}-01-01`;
        to = `${now.getFullYear()}-12-31`;
        break;
      case 'last_year': {
        const year = now.getFullYear() - 1;
        from = `${year}-01-01`;
        to = `${year}-12-31`;
        break;
      }
      case 'all_data':
        from = EARLIEST_DATA_PLACEHOLDER;
        to = toDateInputValue(now);
        break;
    }
    setFromDate(from);
    setToDate(to);
    setAppliedRange({ from, to });
  };

  const handleToggle = (key: FilterKey): void => {
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleApply = (): void => {
    if (!fromDate || !toDate) return;
    setAppliedRange({ from: fromDate, to: toDate });
  };

  const activeAreas = (Object.keys(AREA_METER_TYPES) as FilterKey[]).filter(
    (area) => filters[area]
  );
  const dataItems = data ?? [];
  const applyDisabled = !fromDate || !toDate;

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">Individueller Zeitraum</h2>

      <Card>
        <CardHeader>
          <CardTitle>Zeitraum auswählen</CardTitle>
          <CardDescription>
            Wählen Sie den Zeitraum und die Zählerarten für die Auswertung.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
            <div className="space-y-2">
              <Label htmlFor="custom-from">Von</Label>
              <Input
                id="custom-from"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="custom-to">Bis</Label>
              <Input
                id="custom-to"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">Schnellauswahl</p>
            <div className="flex flex-wrap gap-2">
              {QUICK_SELECTS.map((qs) => (
                <Button
                  key={qs.id}
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => handleQuickSelect(qs.id)}
                >
                  {qs.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">Filter</p>
            <div className="flex flex-wrap gap-4">
              {FILTER_TOGGLES.map((toggle) => (
                // Checkbox is a shared forwardRef primitive; its association is
                // established here via the wrapping label + htmlFor at the call site.
                // eslint-disable-next-line jsx-a11y/label-has-for
                <label
                  key={toggle.key}
                  className="flex items-center gap-2 text-sm"
                  htmlFor={`custom-filter-${toggle.key}`}
                >
                  <Checkbox
                    id={`custom-filter-${toggle.key}`}
                    checked={filters[toggle.key]}
                    onChange={() => handleToggle(toggle.key)}
                  />
                  {toggle.label}
                </label>
              ))}
            </div>
          </div>

          <Button type="button" onClick={handleApply} disabled={applyDisabled}>
            Anwenden
          </Button>
        </CardContent>
      </Card>

      {loading ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Zeitreihen...</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="p-8 text-center text-destructive">
            {error}
          </CardContent>
        </Card>
      ) : activeAreas.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Bitte wählen Sie mindestens einen Bereich aus.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {filters.electricity && prodMeter && expMeter && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Zap className="h-4 w-4" />
                  EEG-Einspeisevergütung (EEG 2009)
                </CardTitle>
                <CardDescription>
                  {formatDate(appliedRange.from)} – {formatDate(appliedRange.to)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {eegLoading && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Lade EEG-Einspeisevergütung...
                  </div>
                )}
                {eegError && (
                  <div className="text-xs text-destructive">{eegError}</div>
                )}
                {eeg && (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="bg-muted rounded p-2">
                        <p className="text-[10px] text-muted-foreground">Erzeugung (P)</p>
                        <p className="text-sm font-semibold">
                          {parseFloat(eeg.production_consumption).toFixed(0)} kWh
                        </p>
                      </div>
                      <div className="bg-muted rounded p-2">
                        <p className="text-[10px] text-muted-foreground">Einspeisung (E)</p>
                        <p className="text-sm font-semibold">
                          {parseFloat(eeg.export_consumption).toFixed(0)} kWh
                        </p>
                      </div>
                      <div className="bg-muted rounded p-2">
                        <p className="text-[10px] text-muted-foreground">Eigenverbrauch</p>
                        <p className="text-sm font-semibold">
                          {parseFloat(eeg.self_consumption).toFixed(0)} kWh
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">
                          Tier 1: {parseFloat(eeg.tier1_kwh).toFixed(1)} &bull; Tier 2:{' '}
                          {parseFloat(eeg.tier2_kwh).toFixed(0)} kWh
                        </p>
                      </div>
                      <div className="bg-muted rounded p-2">
                        <p className="text-[10px] text-muted-foreground">Vergütung</p>
                        <p className="text-sm font-semibold">
                          {formatEuro(eeg.total_compensation)}
                        </p>
                        {eeg.gross_compensation != null && eeg.metering_point_fee_deducted != null && (
                          <div className="text-[10px] text-muted-foreground mt-0.5">
                            <p>Vergütung (brutto): {formatEuro(eeg.gross_compensation)}</p>
                            <p>abzüglich Messstellenbetrieb: −{formatEuro(eeg.metering_point_fee_deducted)}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {activeAreas.map((area) => {
            const Icon = AREA_ICONS[area];
            const areaItems = dataItems.filter((item) =>
              AREA_METER_TYPES[area].includes(item.meter_type)
            );
            return (
              <AreaBlock
                key={area}
                title={AREA_LABELS[area]}
                icon={<Icon className="h-4 w-4" />}
                items={areaItems}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CustomRange;
