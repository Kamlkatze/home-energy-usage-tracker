import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { advancePaymentsApi } from '../api/advancePaymentsApi';
import { metersApi } from '../api/client';
import { Meter, AdvancePaymentCategory } from '../types';
import { ADVANCE_PAYMENT_CATEGORY_LABELS, ADVANCE_PAYMENT_CATEGORIES, getMeterFieldsForCategory, filterMetersForCategory } from '../lib/advancePaymentFields';
import { ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';

const AdvancePaymentForm: React.FC = () => {
  const navigate = useNavigate();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [metersLoading, setMetersLoading] = useState(true);
  const [metersError, setMetersError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [category, setCategory] = useState<AdvancePaymentCategory>(ADVANCE_PAYMENT_CATEGORIES[0]);
  const [validFrom, setValidFrom] = useState(new Date().toISOString().split('T')[0]);
  const [validTo, setValidTo] = useState('');
  const [monthlyAmount, setMonthlyAmount] = useState('');
  const [comment, setComment] = useState('');
  const [meterSelections, setMeterSelections] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchMeters();
  }, []);

  const fetchMeters = async () => {
    try {
      setMetersLoading(true);
      setMetersError(null);
      const data = await metersApi.getAll();
      setMeters(data);
    } catch (err) {
      console.error('Error fetching meters:', err);
      setMetersError('Fehler beim Laden der Zähler');
    } finally {
      setMetersLoading(false);
    }
  };

  const fields = getMeterFieldsForCategory(category);

  useEffect(() => {
    const initial: Record<string, string> = {};
    for (const f of fields) {
      const filtered = filterMetersForCategory(meters, f);
      if (filtered.length > 0 && !initial[f.name]) {
        initial[f.name] = f.allowNull ? '' : filtered[0].id.toString();
      } else if (!initial[f.name]) {
        initial[f.name] = '';
      }
    }
    setMeterSelections((prev) => ({ ...prev, ...initial }));
  }, [category, meters]);

  const handleMeterChange = (fieldName: string, value: string) => {
    setMeterSelections((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!validFrom || !monthlyAmount) {
      setErrorMessage('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    const requiredFields = fields.filter((f) => f.required);
    const emptyRequired = requiredFields.filter((f) => {
      const val = meterSelections[f.name];
      return !val || val === '';
    });
    if (emptyRequired.length > 0) {
      setErrorMessage('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setLoading(true);

      const payload: Record<string, unknown> = {
        category,
        valid_from: validFrom,
        monthly_amount: monthlyAmount,
      };

      if (validTo) {
        payload.valid_to = validTo;
      }

      if (category === 'wastewater') {
        payload.meter_id = null;
        payload.water_cold_meter_id = parseInt(meterSelections.water_cold_meter_id);
        const gardenId = meterSelections.water_garden_meter_id;
        payload.water_garden_meter_id = gardenId && gardenId !== '' ? parseInt(gardenId) : null;
        payload.water_cold_meter_id = parseInt(meterSelections.water_cold_meter_id);
      } else {
        payload.meter_id = parseInt(meterSelections.meter_id);
        payload.water_cold_meter_id = null;
        payload.water_garden_meter_id = null;
      }

      payload.comment = comment || null;

      await advancePaymentsApi.create(payload);
      setSuccess(true);

      setTimeout(() => {
        navigate('/advance-payments');
      }, 2000);
    } catch (err) {
      console.error('Error creating advance payment:', err);
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setErrorMessage(detail || 'Fehler beim Erstellen der Abschlagszahlung. Bitte erneut versuchen.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <Button variant="outline" className="mb-6 gap-2" onClick={() => navigate('/advance-payments')}>
        <ArrowLeft className="h-4 w-4" />
        Zurück zu den Abschlagszahlungen
      </Button>

      <div className="max-w-2xl mx-auto">
        {success ? (
          <Card>
            <CardContent className="p-8 text-center">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Abschlagszahlung hinzugefügt!</h2>
              <p className="text-muted-foreground mb-4">
                Die Abschlagszahlung wurde gespeichert.
              </p>
              <p className="text-sm text-muted-foreground">Weiterleitung zur Übersicht...</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Neue Abschlagszahlung hinzufügen</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="category">Kategorie *</Label>
                  <Select
                    id="category"
                    value={category}
                    onChange={(e) => setCategory(e.target.value as AdvancePaymentCategory)}
                  >
                    {ADVANCE_PAYMENT_CATEGORIES.map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {ADVANCE_PAYMENT_CATEGORY_LABELS[cat]}
                      </SelectItem>
                    ))}
                  </Select>
                </div>

                {fields.map((field) => {
                  const filteredMeters = filterMetersForCategory(meters, field);
                  return (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={field.name}>
                        {field.label}{field.required ? ' *' : ''}
                      </Label>
                      {metersLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Lade Zähler...
                        </div>
                      ) : metersError ? (
                        <div className="text-sm text-destructive">
                          {metersError}
                        </div>
                      ) : (
                        <Select
                          id={field.name}
                          value={meterSelections[field.name] ?? ''}
                          onChange={(e) => handleMeterChange(field.name, e.target.value)}
                        >
                          {field.allowNull && (
                            <SelectItem value="">
                              {field.nullLabel ?? 'Keine Auswahl'}
                            </SelectItem>
                          )}
                          {filteredMeters.map((meter) => (
                            <SelectItem key={meter.id} value={meter.id.toString()}>
                              {meter.label}
                            </SelectItem>
                          ))}
                        </Select>
                      )}
                    </div>
                  );
                })}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="valid_from">Gültig ab *</Label>
                    <Input
                      id="valid_from"
                      type="date"
                      required
                      value={validFrom}
                      onChange={(e) => setValidFrom(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="valid_to">Gültig bis (optional)</Label>
                    <Input
                      id="valid_to"
                      type="date"
                      value={validTo}
                      onChange={(e) => setValidTo(e.target.value)}
                    />
                    <p className="text-sm text-muted-foreground">
                      Leer = unbefristet
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="monthly_amount">Monatlicher Betrag (€) *</Label>
                  <Input
                    id="monthly_amount"
                    type="number"
                    step="0.01"
                    required
                    value={monthlyAmount}
                    onChange={(e) => setMonthlyAmount(e.target.value)}
                    placeholder="z. B. 85.00"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="comment">Anbieter / Kommentar</Label>
                  <Input
                    id="comment"
                    type="text"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="z. B. Stadtwerke Musterstadt"
                  />
                </div>

                {errorMessage && (
                  <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                    {errorMessage}
                  </div>
                )}

                <div className="flex justify-end gap-4 pt-6">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/advance-payments')}
                    disabled={loading}
                  >
                    Abbrechen
                  </Button>
                  <Button
                    type="submit"
                    disabled={loading || metersLoading}
                  >
                    {loading ? 'Speichern...' : 'Abschlagszahlung hinzufügen'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default AdvancePaymentForm;