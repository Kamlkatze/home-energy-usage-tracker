import React from 'react';
import { MeterSection, AdvancePaymentDiffs } from './types';
import { basisLabel } from './utils';
import { formatEuro } from '../shared/chartHelpers';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Loader2, Zap } from 'lucide-react';
import { FeedInCompensation, FeedInCompensationProjection, YearlyProjection } from '../../types';
import MeterBlock from './MeterBlock';

interface ElectricitySectionProps {
  sections: MeterSection[];
  year: number;
  eegData: FeedInCompensation | null;
  eegLoading: boolean;
  eegError: string | null;
  eegProjection: FeedInCompensationProjection | null;
  eegProjectionLoading: boolean;
  eegProjectionError: string | null;
  advancePaymentDiffs: AdvancePaymentDiffs;
  onRefreshSection?: (meterId: number) => void;
}

const ElectricitySection: React.FC<ElectricitySectionProps> = ({
  sections, year,
  eegData, eegLoading, eegError,
  eegProjection, eegProjectionLoading, eegProjectionError,
  advancePaymentDiffs,
  onRefreshSection,
}) => {
  if (sections.length === 0) return null;

  return (
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
        {sections.map((s, i) => (
          <MeterBlock
            key={s.overviewItem.meter_id}
            section={s}
            meterIdx={i}
            advancePaymentDiffs={advancePaymentDiffs}
            year={year}
            onRefreshSection={onRefreshSection}
          />
        ))}
      </CardContent>
    </Card>
  );
};

export default ElectricitySection;