import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { costsApi, metersApi, electricityApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { Meter, Reading, YearsOverviewItem, FeedInCompensation, FeedInCompensationProjection, WastewaterCosts, AdvancePaymentDiffByCategory } from '../types';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Loader2, ArrowLeft } from 'lucide-react';
import { MeterSection } from '../components/year-detail/types';
import ElectricitySection from '../components/year-detail/ElectricitySection';
import WaterSection from '../components/year-detail/WaterSection';
import GasSection from '../components/year-detail/GasSection';

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

const YearDetail: React.FC = () => {
  const { year: yearParam } = useParams<{ year: string }>();
  const year = parseInt(yearParam || '', 10);
  const [sections, setSections] = useState<MeterSection[]>([]);
  const [eegData, setEegData] = useState<FeedInCompensation | null>(null);
  const [eegLoading, setEegLoading] = useState(false);
  const [eegError, setEegError] = useState<string | null>(null);
  const [eegProjection, setEegProjection] = useState<FeedInCompensationProjection | null>(null);
  const [eegProjectionLoading, setEegProjectionLoading] = useState(false);
  const [eegProjectionError, setEegProjectionError] = useState<string | null>(null);
  const [wastewaterData, setWastewaterData] = useState<WastewaterCosts | null>(null);
  const [wastewaterLoading, setWastewaterLoading] = useState(false);
  const [wastewaterError, setWastewaterError] = useState<string | null>(null);

  const sectionsRef = React.useRef(sections);
  // Keep the ref in sync after commit (assigning a ref during render is
  // not allowed, see react-hooks/refs).
  useEffect(() => {
    sectionsRef.current = sections;
  }, [sections]);

  const refreshSection = useCallback(async (meterId: number) => {
    const currentSections = sectionsRef.current;
    const section = currentSections.find(s => s.overviewItem.meter_id === meterId);
    if (!section) return;

    try {
      const readingsPromises = section.chain.map((m) =>
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

      setSections(prev => prev.map(s =>
        s.overviewItem.meter_id === meterId
          ? { ...s, readings: allChainReadings, projectionLoading: true, projectionError: null }
          : s
      ));

      const projection = await costsApi.getYearlyProjection(meterId, year);
      setSections(prev => prev.map(s =>
        s.overviewItem.meter_id === meterId
          ? { ...s, projection, projectionLoading: false }
          : s
      ));
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Fehler beim Laden der Daten.';
      setSections(prev => prev.map(s =>
        s.overviewItem.meter_id === meterId
          ? { ...s, projectionError: msg, projectionLoading: false }
          : s
      ));
    }
  }, [year]);

  const [advancePaymentDiffs, setAdvancePaymentDiffs] = useState<Record<
    'gas' | 'cold_water' | 'wastewater' | 'power_import',
    AdvancePaymentDiffByCategory | null
  >>({
    gas: null,
    cold_water: null,
    wastewater: null,
    power_import: null,
  });

  const { loading, error } = useFetch<null>(async () => {
    try {
      if (isNaN(year)) {
        throw new Error('Ungültiges Jahr.');
      }

      const [overviewData, allMeters] = await Promise.all([
        costsApi.getYearsOverview() as Promise<YearsOverviewItem[]>,
        metersApi.getAll() as Promise<Meter[]>,
      ]);

      const relevantItems = overviewData.filter(
        (item) => item.years.some((y) => y.year === year)
      );

      if (relevantItems.length === 0) {
        setSections([]);
        return null;
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
        key:'gas' | 'cold_water' | 'wastewater' | 'power_import';
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
      return null;
    } catch (err: any) {
      // Surface the error via useFetch's error state (and its central log).
      throw new Error(
        err?.response?.data?.detail ||
        err?.message ||
        'Fehler beim Laden der Jahresdaten.'
      );
    }
  }, [year]);

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

  const electricTypes = ['electricity_import', 'electricity_export', 'electricity_production'];
  const waterTypes = ['water_cold', 'water_garden'];

  const electricSections = sections.filter((s) =>
    electricTypes.includes(s.overviewItem.meter_type)
  );
  const otherSections = sections.filter(
    (s) =>
      !electricTypes.includes(s.overviewItem.meter_type) &&
      !waterTypes.includes(s.overviewItem.meter_type)
  );

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

      <ElectricitySection
        sections={electricSections}
        year={year}
        eegData={eegData}
        eegLoading={eegLoading}
        eegError={eegError}
        eegProjection={eegProjection}
        eegProjectionLoading={eegProjectionLoading}
        eegProjectionError={eegProjectionError}
        advancePaymentDiffs={advancePaymentDiffs}
        onRefreshSection={refreshSection}
      />

      <WaterSection
        sections={sections}
        year={year}
        advancePaymentDiffs={advancePaymentDiffs}
        wastewaterData={wastewaterData}
        wastewaterLoading={wastewaterLoading}
        wastewaterError={wastewaterError}
        onRefreshSection={refreshSection}
      />

      <GasSection
        sections={otherSections}
        advancePaymentDiffs={advancePaymentDiffs}
        year={year}
        onRefreshSection={refreshSection}
      />
    </div>
  );
};

export default YearDetail;