import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { tariffsApi, metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter, TariffKind } from '../types';
import { ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';
import { getTariffFields, TARIFF_KIND_LABELS, TARIFF_KINDS } from '../lib/tariffFields';

const TariffForm: React.FC = () => {
  const navigate = useNavigate();
  const meterTypes = useMeterTypes();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_id: '',
    tariff_kind: 'consumption' as TariffKind,
    valid_from: new Date().toISOString().split('T')[0],
    valid_to: '',
    price_per_unit: '',
    base_fee_monthly: '',
    metering_fee_monthly: '',
    gas_z_zahl: '',
    gas_brennwert: '',
    eeg_tier1_rate: '',
    eeg_tier2_rate: '',
    metering_point_fee_yearly: '',
    comment: '',
  });

  const {
    data: metersData,
    loading: metersLoading,
    error: metersError,
  } = useFetch<Meter[]>(async () => {
    try {
      return await metersApi.getAll();
    } catch {
      throw new Error('Fehler beim Laden der Zähler');
    }
  }, []);
  const meters = metersData ?? [];

  // The first meter is preselected as soon as the list has loaded (and no
  // other meter was picked by the user). Derived during render instead of
  // set inside the fetch callback, to avoid a state update from the effect.
  const effectiveMeterId =
    formData.meter_id !== '' ? formData.meter_id : meters[0]?.id.toString() ?? '';

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleMeterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, meter_id: e.target.value }));
  };

  const handleKindChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, tariff_kind: e.target.value as TariffKind }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!effectiveMeterId || !formData.valid_from || !formData.price_per_unit) {
      alert('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    const selectedMeter = meters.find(m => m.id.toString() === effectiveMeterId);
    const fields = getTariffFields(formData.tariff_kind, selectedMeter?.meter_type, selectedMeter?.unit);

    const requiredFields = fields.filter(f => f.required);
    const emptyRequired = requiredFields.filter(f => !formData[f.name as keyof typeof formData]);
    if (emptyRequired.length > 0) {
      alert('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setLoading(true);
      const payload: Record<string, string | number> = {
        meter_id: parseInt(effectiveMeterId, 10),
        tariff_kind: formData.tariff_kind,
        valid_from: formData.valid_from,
        price_per_unit: formData.price_per_unit,
      };
      if (formData.valid_to) {
        payload.valid_to = formData.valid_to;
      }
      if (formData.base_fee_monthly) {
        payload.base_fee_monthly = formData.base_fee_monthly;
      }
      if (formData.metering_fee_monthly) {
        payload.metering_fee_monthly = formData.metering_fee_monthly;
      }
      if (formData.gas_z_zahl) {
        payload.gas_z_zahl = formData.gas_z_zahl;
      }
      if (formData.gas_brennwert) {
        payload.gas_brennwert = formData.gas_brennwert;
      }
      if (formData.eeg_tier1_rate) {
        payload.eeg_tier1_rate = formData.eeg_tier1_rate;
      }
      if (formData.eeg_tier2_rate) {
        payload.eeg_tier2_rate = formData.eeg_tier2_rate;
      }
      if (formData.metering_point_fee_yearly) {
        payload.metering_point_fee_yearly = formData.metering_point_fee_yearly;
      }
      if (formData.comment) {
        payload.comment = formData.comment;
      }

      await tariffsApi.create(payload);
      setSuccess(true);

      setTimeout(() => {
        navigate('/meters');
      }, 2000);
    } catch (err) {
      console.error('Error creating tariff period:', err);
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      alert(detail || 'Fehler beim Erstellen des Tarifzeitraums. Bitte erneut versuchen.');
    } finally {
      setLoading(false);
    }
  };

  const selectedMeter = meters.find(m => m.id.toString() === effectiveMeterId);
  const fields = getTariffFields(
    formData.tariff_kind,
    selectedMeter?.meter_type,
    selectedMeter?.unit,
  );
  const eegFields = fields.filter(f => f.group === 'eeg');
  const mainFields = fields.filter(f => f.group !== 'eeg');

  return (
    <div className="p-6">
      <Button variant="outline" className="mb-6 gap-2" onClick={() => navigate('/meters')}>
        <ArrowLeft className="h-4 w-4" />
        Zurück zu den Zählern
      </Button>

      <div className="max-w-2xl mx-auto">
        {success ? (
          <Card>
            <CardContent className="p-8 text-center">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Tarifzeitraum hinzugefügt!</h2>
              <p className="text-muted-foreground mb-4">
                Der Tarifzeitraum wurde gespeichert.
              </p>
              <p className="text-sm text-muted-foreground">Weiterleitung zur Zählerliste...</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Neuen Tarifzeitraum hinzufügen</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="meter_id">Zähler *</Label>
                  {metersLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Lade Zähler...
                    </div>
                  ) : metersError ? (
                    <div className="text-sm text-destructive">
                      {metersError}
                    </div>
                  ) : meters.length === 0 ? (
                    <div className="text-sm text-muted-foreground">
                      Keine Zähler vorhanden. Bitte zuerst einen Zähler anlegen.
                    </div>
                  ) : (
                    <>
                      <Select
                        id="meter_id"
                        value={effectiveMeterId}
                        onChange={handleMeterChange}
                      >
                        {meters.map((meter) => (
                          <SelectItem key={meter.id} value={meter.id.toString()}>
                            {meter.label} ({meterTypeLabel(meterTypes, meter.meter_type)} • {meter.unit})
                          </SelectItem>
                        ))}
                      </Select>
                      {selectedMeter && (
                        <p className="text-sm text-muted-foreground">
                          Ausgewählter Zähler: {selectedMeter.label} ({meterTypeLabel(meterTypes, selectedMeter.meter_type)})
                        </p>
                      )}
                      {formData.tariff_kind === 'feed_in_eeg2009' && (
                        <p className="text-sm text-muted-foreground mt-2">
                          Dieser Tarif muss auf dem Einspeise-Zähler (Strom Einspeisung) angelegt werden, nicht auf dem Erzeugungszähler.
                        </p>
                      )}
                    </>
                  )}
                </div>

                <div className="space-y-2 mt-6">
                  <Label htmlFor="tariff_kind">Tarifart *</Label>
                  <Select
                    id="tariff_kind"
                    value={formData.tariff_kind}
                    onChange={handleKindChange}
                  >
                    {TARIFF_KINDS.map((kind) => (
                      <SelectItem key={kind} value={kind}>
                        {TARIFF_KIND_LABELS[kind]}
                      </SelectItem>
                    ))}
                  </Select>
                  <p className="text-sm text-muted-foreground">
                    Verschiedene Tarifarten dürfen sich zeitlich überschneiden
                    (z.&nbsp;B. Arbeitspreis und Einspeisevergütung).
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                  <div className="space-y-2">
                    <Label htmlFor="valid_from">Gültig ab *</Label>
                    <Input
                      id="valid_from"
                      name="valid_from"
                      type="date"
                      required
                      value={formData.valid_from}
                      onChange={handleChange}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="valid_to">Gültig bis (optional)</Label>
                    <Input
                      id="valid_to"
                      name="valid_to"
                      type="date"
                      value={formData.valid_to}
                      onChange={handleChange}
                    />
                    <p className="text-sm text-muted-foreground">
                      Ohne Enddatum läuft der Zeitraum unbefristet weiter.
                    </p>
                  </div>
                </div>

                {mainFields.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    {mainFields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label htmlFor={field.name}>
                          {field.label}{field.required ? ' *' : ''}
                        </Label>
                        <Input
                          id={field.name}
                          name={field.name}
                          type="number"
                          step={field.step}
                          required={field.required}
                          value={formData[field.name as keyof typeof formData]}
                          onChange={handleChange}
                          placeholder={field.placeholder}
                        />
                        {field.helperText && (
                          <p className="text-sm text-muted-foreground">{field.helperText}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {eegFields.length > 0 && (
                  <div className="mt-6 border border-blue-200 rounded-lg p-4 bg-blue-50/50">
                    <h3 className="text-sm font-semibold text-blue-800 mb-3">
                      EEG 2009 Vergütungssätze
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {eegFields.map((field) => (
                        <div key={field.name} className="space-y-2">
                          <Label htmlFor={field.name}>
                            {field.label} *
                          </Label>
                          <Input
                            id={field.name}
                            name={field.name}
                            type="number"
                            step={field.step}
                            required
                            value={formData[field.name as keyof typeof formData]}
                            onChange={handleChange}
                            placeholder={field.placeholder}
                          />
                          {field.helperText && (
                            <p className="text-sm text-muted-foreground">{field.helperText}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="comment">Anbieter / Kommentar</Label>
                  <Input
                    id="comment"
                    name="comment"
                    type="text"
                    value={formData.comment}
                    onChange={handleChange}
                    placeholder="z. B. Stadtwerke Musterstadt"
                  />
                </div>

                <div className="flex justify-end gap-4 pt-6">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/meters')}
                    disabled={loading}
                  >
                    Abbrechen
                  </Button>
                  <Button
                    type="submit"
                    disabled={loading || metersLoading || meters.length === 0}
                  >
                    {loading ? 'Speichern...' : 'Tarifzeitraum hinzufügen'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            * Pflichtfelder. Sich überschneidende Zeiträume derselben Tarifart
            werden vom System abgelehnt.
          </p>
        </div>
      </div>
    </div>
  );
};

export default TariffForm;