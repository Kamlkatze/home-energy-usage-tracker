import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { costsApi, metersApi, electricityApi } from '../api/client';
import { Meter, Reading, YearsOverviewItem, YearlyProjection, FeedInCompensation, WastewaterCosts } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Loader2, ArrowLeft, Euro } from 'lucide-react';
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
  const [hasElectricityMeters, setHasElectricityMeters] = useState(false);

  const [wastewaterData, setWastewaterData] = useState<WastewaterCosts | null>(null);
  const [wastewaterLoading, setWastewaterLoading] = useState(false);
  const [wastewaterError, setWastewaterError] = useState<string | null>(null);
  const [hasColdWaterMeter, setHasColdWaterMeter] = useState(false);

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
      setHasElectricityMeters(hasElectric);

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
        } else {
          // Electricity meter present but no production/export pair — not a solar setup
          setEegData(null);
          setEegLoading(false);
          setEegError(null);
        }
      }

      // Find cold/garden water meters and fetch wastewater costs
      const coldItem = relevantItems.find(
        (item) => item.meter_type === 'water_cold'
      );
      const gardenItem = relevantItems.find(
        (item) => item.meter_type === 'water_garden'
      );
      setHasColdWaterMeter(!!coldItem);

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
          // 404 = kein wastewater-Tarif → Kachel ausblenden (kein Fehler)
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
      <div className="p-6">
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
      <div className="p-6">
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
      <div className="p-6">
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
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/years-overview">
          <Button variant="outline" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Jahresübersicht
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">Jahresdetail: {year}</h1>
      </div>

      {/* EEG Einspeisevergütung */}
      {hasElectricityMeters && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Euro className="h-4 w-4" />
              EEG-Einspeisevergütung {year}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {eegLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Lade EEG-Einspeisevergütung...
              </div>
            ) : eegError ? (
              <Card>
                <CardContent className="py-4 text-destructive text-sm">
                  {eegError}
                </CardContent>
              </Card>
            ) : eegData ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Erzeugung (P)</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(eegData.production_consumption).toFixed(1)} kWh
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Einspeisung (E)</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(eegData.export_consumption).toFixed(1)} kWh
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Eigenverbrauch</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(eegData.self_consumption).toFixed(1)} kWh
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Tier 1: {parseFloat(eegData.tier1_kwh).toFixed(1)} kWh
                    &bull; Tier 2: {parseFloat(eegData.tier2_kwh).toFixed(1)} kWh
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Vergütung</p>
                  <p className="text-xl font-semibold">
                    {formatEuro(eegData.total_compensation)}
                  </p>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Abwasserkosten */}
      {hasColdWaterMeter && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Euro className="h-4 w-4" />
              Abwasserkosten {year}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {wastewaterLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Lade Abwasserkosten...
              </div>
            ) : wastewaterError ? (
              <div className="text-destructive text-sm">{wastewaterError}</div>
            ) : wastewaterData ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Kaltwasserverbrauch</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(wastewaterData.cold_consumption).toFixed(1)} m³
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Gartenwasserverbrauch</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(wastewaterData.garden_consumption).toFixed(1)} m³
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Abwasserverbrauch</p>
                  <p className="text-xl font-semibold">
                    {parseFloat(wastewaterData.wastewater_consumption).toFixed(1)} m³
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Preis pro m³</p>
                  <p className="text-xl font-semibold">
                    {formatEuro(wastewaterData.price_per_unit)} /m³
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Abwasserkosten gesamt</p>
                  <p className="text-xl font-semibold">
                    {formatEuro(wastewaterData.total_cost)}
                  </p>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Gesamtwasserkosten = Frischwasser (Kalt + Garten) + Abwasser */}
      {hasColdWaterMeter && wastewaterData && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Euro className="h-4 w-4" />
              Gesamtwasserkosten {year}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(() => {
              const coldSection = sections.find(
                (s) => s.overviewItem.meter_type === 'water_cold'
              );
              const gardenSection = sections.find(
                (s) => s.overviewItem.meter_type === 'water_garden'
              );
              const coldCost = coldSection?.projection?.actual_cost_to_date ?? null;
              const gardenCost = gardenSection?.projection?.actual_cost_to_date ?? null;
              const total = (
                (coldCost ? parseFloat(coldCost) : 0) +
                (gardenCost ? parseFloat(gardenCost) : 0) +
                parseFloat(wastewaterData.total_cost)
              ).toFixed(2);

              return (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Frischwasserkosten Kaltwasser</p>
                    <p className="text-xl font-semibold">{formatEuro(coldCost)}</p>
                  </div>
                  {gardenCost && (
                    <div className="bg-muted rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">Frischwasserkosten Gartenwasser</p>
                      <p className="text-xl font-semibold">{formatEuro(gardenCost)}</p>
                    </div>
                  )}
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Abwasserkosten</p>
                    <p className="text-xl font-semibold">{formatEuro(wastewaterData.total_cost)}</p>
                  </div>
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground font-bold">Gesamt</p>
                    <p className="text-xl font-semibold">{total} €</p>
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {sections.map((section, idx) => {
        const item = section.overviewItem;
        const unit = item.unit;
        const chartColor = COLORS[idx % COLORS.length];

        const chartData = section.readings.map((r) => ({
          date: new Date(r.reading_date).toLocaleDateString(),
          value: parseFloat(r.value),
          note: r.note,
        }));

        const yearEntry = item.years.find((y) => y.year === year);
        const hideCostProjection =
          item.meter_type === 'electricity_export' || item.meter_type === 'electricity_production';

        return (
          <Card key={item.meter_id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{item.meter_label}</CardTitle>
                <span className="text-sm font-medium bg-primary/10 text-primary px-3 py-1 rounded-full">
                  {item.meter_type} &bull; {unit}
                </span>
              </div>
              {section.chain.length > 1 && (
                <p className="text-sm text-muted-foreground mt-1">
                  Ersetzungskette: {section.chain.map((m) => m.label).join(' → ')}
                </p>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Consumption overview */}
              {yearEntry && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Verbrauch {year}</p>
                    <p className="text-xl font-semibold">
                      {yearEntry.consumption != null
                        ? `${parseFloat(yearEntry.consumption).toFixed(1)} ${unit}`
                        : '—'}
                    </p>
                  </div>
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Kosten {year}</p>
                    <p className="text-xl font-semibold">
                      {yearEntry.cost != null ? formatEuro(yearEntry.cost) : '—'}
                    </p>
                    {yearEntry.cost_basis && (
                      <p className="text-xs text-muted-foreground mt-1">
                        ({yearEntry.cost_basis === 'projected' ? 'hochgerechnet' : 'tatsächlich'})
                      </p>
                    )}
                  </div>
                  <div className="bg-muted rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Zählerstände</p>
                    <p className="text-xl font-semibold">{section.readings.length}</p>
                  </div>
                </div>
              )}

              {/* Chart */}
              <div>
                <h3 className="text-lg font-semibold mb-2">Verbrauchsverlauf {year}</h3>
                <div className="h-72">
                  {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis label={{ value: unit, angle: -90, position: 'insideLeft' }} />
                        <Tooltip
                          formatter={(value) => [`${value} ${unit}`, 'Zählerstand']}
                          labelFormatter={(label) => `Datum: ${label}`}
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke={chartColor}
                          strokeWidth={2}
                          dot={{ r: 4 }}
                          activeDot={{ r: 6 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-muted-foreground">
                      Keine Zählerstände für {year} vorhanden.
                    </div>
                  )}
                </div>
              </div>

              {/* Readings table */}
              <div>
                <h3 className="text-lg font-semibold mb-2">Zählerstände {year}</h3>
                {section.readings.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Datum</TableHead>
                        <TableHead>Wert ({unit})</TableHead>
                        <TableHead>Notiz</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {section.readings.map((r) => (
                        <TableRow key={r.id}>
                          <TableCell>
                            {new Date(r.reading_date).toLocaleDateString()}
                          </TableCell>
                          <TableCell>{r.value}</TableCell>
                          <TableCell>{r.note || '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    Keine Zählerstände für {year} vorhanden.
                  </div>
                )}
              </div>

              {/* Cost projection — hidden for export and production meters (no consumption costs) */}
              {!hideCostProjection && (
              <div>
                <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                  <Euro className="h-4 w-4" />
                  Kostenprojektion {year}
                </h3>
                {section.projectionLoading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Lade Projektion...
                  </div>
                ) : section.projectionError ? (
                  <Card>
                    <CardContent className="py-4 text-destructive">
                      {section.projectionError}
                    </CardContent>
                  </Card>
                ) : section.projection ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-muted rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        Tatsächlicher Verbrauch
                      </p>
                      <p className="text-xl font-semibold">
                        {section.projection.actual_consumption_to_date != null
                          ? `${parseFloat(section.projection.actual_consumption_to_date).toFixed(1)} ${unit}`
                          : '—'}
                      </p>
                    </div>
                    <div className="bg-muted rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        Hochgerechneter Verbrauch
                      </p>
                      <p className="text-xl font-semibold">
                        {section.projection.projected_annual_consumption != null
                          ? `${parseFloat(section.projection.projected_annual_consumption).toFixed(1)} ${unit}`
                          : '—'}
                      </p>
                    </div>
                    <div className="bg-muted rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        Tatsächliche Kosten
                      </p>
                      <p className="text-xl font-semibold">
                        {formatEuro(section.projection.actual_cost_to_date)}
                      </p>
                    </div>
                    <div className="bg-muted rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        Hochgerechnete Kosten
                      </p>
                      <p className="text-xl font-semibold">
                        {formatEuro(section.projection.projected_annual_cost)}
                      </p>
                    </div>
                  </div>
                ) : null}

                {section.projection && section.projection.message && (
                  <p className="text-sm text-muted-foreground mt-2">
                    {section.projection.message}
                  </p>
                )}

                {section.projection && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Basis: {basisLabel(section.projection.basis)}
                    &nbsp;|&nbsp;Stand: {new Date(section.projection.as_of_date).toLocaleDateString()}
                  </p>
                )}
              </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

export default YearDetail;