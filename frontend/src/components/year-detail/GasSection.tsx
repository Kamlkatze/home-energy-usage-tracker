import React from 'react';
import { MeterSection, AdvancePaymentDiffs } from './types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import MeterBlock from './MeterBlock';

interface GasSectionProps {
  sections: MeterSection[];
  advancePaymentDiffs: AdvancePaymentDiffs;
  year: number;
}

const GasSection: React.FC<GasSectionProps> = ({ sections, advancePaymentDiffs, year }) => {
  if (sections.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          Weitere Zähler {year}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {sections.map((section, idx) => (
          <MeterBlock
            key={section.overviewItem.meter_id}
            section={section}
            meterIdx={idx}
            advancePaymentDiffs={advancePaymentDiffs}
            year={year}
          />
        ))}
      </CardContent>
    </Card>
  );
};

export default GasSection;