import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { costsApi, metersApi, electricityApi } from '../api/client';
import { Meter, Reading, YearsOverviewItem, YearlyProjection, FeedInCompensation, FeedInCompensationProjection, WastewaterCosts, AdvancePaymentDiffByCategory } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Loader2, ArrowLeft, Euro, Zap } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface MeterSection {
  overviewItem: YearsOverviewItem;
  chain: Meter[];
  readings: Reading[];
  projection: YearlyProjection | null;
  projectionLoading: boolean;
  projectionError: string | null;
}

function getMeterChain(allMeters: Meter[], terminalId: number): Meter[] {
  const meterMap = new Map(allMeters.map((m) => [m.id, m]));
  const chain: Meter[] = [];
  let currentId: number | null = terminalId;
  const visited = new Set<number>();
  while (currentId !== null && !visited.has(currentId)) {
    visited.add(currentId);
    const m = meterMap.get(currentId);
    if (!m) break;
    chain.unshift(m);
    currentId = m.replaces_meter_id;
    if (chain.length > 20) break;
  }
  return chain;
}

function formatEuro(value: string | null): string {
  if (value === null) return '—';
  return `${parseFloat(value).toFixed(2)} €`;
}

function basisLabel(basis: YearlyProjection['basis']): string {
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

const ChartTooltip: React.FC<{ active?: boolean; payload?: any[]; label?: any; unit: string }> = ({ active, payload, label, unit }) => {
  if (!active || !payload || payload.length === 0) return null;
  const isFuture = typeof label === 'number' ? label > Date.now() : false;
  const filteredPayload = isFuture
    ? payload
    : payload.filter((p: any) => p.name !== 'Hochrechnung');
  if (filteredPayload.length === 0) return null;
  return (
    <div style={{
      backgroundColor: 'hsl(var(--popover))',
      color: 'hsl(var(--popover-foreground))',
      border: '1px solid hsl(var(--border))',
      borderRadius: 'var(--radius)',
      padding: '8px 12px',
      fontSize: '12px',
    }}>
      <p style={{ marginBottom: 4, fontWeight: 600 }}>
        Datum: {label ? new Date(label).toLocaleDateString() : '—'}
      </p>
      {filteredPayload.map((p: any, idx: number) => (
        <p key={idx} style={{ color: p.color, margin: 0 }}>
          {p.name}: {typeof p.value === 'number' ? `${p.value} ${unit}` : p.value}
        </p>
      ))}
    </div>
  );
};

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316',
];

const YearDetail: React.FC = () => {
  const { year: yearParam } = useParams<{ year: string }>();
  const year = parseInt(yearParam || '', 10);
  const [sections, setSections] = useState<MeterSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eegData, setEegData] = useState<FeedInCompensation | null>(null);
  const [eegLoading, setEegLoading] = useState(false);
  const [eegError, setEegError] = useState<string | null>(null);
  const [eegProjection, setEegProjection] = useState<FeedInCompensationProjection | null>(null);
  const [eegProjectionLoading, setEegProjectionLoading] = useState(false);
  const [eegProjectionError, setEegProjectionError] = useState<string | null>(null);
  const [wastewaterData, setWastewaterData] = useState<WastewaterCosts | null>(null);
  const [wastewaterLoading, setWastewaterLoading] = useState(false);
  const [wastewaterError, setWastewaterError] = useState<string | null>(null);
  const [advancePaymentDiffs, setAdvancePaymentDiffs] = useState<Record<
    'gas' | 'cold_water' | 'wastewater' | 'power_import',
    AdvancePaymentDiffByCategory | null
  >>({
    gas: null,
    cold_water: null,
    wastewater: null,
    power_import: null,
  });

  const fetchData = useCallback(async () => {
    if (isNaN(year)) {
      setError('Ungültiges Jahr.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [overviewData, allMeters] = await Promise.all([
        costsApi.getYearsOverview() as Promise<YearsOverviewItem[]>,
        metersApi.getAll() as Promise<Meter[]>,
      ]);

      const relevantItems = overviewData.filter(
        (item) => item.years.some((y) => y.year === year)
      );

      if (relevantItems.length === 0) {
        setSections([]);
        setLoading(false);
        return;
      }

      const meterSections: MeterSection[] = [];

      for (const item of relevantItems) {
        const chain = getMeterChain(allMeters, item.meter_id);

        const readingsPromises = chain.map((m) =>
          metersApi.getReadings(m.id) as Promise<Reading[]>
        );

        const fetchedReadingsArrays = await Promise.all(readingsPromises);
        const allChainReadings = fetchedReadingsArrays
          .flat()
          .filter((r) => {
            const d = new Date(r.reading_date);
            return d.getFullYear() === year;
          })
          .sort(
            (a, b) =>
              new Date(a.reading_date).getTime() -
              new Date(b.reading_date).getTime()
          );

        meterSections.push({
          overviewItem: item,
          chain,
          readings: allChainReadings,
          projection: null,
          projectionLoading: true,
          projectionError: null,
        });
      }

      setSections(meterSections);
      setLoading(false);

      // Fetch yearly projections in parallel
      const updatedSections = await Promise.all(
        meterSections.map(async (section) => {
          try {
            const projection = await costsApi.getYearlyProjection(
              section.overviewItem.meter_id,
              year
            );
            return { ...section, projection, projectionLoading: false };
          } catch (err: any) {
            const msg =
              err?.response?.data?.detail ||
              err?.message ||
              'Fehler beim Laden der Kostenprojektion.';
            return { ...section, projectionError: msg, projectionLoading: false };
          }
        })
      );

      setSections(updatedSections);

      // Check for electricity meters and fetch EEG feed-in compensation
      const electricTypes = ['electricity_import', 'electricity_export', 'electricity_production'];
      const hasElectric = relevantItems.some((item) =>
        electricTypes.includes(item.meter_type)
      );

      if (hasElectric) {
        const prodItem = relevantItems.find(
          (item) => item.meter_type === 'electricity_production'
        );
        const expItem = relevantItems.find(
          (item) => item.meter_type === 'electricity_export'
        );

        if (prodItem && expItem) {
          setEegLoading(true);
          setEegError(null);
          try {
            const fromDate = `${year}-01-01`;
            const toDate = `${year}-12-31`;
            const eeg = await electricityApi.getFeedInCompensation(
              prodItem.meter_id,
              expItem.meter_id,
              fromDate,
              toDate,
            );
            setEegData(eeg);
          } catch (eegErr: any) {
            const msg =
              eegErr?.response?.data?.detail ||
              eegErr?.message ||
              'Fehler beim Laden der EEG-Einspeisevergütung.';
            setEegError(msg);
          } finally {
            setEegLoading(false);
          }

          // Fetch EEG projection
          setEegProjectionLoading(true);
          setEegProjectionError(null);
          try {
            const proj = await electricityApi.getFeedInCompensationProjection(
              prodItem.meter_id,
              expItem.meter_id,
              year,
            );
            setEegProjection(proj);
          } catch (projErr: any) {
            const msg =
              projErr?.response?.data?.detail ||
              projErr?.message ||
              'Fehler beim Laden der EEG-Prognose.';
            setEegProjectionError(msg);
          } finally {
            setEegProjectionLoading(false);
          }
        } else {
          setEegData(null);
          setEegLoading(false);
          setEegError(null);
          setEegProjection(null);
          setEegProjectionLoading(false);
          setEegProjectionError(null);
        }
      }

      // Find cold/garden water meters and fetch wastewater costs
      const coldItem = relevantItems.find(
        (item) => item.meter_type === 'water_cold'
      );
      const gardenItem = relevantItems.find(
        (item) => item.meter_type === 'water_garden'
      );

      if (coldItem) {
        setWastewaterLoading(true);
        setWastewaterError(null);
        try {
          const fromDate = `${year}-01-01`;
          const toDate = year === new Date().getFullYear()
            ? new Date().toISOString().split('T')[0]
            : `${year}-12-31`;
          const result = await costsApi.getWastewaterCosts(
            coldItem.meter_id,
            fromDate,
            toDate,
            gardenItem?.meter_id,
          );
          setWastewaterData(result);
        } catch (wwErr: any) {
          if (wwErr?.response?.status === 404) {
            setWastewaterData(null);
            setWastewaterError(null);
          } else {
            setWastewaterError(
              wwErr?.response?.data?.detail ||
              wwErr?.message ||
              'Fehler beim Laden der Abwasserkosten.'
            );
          }
        } finally {
          setWastewaterLoading(false);
        }
      } else {
        setWastewaterData(null);
        setWastewaterLoading(false);
        setWastewaterError(null);
      }

      // Fetch advance payment diffs for gas, cold_water, wastewater, power_import
      const advanceFetchers: Array<{
        key: 'gas' | 'cold_water' | 'wastewater' | 'power_import';
        fn: () => Promise<AdvancePaymentDiffByCategory | null>;
      }> = [];

      const gasItem = relevantItems.find(i => i.meter_type === 'gas');
      if (gasItem) {
        advanceFetchers.push({
          key: 'gas',
          fn: () => costsApi.getAdvancePaymentDiffByCategory('gas', year, gasItem.meter_id),
        });
      }

      const powerImportItem = relevantItems.find(i => i.meter_type === 'electricity_import');
      if (powerImportItem) {
        advanceFetchers.push({
          key: 'power_import',
          fn: () => costsApi.getAdvancePaymentDiffByCategory('power_import', year, powerImportItem.meter_id),
        });
      }

      if (coldItem) {
        advanceFetchers.push({
          key: 'cold_water',
          fn: () => costsApi.getAdvancePaymentDiffByCategory('cold_water', year, coldItem.meter_id),
        });
        advanceFetchers.push({
          key: 'wastewater',
          fn: () => costsApi.getAdvancePaymentDiffByCategory('wastewater', year, undefined, coldItem.meter_id, gardenItem?.meter_id),
        });
      }

      const diffs: Record<string, AdvancePaymentDiffByCategory | null> = {
        gas: null,
        cold_water: null,
        wastewater: null,
        power_import: null,
      };

      await Promise.all(
        advanceFetchers.map(async ({ key, fn }) => {
          try {
            diffs[key] = await fn();
          } catch {
            // Leave as null (network error etc.)
          }
        })
      );

      setAdvancePaymentDiffs(diffs as Record<'gas' | 'cold_water' | 'wastewater' | 'power_import', AdvancePaymentDiffByCategory | null>);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        err?.message ||
        'Fehler beim Laden der Jahresdaten.'
      );
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && sections.length === 0) {
    return (
      <div className="p-4">
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Jahresdaten...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="mb-4">
          <Link to="/years-overview">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Zurück zur Jahresübersicht
            </Button>
          </Link>
        </div>
        <Card>
          <CardContent className="p-8 text-center text-destructive">
            {error}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <div className="p-4">
        <div className="mb-4">
          <Link to="/years-overview">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Zurück zur Jahresübersicht
            </Button>
          </Link>
        </div>
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Keine Zählerdaten für das Jahr {year} vorhanden.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-4">
        <Link to="/years-overview">
          <Button variant="outline" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Jahresübersicht
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">Jahresdetail: {year}</h1>
      </div>

      {(() => {
        const electricTypes = ['electricity_import', 'electricity_export', 'electricity_production'];
        const waterTypes = ['water_cold', 'water_garden'];

        const electricSections = sections.filter((s) =>
          electricTypes.includes(s.overviewItem.meter_type)
        );
        const waterSections = sections.filter((s) =>
          waterTypes.includes(s.overviewItem.meter_type)
        );
        const otherSections = sections.filter(
          (s) =>
            !electricTypes.includes(s.overviewItem.meter_type) &&
            !waterTypes.includes(s.overviewItem.meter_type)
        );

        const renderMeterBlock = (section: MeterSection, meterIdx: number) => {
          const item = section.overviewItem;
          const unit = item.unit;
          const chartColor = COLORS[meterIdx % COLORS.length];

          const formatConsumption = (value: string | null): string => {
            if (value === null) return '—';
            const num = parseFloat(value);
            return unit === 'kWh' ? `${Math.round(num)} ${unit}` : `${num.toFixed(1)} ${unit}`;
          };

          const formatReadingValue = (value: string): string =>
            unit === 'kWh' ? Math.round(parseFloat(value)).toString() : value;

          const startOfYear = new Date(year, 0, 1).getTime();
          const startOfNextYear = new Date(year + 1, 0, 1).getTime();

const chartData = section.readings.map((r) => ({
            date: new Date(r.reading_date).toLocaleDateString(),
            timestamp: new Date(r.reading_date).getTime(),
            value: parseFloat(r.value),
            note: r.note,
          }));

          const roundValue = (v: number): number =>
            unit.includes('m³') ? Math.round(v * 100) / 100 : Math.round(v);

          const lastPoint = chartData.length > 0 ? chartData[chartData.length - 1] : null;
          const rawProjectionValue = section.projection?.projected_meter_reading_end_of_year;
          const projectionData = rawProjectionValue
            ? [
                lastPoint
                  ? { timestamp: lastPoint.timestamp, value: lastPoint.value }
                  : { timestamp: startOfYear, value: 0 },
                { timestamp: startOfNextYear, value: roundValue(parseFloat(rawProjectionValue)) },
              ]
            : [];

          const showProjection = projectionData.length > 0
            && section.projection
            && section.projection.basis !== 'actual_full_year'
            && section.projection.basis !== 'insufficient_data';

          const combinedData: Array<{
            timestamp: number;
            date: string;
            value: number | undefined;
            note: string | null;
            projectedValue: number | undefined;
            isProjectionEnd: boolean;
          }> = (() => {
            const data = chartData.map(d => ({ ...d, projectedValue: undefined as number | undefined, isProjectionEnd: false }));
            if (showProjection && projectionData.length >= 2) {
              if (data.length > 0) {
                data[data.length - 1].projectedValue = data[data.length - 1].value;
              } else {
                data.push({
                  timestamp: startOfYear,
                  date: '',
                  value: 0,
                  note: null,
                  projectedValue: 0,
                  isProjectionEnd: false,
                });
              }
              data.push({
                timestamp: startOfNextYear,
                date: '',
                value: undefined as any,
                note: null,
                projectedValue: projectionData[1].value,
                isProjectionEnd: true,
              });
              data.sort((a, b) => a.timestamp - b.timestamp);
            }
            return data;
          })();

          const yValues = [
            ...chartData.map(d => d.value),
            ...(showProjection ? projectionData.map(d => d.value) : []),
          ];
          const yMin = yValues.length > 0 ? Math.min(...yValues) : 0;
          const yMax = yValues.length > 0 ? Math.max(...yValues) : 1;
          const yPadding = (yMax - yMin) * 0.1 || 1;

          const yearEntry = item.years.find((y) => y.year === year);
          const isExportOrProduction =
            item.meter_type === 'electricity_export' || item.meter_type === 'electricity_production';
          const isWater = item.meter_type === 'water_cold' || item.meter_type === 'water_garden';
          const costLabel = isWater ? 'Frischwasserkosten' : 'Kosten';

          return (
            <div key={item.meter_id} className="border rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-sm">{item.meter_label}</h4>
                <span className="text-xs font-medium bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                  {item.meter_type}
                </span>
              </div>
              {section.chain.length > 1 && (
                <p className="text-xs text-muted-foreground">
                  Ersetzungskette: {section.chain.map((m) => m.label).join(' → ')}
                </p>
              )}

              {yearEntry && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="bg-muted rounded p-2">
                    <p className="text-xs text-muted-foreground">
                      {item.meter_type === 'electricity_export' ? 'Einspeisung' :
                       item.meter_type === 'electricity_production' ? 'Erzeugung' : 'Verbrauch'} {year}
                    </p>
                    <p className="text-sm font-semibold">
                      {section.projection?.actual_consumption_to_date != null
                        ? formatConsumption(section.projection.actual_consumption_to_date)
                        : yearEntry.consumption != null
                          ? formatConsumption(yearEntry.consumption)
                          : '—'}
                    </p>
                  </div>
                  {!isExportOrProduction && item.meter_type === 'electricity_import' && (
                    <>
                      {section.projection && section.projection.basis !== 'actual_full_year' && section.projection.projected_annual_consumption != null && (
                        <div className="bg-muted rounded p-2">
                          <p className="text-xs text-muted-foreground">
                            Verbrauch (prog.) {year}
                          </p>
                          <p className="text-sm font-semibold">
                            {formatConsumption(section.projection.projected_annual_consumption)}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            Basis: {basisLabel(section.projection.basis)}
                          </p>
                        </div>
                      )}
                      {section.projection && section.projection.basis === 'actual_full_year' && (
                        <div className="bg-muted rounded p-2 flex items-center justify-center">
                          <p className="text-xs text-muted-foreground">
                            Jahr abgeschlossen
                          </p>
                        </div>
                      )}
                    </>
                  )}
                  {!isExportOrProduction && item.meter_type !== 'electricity_import' && (
                    <div className="bg-muted rounded p-2">
                      <p className="text-xs text-muted-foreground">{costLabel} {year}</p>
                      <p className="text-sm font-semibold">
                        {yearEntry.cost != null ? formatEuro(yearEntry.cost) : '—'}
                      </p>
                      {yearEntry.cost_basis && (
                        <p className="text-[10px] text-muted-foreground mt-0.5">
                          ({yearEntry.cost_basis === 'projected' ? 'hochgerechnet' : 'tatsächlich'})
                        </p>
                      )}
                    </div>
                  )}
                  {!isExportOrProduction && item.meter_type !== 'electricity_import' && section.projection && section.projection.basis !== 'actual_full_year' && section.projection.projected_annual_consumption != null && (
                    <div className="bg-muted rounded p-2">
                      <p className="text-xs text-muted-foreground">
                        {item.meter_type === 'electricity_export' ? 'Einspeisung' :
                         item.meter_type === 'electricity_production' ? 'Erzeugung' : 'Verbrauch'} (prog.) {year}
                      </p>
                      <p className="text-sm font-semibold">
                        {formatConsumption(section.projection.projected_annual_consumption)}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Basis: {basisLabel(section.projection.basis)}
                      </p>
                    </div>
                  )}
                  {!isExportOrProduction && item.meter_type !== 'electricity_import' && section.projection && section.projection.basis === 'actual_full_year' && (
                    <div className="bg-muted rounded p-2 flex items-center justify-center">
                      <p className="text-xs text-muted-foreground">
                        Jahr abgeschlossen
                      </p>
                    </div>
                  )}
                  {isExportOrProduction && (
                    <>
                      {section.projection && section.projection.basis !== 'actual_full_year' && section.projection.projected_annual_consumption != null && (
                        <div className="bg-muted rounded p-2">
                          <p className="text-xs text-muted-foreground">
                            {item.meter_type === 'electricity_export' ? 'Einspeisung' :
                             item.meter_type === 'electricity_production' ? 'Erzeugung' : 'Verbrauch'} (prog.) {year}
                          </p>
                          <p className="text-sm font-semibold">
                            {formatConsumption(section.projection.projected_annual_consumption)}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            Basis: {basisLabel(section.projection.basis)}
                          </p>
                        </div>
                      )}
                      {section.projection && section.projection.basis === 'actual_full_year' && (
                        <div className="bg-muted rounded p-2 flex items-center justify-center">
                          <p className="text-xs text-muted-foreground">
                            Jahr abgeschlossen
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              <div>
                <h5 className="text-xs font-semibold text-muted-foreground mb-1">Verbrauchsverlauf {year}</h5>
                <div className="h-48">
                  {combinedData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={combinedData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          type="number"
                          dataKey="timestamp"
                          domain={[startOfYear, startOfNextYear]}
                          tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                          tickFormatter={(ts: number) => {
                            const d = new Date(ts);
                            return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.`;
                          }}
                          stroke="hsl(var(--muted-foreground))"
                        />
                        <YAxis
                          domain={[yMin - yPadding, yMax + yPadding]}
                          label={{ value: unit, angle: -90, position: 'insideLeft', fill: 'hsl(var(--muted-foreground))' }}
                          tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                          tickFormatter={(v: number) => Math.round(v).toString()}
                          stroke="hsl(var(--muted-foreground))"
                        />
                        <Tooltip content={<ChartTooltip unit={unit} />} />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke={chartColor}
                          strokeWidth={1.5}
                          dot={{ r: 2 }}
                          activeDot={{ r: 4 }}
                          name="Zählerstand"
                        />
                        {showProjection && (
                          <Line
                            type="monotone"
                            dataKey="projectedValue"
                            stroke={chartColor}
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={(props: any) =>
                              props.payload.isProjectionEnd
                                ? <circle cx={props.cx} cy={props.cy} r={3} fill={chartColor} />
                                : <></>
                            }
                            activeDot={false}
                            name="Hochrechnung"
                          />
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                      Keine Zählerstände für {year} vorhanden.
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h5 className="text-xs font-semibold text-muted-foreground mb-1">Zählerstände {year}</h5>
                <div className="max-h-36 overflow-y-auto">
                  {section.readings.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">Datum</TableHead>
                          <TableHead className="text-xs">Wert ({unit})</TableHead>
                          <TableHead className="text-xs">Notiz</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {section.readings.map((r) => (
                          <TableRow key={r.id}>
                            <TableCell className="text-xs py-1">{new Date(r.reading_date).toLocaleDateString()}</TableCell>
                            <TableCell className="text-xs py-1">{formatReadingValue(r.value)}</TableCell>
                            <TableCell className="text-xs py-1">{r.note || '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-4 text-xs text-muted-foreground">
                      Keine Zählerstände für {year} vorhanden.
                    </div>
                  )}
                </div>
              </div>

              {!isExportOrProduction && item.meter_type === 'electricity_import' && (
                <>
                  <div>
                    <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                      Kostenprojektion {year}
                    </h5>
                    {section.projectionLoading ? (
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Lade Projektion...
                      </div>
                    ) : section.projectionError ? (
                      <div className="text-xs text-destructive">{section.projectionError}</div>
                    ) : section.projection ? (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">Verbrauch tatsächlich</p>
                          <p className="text-xs font-semibold">
                            {section.projection.actual_consumption_to_date != null
                              ? formatConsumption(section.projection.actual_consumption_to_date)
                              : '—'}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">Kosten tatsächlich</p>
                          <p className="text-xs font-semibold">
                            {formatEuro(section.projection.actual_cost_to_date)}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">Verbrauch prognostiziert</p>
                          <p className="text-xs font-semibold">
                            {section.projection.projected_annual_consumption != null
                              ? formatConsumption(section.projection.projected_annual_consumption)
                              : '—'}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">Kosten prognostiziert</p>
                          <p className="text-xs font-semibold">
                            {formatEuro(section.projection.projected_annual_cost)}
                          </p>
                        </div>
                        {(() => {
                          const cat = 'power_import';
                          const data = advancePaymentDiffs[cat];
                          return data ? (
                            <>
                              <div className="bg-muted rounded p-1.5">
                                <p className="text-[10px] text-muted-foreground">Abschlagszahlungen hochgerechnet</p>
                                <p className="text-xs font-semibold">
                                  {data.total_advance_payments != null ? formatEuro(data.total_advance_payments) : '—'}
                                </p>
                              </div>
                              <div className="bg-muted rounded p-1.5">
                                <p className="text-[10px] text-muted-foreground">Differenz Abschläge zu Kosten</p>
                                <p className="text-xs font-semibold" style={{
                                  color: data.difference != null
                                    ? (parseFloat(data.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                                    : undefined,
                                }}>
                                  {data.difference != null ? formatEuro(data.difference) : '—'}
                                </p>
                              </div>
                            </>
                          ) : (
                            <div className="col-span-2 bg-muted rounded p-1.5">
                              <p className="text-xs text-muted-foreground">Kein Abschlag hinterlegt.</p>
                            </div>
                          );
                        })()}
                      </div>
                    ) : null}

                    {section.projection && section.projection.message && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">{section.projection.message}</p>
                    )}
                    {section.projection && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Basis: {basisLabel(section.projection.basis)}
                        &nbsp;|&nbsp;Stand: {new Date(section.projection.as_of_date).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </>
              )}

              {!isExportOrProduction && item.meter_type !== 'electricity_import' && (
                <>
                  <div>
                    <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                      {isWater ? 'Frischwasserkosten-Prognose' : 'Kostenprojektion'} {year}
                    </h5>
                    {section.projectionLoading ? (
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Lade Projektion...
                      </div>
                    ) : section.projectionError ? (
                      <div className="text-xs text-destructive">{section.projectionError}</div>
                    ) : section.projection ? (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1">
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">{isWater ? 'Frischwasser-' : ''}Verbrauch (tats.)</p>
                          <p className="text-xs font-semibold">
                            {section.projection.actual_consumption_to_date != null
                              ? formatConsumption(section.projection.actual_consumption_to_date)
                              : '—'}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">{isWater ? 'Frischwasser-' : ''}Verbrauch (prog.)</p>
                          <p className="text-xs font-semibold">
                            {section.projection.projected_annual_consumption != null
                              ? formatConsumption(section.projection.projected_annual_consumption)
                              : '—'}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">{isWater ? 'Frischwasser-' : ''}kosten (tats.)</p>
                          <p className="text-xs font-semibold">
                            {formatEuro(section.projection.actual_cost_to_date)}
                          </p>
                        </div>
                        <div className="bg-muted rounded p-1.5">
                          <p className="text-[10px] text-muted-foreground">{isWater ? 'Frischwasser-' : ''}kosten (prog.)</p>
                          <p className="text-xs font-semibold">
                            {formatEuro(section.projection.projected_annual_cost)}
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {section.projection && section.projection.message && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">{section.projection.message}</p>
                    )}
                    {section.projection && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Basis: {basisLabel(section.projection.basis)}
                        &nbsp;|&nbsp;Stand: {new Date(section.projection.as_of_date).toLocaleDateString()}
                      </p>
                    )}
                  </div>

                  {(() => {
                    const advanceCategories: Array<{
                      cat: 'gas' | 'cold_water' | 'wastewater' | 'power_import';
                      label: string;
                    }> = [];
                    if (item.meter_type === 'gas') {
                      advanceCategories.push({ cat: 'gas', label: 'Gas' });
                    }

                    if (advanceCategories.length === 0) return null;

                    return advanceCategories.map(({ cat, label }) => {
                      const data = advancePaymentDiffs[cat];
                      return (
                        <div key={cat} className="border rounded-lg p-3 bg-muted/20 mt-2">
                          <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                            Abschlagsdifferenz {label} {year}
                          </h5>
                          {data ? (
                            <div className="grid grid-cols-2 gap-2">
                              <div className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground">Abschlagszahlungen (hochger.)</p>
                                <p className="text-xs font-semibold">
                                  {data.total_advance_payments != null ? formatEuro(data.total_advance_payments) : '—'}
                                </p>
                              </div>
                              <div className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground">Differenz zu Abschlägen</p>
                                <p className="text-xs font-semibold" style={{
                                  color: data.difference != null
                                    ? (parseFloat(data.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                                    : undefined,
                                }}>
                                  {data.difference != null ? formatEuro(data.difference) : '—'}
                                </p>
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground">Kein Abschlag hinterlegt.</p>
                          )}
                        </div>
                      );
                    });
                  })()}
                </>
              )}
            </div>
          );
        };

        return (
          <>
            {/* ---- STROM category ---- */}
            {electricSections.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Zap className="h-4 w-4" />
                    Strom {year}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {eegLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Lade EEG-Einspeisevergütung...
                    </div>
                  )}
                  {eegError && (
                    <div className="text-xs text-destructive">{eegError}</div>
                  )}
                  {eegData && (
                    <div className="border rounded-lg p-3 bg-muted/20">
                      <h4 className="text-xs font-semibold text-muted-foreground mb-2">EEG-Einspeisevergütung</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Erzeugung (P)</p>
                          <p className="text-sm font-semibold">{parseFloat(eegData.production_consumption).toFixed(0)} kWh</p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Einspeisung (E)</p>
                          <p className="text-sm font-semibold">{parseFloat(eegData.export_consumption).toFixed(0)} kWh</p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Eigenverbrauch</p>
                          <p className="text-sm font-semibold">{parseFloat(eegData.self_consumption).toFixed(0)} kWh</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            Tier 1: {parseFloat(eegData.tier1_kwh).toFixed(1)} &bull; Tier 2: {parseFloat(eegData.tier2_kwh).toFixed(0)} kWh
                          </p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Vergütung</p>
                          <p className="text-sm font-semibold">{formatEuro(eegData.total_compensation)}</p>
                        </div>
                      </div>
                    </div>
                  )}
                  {eegProjectionError && (
                    <div className="text-xs text-destructive">{eegProjectionError}</div>
                  )}
                  {eegProjection && eegProjection.basis === 'actual_full_year' && (
                    <div className="border rounded-lg p-3 bg-muted/20">
                      <h4 className="text-xs font-semibold text-muted-foreground mb-2">EEG-Einspeisevergütung (Prognose)</h4>
                      <p className="text-xs text-muted-foreground">
                        Das Jahr {year} ist bereits abgeschlossen. Die tatsächlichen Werte werden oben angezeigt.
                      </p>
                    </div>
                  )}
                  {eegProjectionLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Lade EEG-Prognose...
                    </div>
                  )}
                  {eegProjection && eegProjection.basis !== 'actual_full_year' && eegProjection.production_consumption != null && (
                    <div className="border rounded-lg p-3 bg-muted/20">
                      <h4 className="text-xs font-semibold text-muted-foreground mb-2">EEG-Einspeisevergütung (Prognose)</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Erzeugung (P)</p>
                          <p className="text-sm font-semibold">{parseFloat(eegProjection.production_consumption).toFixed(0)} kWh</p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Einspeisung (E)</p>
                          <p className="text-sm font-semibold">{parseFloat(eegProjection.export_consumption!).toFixed(0)} kWh</p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Eigenverbrauch</p>
                          <p className="text-sm font-semibold">{parseFloat(eegProjection.self_consumption!).toFixed(0)} kWh</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            Tier 1: {parseFloat(eegProjection.tier1_kwh!).toFixed(1)} &bull; Tier 2: {parseFloat(eegProjection.tier2_kwh!).toFixed(0)} kWh
                          </p>
                        </div>
                        <div className="bg-muted rounded p-2">
                          <p className="text-[10px] text-muted-foreground">Vergütung</p>
                          <p className="text-sm font-semibold">{formatEuro(eegProjection.total_compensation!)}</p>
                        </div>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-2">
                        Basis: {basisLabel(eegProjection.basis as YearlyProjection['basis'])}
                      </p>
                    </div>
                  )}
                  {electricSections.map((s, i) => renderMeterBlock(s, i))}
                </CardContent>
              </Card>
            )}

            {/* ---- WASSER category ---- */}
            {waterSections.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Euro className="h-4 w-4" />
                    Wasser {year}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {wastewaterLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Lade Abwasserkosten...
                    </div>
                  )}
                  {wastewaterError && (
                    <div className="text-xs text-destructive">{wastewaterError}</div>
                  )}
                  {wastewaterData && (
                    <>
                      <div className="border rounded-lg p-3 bg-muted/20">
                        <h4 className="text-xs font-semibold text-muted-foreground mb-2">Abwasserkosten</h4>
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                          <div className="bg-muted rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Frischwasserverbrauch</p>
                            <p className="text-sm font-semibold">{parseFloat(wastewaterData.cold_consumption).toFixed(1)} m³</p>
                          </div>
                          <div className="bg-muted rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Gartenwasserverbrauch</p>
                            <p className="text-sm font-semibold">{parseFloat(wastewaterData.garden_consumption).toFixed(1)} m³</p>
                          </div>
                          <div className="bg-muted rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Abwasserverbrauch</p>
                            <p className="text-sm font-semibold">{parseFloat(wastewaterData.wastewater_consumption).toFixed(1)} m³</p>
                          </div>
                          <div className="bg-muted rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Preis pro m³</p>
                            <p className="text-sm font-semibold">{formatEuro(wastewaterData.price_per_unit)} /m³</p>
                          </div>
                          <div className="bg-muted rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Abwasserkosten gesamt</p>
                            <p className="text-sm font-semibold">{formatEuro(wastewaterData.total_cost)}</p>
                          </div>
                        </div>
                      </div>
                      <div className="border rounded-lg p-3 bg-muted/20">
                        <h4 className="text-xs font-semibold text-muted-foreground mb-2">Gesamtwasserkosten</h4>
                        {(() => {
                          const coldSection = sections.find((s) => s.overviewItem.meter_type === 'water_cold');
                          const gardenSection = sections.find((s) => s.overviewItem.meter_type === 'water_garden');
                          const coldCost = coldSection?.projection?.actual_cost_to_date ?? null;
                          const gardenCost = gardenSection?.projection?.actual_cost_to_date ?? null;
                          const total = (
                            (coldCost ? parseFloat(coldCost) : 0) +
                            (gardenCost ? parseFloat(gardenCost) : 0) +
                            parseFloat(wastewaterData.total_cost)
                          ).toFixed(2);

                          return (
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                              <div className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground">Frischwasser</p>
                                <p className="text-sm font-semibold">{formatEuro(coldCost)}</p>
                              </div>
                              {gardenCost && (
                                <div className="bg-muted rounded p-2">
                                  <p className="text-[10px] text-muted-foreground">Frischwasser Gartenwasser</p>
                                  <p className="text-sm font-semibold">{formatEuro(gardenCost)}</p>
                                </div>
                              )}
                              <div className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground">Abwasserkosten</p>
                                <p className="text-sm font-semibold">{formatEuro(wastewaterData.total_cost)}</p>
                              </div>
                              <div className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground font-semibold">Gesamt</p>
                                <p className="text-sm font-bold">{total} €</p>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </>
                  )}

                  {(() => {
                    const hasColdWater = waterSections.some(s => s.overviewItem.meter_type === 'water_cold');
                    const waterAdvanceCategories: Array<{
                      cat: 'cold_water' | 'wastewater';
                      label: string;
                    }> = [];
                    if (hasColdWater) {
                      waterAdvanceCategories.push({ cat: 'cold_water', label: 'Frischwasser' });
                      waterAdvanceCategories.push({ cat: 'wastewater', label: 'Abwasser' });
                    }
                    if (waterAdvanceCategories.length === 0) return null;
                    return (
                      <div className="border rounded-lg p-3 bg-muted/20">
                        <h4 className="text-xs font-semibold text-muted-foreground mb-2">Abschlagsdifferenzen</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {waterAdvanceCategories.map(({ cat, label }) => {
                            const data = advancePaymentDiffs[cat];
                            return (
                              <div key={cat} className="bg-muted rounded p-2">
                                <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
                                {data ? (
                                  <div className="grid grid-cols-2 gap-2">
                                    <div>
                                      <p className="text-[10px] text-muted-foreground">Abschlagszahlungen (hochger.)</p>
                                      <p className="text-xs font-semibold">
                                        {data.total_advance_payments != null ? formatEuro(data.total_advance_payments) : '—'}
                                      </p>
                                    </div>
                                    <div>
                                      <p className="text-[10px] text-muted-foreground">Differenz zu Abschlägen</p>
                                      <p className="text-xs font-semibold" style={{
                                        color: data.difference != null
                                          ? (parseFloat(data.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                                          : undefined,
                                      }}>
                                        {data.difference != null ? formatEuro(data.difference) : '—'}
                                      </p>
                                    </div>
                                  </div>
                                ) : (
                                  <p className="text-xs text-muted-foreground">Kein Abschlag hinterlegt.</p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}

                  {waterSections.map((s, i) => renderMeterBlock(s, i))}
                </CardContent>
              </Card>
            )}

            {/* ---- OTHER meters (gas, etc.) ---- */}
            {otherSections.map((section, idx) => renderMeterBlock(section, idx))}
          </>
        );
      })()}
    </div>
  );
};

export default YearDetail;