import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { tariffsApi, metersApi } from '../api/client';
import { Meter, TariffKind } from '../types';
import { ArrowLeft, CheckCircle } from 'lucide-react';

const TARIFF_KIND_LABELS: Record<TariffKind, string> = {
  consumption: 'Arbeitspreis',
  base_fee: 'Grundpreis',
  feed_in: 'Einspeisevergütung',
  self_consumption: 'Selbstverbrauchsvergütung',
  metering_fee: 'Messstellenbetrieb',
};

const TARIFF_KINDS = Object.keys(TARIFF_KIND_LABELS) as TariffKind[];

const TariffForm: React.FC = () => {
  const navigate = useNavigate();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_id: '',
    tariff_kind: 'consumption' as TariffKind,
    valid_from: new Date().toISOString().split('T')[0],
    valid_to: '',
    price_per_unit: '',
    base_fee_monthly: '',
  });

  useEffect(() => {
    fetchMeters();
  }, []);

  const fetchMeters = async () => {
    try {
      const data = await metersApi.getAll();
      setMeters(data);
      if (data.length > 0 && !formData.meter_id) {
        setFormData(prev => ({ ...prev, meter_id: data[0].id.toString() }));
      }
    } catch (err) {
      console.error('Error fetching meters:', err);
    }
  };

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

    if (!formData.meter_id || !formData.valid_from || !formData.price_per_unit) {
      alert('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setLoading(true);
      // Prices are sent as strings to preserve decimal precision
      const payload: Record<string, string | number> = {
        meter_id: parseInt(formData.meter_id),
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

  const selectedMeter = meters.find(m => m.id.toString() === formData.meter_id);

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
                  <Select
                    id="meter_id"
                    value={formData.meter_id}
                    onChange={handleMeterChange}
                  >
                    {meters.map((meter) => (
                      <SelectItem key={meter.id} value={meter.id.toString()}>
                        {meter.label} ({meter.meter_type} • {meter.unit})
                      </SelectItem>
                    ))}
                  </Select>
                  {selectedMeter && (
                    <p className="text-sm text-muted-foreground">
                      Ausgewählter Zähler: {selectedMeter.label} ({selectedMeter.meter_type})
                    </p>
                  )}
                </div>

                <div className="space-y-2">
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="price_per_unit">
                      Preis pro Einheit {selectedMeter ? `(${selectedMeter.unit})` : ''} *
                    </Label>
                    <Input
                      id="price_per_unit"
                      name="price_per_unit"
                      type="number"
                      step="0.00001"
                      required
                      value={formData.price_per_unit}
                      onChange={handleChange}
                      placeholder="z. B. 0.35490"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="base_fee_monthly">Grundpreis monatlich (optional)</Label>
                    <Input
                      id="base_fee_monthly"
                      name="base_fee_monthly"
                      type="number"
                      step="0.01"
                      value={formData.base_fee_monthly}
                      onChange={handleChange}
                      placeholder="z. B. 12.50"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-4 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/meters')}
                    disabled={loading}
                  >
                    Abbrechen
                  </Button>
                  <Button type="submit" disabled={loading}>
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
