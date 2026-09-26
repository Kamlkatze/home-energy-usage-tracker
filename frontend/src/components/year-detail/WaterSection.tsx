import React, { useState } from 'react';
import { MeterSection, AdvancePaymentDiffs } from './types';
import { basisLabel } from './utils';
import {
  formatConsumption as formatConsumptionShared,
  formatEuro,
  niceAxisBounds,
} from '../shared/chartHelpers';
import ChartTooltip from '../shared/ChartTooltip';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Loader2, Euro, Pencil, Trash2 } from 'lucide-react';
import { WastewaterCosts, Reading } from '../../types';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import ReadingEditDialog from './ReadingEditDialog';

const WATER_COLORS = {
  fw: '#3b82f6',
  gw: '#10b981',
};

interface CombinedChartPoint {
  timestamp: number;
  fwValue: number | undefined;
  gwValue: number | undefined;
  fwProjected: number | undefined;
  gwProjected: number | undefined;
  isFwEnd: boolean;
  isGwEnd: boolean;
}

function makeCombinedChartData(
  coldSection: MeterSection | undefined,
  gardenSection: MeterSection | undefined,
  year: number,
  showConsumption: boolean
): CombinedChartPoint[] {
  const startOfYear = new Date(year, 0, 1).getTime();
  const startOfNextYear = new Date(year + 1, 0, 1).getTime();
  const map = new Map<number, CombinedChartPoint>();

  const coldStartValue = showConsumption && coldSection?.projection?.start_reading_value
    ? parseFloat(coldSection.projection.start_reading_value)
    : null;
  const gardenStartValue = showConsumption && gardenSection?.projection?.start_reading_value
    ? parseFloat(gardenSection.projection.start_reading_value)
    : null;

  function upsert(timestamp: number, updates: Partial<CombinedChartPoint>) {
    const existing = map.get(timestamp);
    if (existing) {
      Object.assign(existing, updates);
    } else {
      map.set(timestamp, {
        timestamp,
        fwValue: undefined,
        gwValue: undefined,
        fwProjected: undefined,
        gwProjected: undefined,
        isFwEnd: false,
        isGwEnd: false,
        ...updates,
      });
    }
  }

  for (const r of (coldSection?.readings || [])) {
    const raw = parseFloat(r.value);
    upsert(new Date(r.reading_date).getTime(), { fwValue: coldStartValue != null ? raw - coldStartValue : raw });
  }

  for (const r of (gardenSection?.readings || [])) {
    const raw = parseFloat(r.value);
    upsert(new Date(r.reading_date).getTime(), { gwValue: gardenStartValue != null ? raw - gardenStartValue : raw });
  }

  let results = Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);

  const coldProj = coldSection?.projection;
  const coldProjEndRaw = showConsumption
    ? coldProj?.projected_annual_consumption
    : coldProj?.projected_meter_reading_end_of_year;
  const coldShowProj = coldProj && coldProjEndRaw && coldProj.basis !== 'actual_full_year' && coldProj.basis !== 'insufficient_data';

  if (coldShowProj) {
    const projEndValue = Math.round(parseFloat(coldProjEndRaw) * 100) / 100;
    const lastCold = [...results].reverse().find(p => p.fwValue !== undefined);
    if (lastCold) {
      lastCold.fwProjected = lastCold.fwValue;
    } else {
      upsert(startOfYear, { fwProjected: 0 });
    }
    upsert(startOfNextYear, { fwProjected: projEndValue, isFwEnd: true });
  }

  const gardenProj = gardenSection?.projection;
  const gardenProjEndRaw = showConsumption
    ? gardenProj?.projected_annual_consumption
    : gardenProj?.projected_meter_reading_end_of_year;
 const gardenShowProj = gardenProj && gardenProjEndRaw && gardenProj.basis !== 'actual_full_year' && gardenProj.basis !== 'insufficient_data';

  if (gardenShowProj) {
    const projEndValue = Math.round(parseFloat(gardenProjEndRaw) * 100) / 100;
    const lastGarden = [...results].reverse().find(p => p.gwValue !== undefined);
    if (lastGarden) {
      lastGarden.gwProjected = lastGarden.gwValue;
    } else {
      upsert(startOfYear, { gwProjected: 0 });
    }
    upsert(startOfNextYear, { gwProjected: projEndValue, isGwEnd: true });
  }

  results = Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);

  const deduped: CombinedChartPoint[] = [];
  const seen = new Set<number>();
  for (let i = results.length - 1; i >= 0; i--) {
    if (!seen.has(results[i].timestamp)) {
      seen.add(results[i].timestamp);
      deduped.unshift(results[i]);
    }
  }

  return deduped;
}

interface WaterSectionProps {
  sections: MeterSection[];
  year: number;
  advancePaymentDiffs: AdvancePaymentDiffs;
  wastewaterData: WastewaterCosts | null;
  wastewaterLoading: boolean;
  wastewaterError: string | null;
  onRefreshSection?: (meterId: number) => void;
}

const WaterSection: React.FC<WaterSectionProps> = ({
  sections, year, advancePaymentDiffs,
  wastewaterData, wastewaterLoading, wastewaterError,
  onRefreshSection,
}) => {
  const [showConsumption, setShowConsumption] = useState(true);
  const [editingReading, setEditingReading] = useState<{ reading: Reading; meterId: number } | null>(null);
  const coldSection = sections.find(s => s.overviewItem.meter_type === 'water_cold');
  const gardenSection = sections.find(s => s.overviewItem.meter_type === 'water_garden');

  if (!coldSection) return null;

  const coldYearEntry = coldSection.overviewItem.years.find(y => y.year === year);
  const gardenYearEntry = gardenSection?.overviewItem.years.find(y => y.year === year);

const coldConsActual = coldSection.projection?.actual_consumption_to_date ?? coldYearEntry?.consumption ?? null;
  const coldConsProj = coldSection.projection?.projected_annual_consumption ?? null;
  const coldCostActual = coldSection.projection?.actual_cost_to_date ?? null;
  const coldCostProj = coldSection.projection?.projected_annual_cost ?? null;

  const gardenConsActual = gardenSection?.projection?.actual_consumption_to_date ?? gardenYearEntry?.consumption ?? null;
  const gardenConsProj = gardenSection?.projection?.projected_annual_consumption ?? null;

  const awConsActual = wastewaterData?.wastewater_consumption ?? null;
  const awCostActual = wastewaterData?.total_cost ?? null;
  const pricePerUnit = wastewaterData?.price_per_unit ?? null;

  let awConsProj: string | null = null;
  if (coldConsProj && gardenConsProj) {
    const diff = parseFloat(coldConsProj) - parseFloat(gardenConsProj);
    awConsProj = diff > 0 ? diff.toFixed(3) : '0.000';
  } else if (coldConsProj) {
    awConsProj = coldConsProj;
  }

  let awCostProj: string | null = null;
  if (awConsProj && pricePerUnit) {
    const est = parseFloat(awConsProj) * parseFloat(pricePerUnit);
    awCostProj = est.toFixed(2);
  }

  const combinedData = makeCombinedChartData(coldSection, gardenSection, year, showConsumption);

  const allValues = combinedData.flatMap(d => [d.fwValue, d.gwValue]).filter((v): v is number => v !== undefined);
  const bounds = niceAxisBounds(
    allValues.length > 0 ? Math.min(...allValues) : 0,
    allValues.length > 0 ? Math.max(...allValues) : 1,
    showConsumption
  );

  const startOfYear = new Date(year, 0, 1).getTime();
  const startOfNextYear = new Date(year + 1, 0, 1).getTime();

  const formatConsumption = (value: string | null): string =>
    formatConsumptionShared(value, 'm\u00B3');

  const coldDiff = advancePaymentDiffs['cold_water'];
  const awDiff = advancePaymentDiffs['wastewater'];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Euro className="h-4 w-4" />
          Wasser {year}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">

        <div className="border rounded-lg p-3 bg-muted/20">
          <h4 className="text-xs font-semibold text-muted-foreground mb-2">Verbräuche {year}</h4>
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Frischwasser (tats.)</p>
              <p className="text-sm font-semibold">{formatConsumption(coldConsActual)}</p>
            </div>
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Frischwasser (prog.)</p>
              <p className="text-sm font-semibold">{formatConsumption(coldConsProj)}</p>
              {coldSection.projection && coldSection.projection.basis !== 'actual_full_year' && (
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Basis: {basisLabel(coldSection.projection.basis)}
                </p>
              )}
            </div>
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Gartenwasser (tats.)</p>
              <p className="text-sm font-semibold">{formatConsumption(gardenConsActual)}</p>
            </div>
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Gartenwasser (prog.)</p>
              <p className="text-sm font-semibold">{formatConsumption(gardenConsProj)}</p>
              {gardenSection?.projection && gardenSection.projection.basis !== 'actual_full_year' && (
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Basis: {basisLabel(gardenSection.projection.basis)}
                </p>
              )}
            </div>
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Abwasserverbrauch (tats.)</p>
              <p className="text-sm font-semibold">{formatConsumption(awConsActual)}</p>
            </div>
            <div className="bg-muted rounded p-2">
              <p className="text-[10px] text-muted-foreground">Abwasserverbrauch (prog.)</p>
              <p className="text-sm font-semibold">{formatConsumption(awConsProj)}</p>
            </div>
          </div>
        </div>

        <div className="border rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-xs font-semibold text-muted-foreground">
              {showConsumption ? 'Frischwasser & Gartenwasser seit 01.01.' : 'Frischwasser & Gartenwasser'} {year}
            </h4>
            <button
              onClick={() => setShowConsumption(!showConsumption)}
              className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                showConsumption
                  ? 'bg-primary/10 text-primary border-primary/30'
                  : 'bg-muted text-muted-foreground border-transparent'
              }`}
            >
              seit 01.01.
            </button>
          </div>
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
                    domain={[bounds.min, bounds.max]}
                    label={{ value: showConsumption ? 'm\u00B3 (kumuliert)' : 'm\u00B3', angle: -90, position: 'insideLeft', fill: 'hsl(var(--muted-foreground))' }}
                    tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    tickFormatter={(v: number) => Math.round(v).toString()}
                    stroke="hsl(var(--muted-foreground))"
                  />
                  <Tooltip content={<ChartTooltip unit="m\u00B3" />} />
                  <Line
                    type="monotone"
                    dataKey="fwValue"
                    stroke={WATER_COLORS.fw}
                    strokeWidth={1.5}
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                    name="Frischwasser"
                  />
                  {(() => {
                    const cp = coldSection?.projection;
                    const cer = cp?.projected_meter_reading_end_of_year;
                    const csp = cp && cer && cp.basis !== 'actual_full_year' && cp.basis !== 'insufficient_data';
                    return csp ? (
                      <Line
                        type="monotone"
                        dataKey="fwProjected"
                        stroke={WATER_COLORS.fw}
                        strokeWidth={1.5}
                        strokeDasharray="5 5"
                        dot={(props: any) =>
                          props.payload.isFwEnd
                            ? <circle cx={props.cx} cy={props.cy} r={3} fill={WATER_COLORS.fw} />
                            : <></>
                        }
                        activeDot={false}
                        name="Frischwasser (prog.)"
                      />
                    ) : null;
                  })()}
                  <Line
                    type="monotone"
                    dataKey="gwValue"
                    stroke={WATER_COLORS.gw}
                    strokeWidth={1.5}
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                    name="Gartenwasser"
                  />
                  {(() => {
                    const gp = gardenSection?.projection;
                    const ger = gp?.projected_meter_reading_end_of_year;
                    const gsp = gp && ger && gp.basis !== 'actual_full_year' && gp.basis !== 'insufficient_data';
                    return gsp ? (
                      <Line
                        type="monotone"
                        dataKey="gwProjected"
                        stroke={WATER_COLORS.gw}
                        strokeWidth={1.5}
                        strokeDasharray="5 5"
                        dot={(props: any) =>
                          props.payload.isGwEnd
                            ? <circle cx={props.cx} cy={props.cy} r={3} fill={WATER_COLORS.gw} />
                            : <></>
                        }
                        activeDot={false}
                        name="Gartenwasser (prog.)"
                      />
                    ) : null;
                  })()}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                Keine Zählerstände für {year} vorhanden.
              </div>
            )}
          </div>
        </div>

{(wastewaterData || coldSection.projection) && (
          <div className="border rounded-lg p-3 bg-muted/20">
            <h4 className="text-xs font-semibold text-muted-foreground mb-2">Gegenüberstellung {year}</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

              <div>
                <h5 className="text-xs font-semibold text-muted-foreground mb-2">Frischwasser</h5>
                <div className="grid grid-cols-2 gap-1">
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Verbrauch tatsächlich</p>
                    <p className="text-xs font-semibold">{formatConsumption(coldConsActual)}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Frischwasserkosten tatsächlich</p>
                    <p className="text-xs font-semibold">{coldCostActual != null ? formatEuro(coldCostActual) : '—'}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Verbrauch prognostiziert</p>
                    <p className="text-xs font-semibold">{formatConsumption(coldConsProj)}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Frischwasserkosten prognostiziert</p>
                    <p className="text-xs font-semibold">{coldCostProj != null ? formatEuro(coldCostProj) : '—'}</p>
                  </div>
                  {coldDiff ? (
                    <>
                      <div className="bg-muted rounded p-1.5">
                        <p className="text-[10px] text-muted-foreground">Abschlagszahlungen hochgerechnet</p>
                        <p className="text-xs font-semibold">
                          {coldDiff.total_advance_payments != null ? formatEuro(coldDiff.total_advance_payments) : '—'}
                        </p>
                      </div>
                      <div className="bg-muted rounded p-1.5">
                        <p className="text-[10px] text-muted-foreground">Differenz Abschläge zu Kosten</p>
                        <p className="text-xs font-semibold" style={{
                          color: coldDiff.difference != null
                            ? (parseFloat(coldDiff.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                            : undefined,
                        }}>
                          {coldDiff.difference != null ? formatEuro(coldDiff.difference) : '—'}
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="col-span-2 bg-muted rounded p-1.5">
                      <p className="text-xs text-muted-foreground">Kein Abschlag für Frischwasser hinterlegt.</p>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h5 className="text-xs font-semibold text-muted-foreground mb-2">Abwasser</h5>
                <div className="grid grid-cols-2 gap-1">
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Verbrauch tatsächlich</p>
                    <p className="text-xs font-semibold">{formatConsumption(awConsActual)}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Abwasserkosten tatsächlich</p>
                    <p className="text-xs font-semibold">{awCostActual != null ? formatEuro(awCostActual) : '—'}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Verbrauch prognostiziert</p>
                    <p className="text-xs font-semibold">{formatConsumption(awConsProj)}</p>
                  </div>
                  <div className="bg-muted rounded p-1.5">
                    <p className="text-[10px] text-muted-foreground">Abwasserkosten prognostiziert</p>
                    <p className="text-xs font-semibold">{awCostProj != null ? formatEuro(awCostProj) : '—'}</p>
                  </div>
                  {awDiff ? (
                    <>
                      <div className="bg-muted rounded p-1.5">
                        <p className="text-[10px] text-muted-foreground">Abschlagszahlungen hochgerechnet</p>
                        <p className="text-xs font-semibold">
                          {awDiff.total_advance_payments != null ? formatEuro(awDiff.total_advance_payments) : '—'}
                        </p>
                      </div>
                      <div className="bg-muted rounded p-1.5">
                        <p className="text-[10px] text-muted-foreground">Differenz Abschläge zu Kosten</p>
                        <p className="text-xs font-semibold" style={{
                          color: awDiff.difference != null
                            ? (parseFloat(awDiff.difference) >= 0 ? '#16a34a' : 'hsl(var(--destructive))')
                            : undefined,
                        }}>
                          {awDiff.difference != null ? formatEuro(awDiff.difference) : '—'}
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="col-span-2 bg-muted rounded p-1.5">
                      <p className="text-xs text-muted-foreground">Kein Abschlag für Abwasser hinterlegt.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="border rounded-lg p-3">
          <h4 className="text-xs font-semibold text-muted-foreground mb-1">Zählerstände Frischwasser {year}</h4>
          <div className="max-h-36 overflow-y-auto">
            {coldSection.readings.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Datum</TableHead>
                    <TableHead className="text-xs">Wert (m³)</TableHead>
                    <TableHead className="text-xs">Notiz</TableHead>
                    <TableHead className="text-xs w-16"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {coldSection.readings.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-xs py-1">{new Date(r.reading_date).toLocaleDateString()}</TableCell>
                      <TableCell className="text-xs py-1">{parseFloat(r.value).toFixed(1)}</TableCell>
                      <TableCell className="text-xs py-1">{r.note || '—'}</TableCell>
                      <TableCell className="text-xs py-1">
                        <div className="flex gap-1">
                          <button
                            onClick={() => setEditingReading({ reading: r, meterId: coldSection.overviewItem.meter_id })}
                            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                            title="Bearbeiten"
                          >
                            <Pencil className="h-3 w-3" />
                          </button>
                          <button
                            onClick={() => setEditingReading({ reading: r, meterId: coldSection.overviewItem.meter_id })}
                            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-destructive transition-colors"
                            title="Löschen"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
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

        {gardenSection && (
          <div className="border rounded-lg p-3">
            <h4 className="text-xs font-semibold text-muted-foreground mb-1">Zählerstände Gartenwasser {year}</h4>
            <div className="max-h-36 overflow-y-auto">
              {gardenSection.readings.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Datum</TableHead>
                      <TableHead className="text-xs">Wert (m³)</TableHead>
                      <TableHead className="text-xs">Notiz</TableHead>
                      <TableHead className="text-xs w-16"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gardenSection.readings.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="text-xs py-1">{new Date(r.reading_date).toLocaleDateString()}</TableCell>
                        <TableCell className="text-xs py-1">{parseFloat(r.value).toFixed(1)}</TableCell>
                        <TableCell className="text-xs py-1">{r.note || '—'}</TableCell>
                        <TableCell className="text-xs py-1">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setEditingReading({ reading: r, meterId: gardenSection.overviewItem.meter_id })}
                              className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                              title="Bearbeiten"
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                            <button
                              onClick={() => setEditingReading({ reading: r, meterId: gardenSection.overviewItem.meter_id })}
                              className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-destructive transition-colors"
                              title="Löschen"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </TableCell>
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
        )}

        {wastewaterLoading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Lade Abwasserkosten...
          </div>
        )}
        {wastewaterError && (
          <div className="text-xs text-destructive">{wastewaterError}</div>
        )}

        {editingReading && (
          <ReadingEditDialog
            reading={editingReading.reading}
            unit="m³"
            onClose={() => setEditingReading(null)}
            onSaved={() => {
              const mid = editingReading.meterId;
              setEditingReading(null);
              if (onRefreshSection) onRefreshSection(mid);
            }}
          />
        )}

      </CardContent>
    </Card>
  );
};

export default WaterSection;
