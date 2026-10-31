import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { metersApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { useMeterTypes } from '../hooks/useMeterTypes';
import { Meter, MeterType } from '../types';
import { ArrowLeft, CheckCircle } from 'lucide-react';

const MeterForm: React.FC = () => {
  const navigate = useNavigate();
  const meterTypes = useMeterTypes();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_type: '' as MeterType | '',
    label: '',
    meter_number: '',
    replaces_meter_id: '' as string, // empty string = keine Auswahl
  });

  // Load all meters for the "Ersetzt Zähler" dropdown
  const { data: allMetersData } = useFetch<Meter[]>(async () => {
    try {
      return await metersApi.getAll();
    } catch {
      throw new Error('Fehler beim Laden der Zähler');
    }
  }, []);
  const allMeters = allMetersData ?? [];

  // The first meter type is selected as soon as the types have loaded.
  // Derived during render instead of the previous setState-in-effect, so
  // no state update is triggered by an effect. (Explicit length check:
  // indexing alone keeps TS from widening the type with ''.)
  const firstType: MeterType | '' =
    meterTypes.length > 0 ? meterTypes[0].value : '';
  const effectiveMeterType: MeterType | '' =
    formData.meter_type !== '' ? formData.meter_type : firstType;

  // Computed up front: the equality checks below narrow effectiveMeterType
  // away from '' (const closure narrowing), so this flag is derived here.
  const hasMeterType = effectiveMeterType !== '';

  const selectedType = meterTypes.find(
    (type) => type.value === effectiveMeterType
  );

  // Meters eligible as predecessors:
  // - same type as currently selected type
  // - not already replaced by another meter (no meter in allMeters has replaces_meter_id pointing to it)
  const replacedMeterIds = new Set(
    allMeters
      .filter((m) => m.replaces_meter_id !== null)
      .map((m) => m.replaces_meter_id as number)
  );
  const eligiblePredecessors = allMeters.filter(
    (m) => m.meter_type === effectiveMeterType && !replacedMeterIds.has(m.id)
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({
      ...prev,
      meter_type: e.target.value as MeterType,
      replaces_meter_id: '', // reset predecessor when type changes
    }));
  };

  const handlePredecessorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, replaces_meter_id: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!hasMeterType || !formData.label.trim()) {
      alert('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setLoading(true);
      // No "unit" field: the unit is derived server-side from meter_type
      const payload: Record<string, unknown> = {
        meter_type: effectiveMeterType,
        label: formData.label.trim(),
        meter_number: formData.meter_number.trim() || null,
      };

      if (formData.replaces_meter_id !== '') {
        payload.replaces_meter_id = parseInt(formData.replaces_meter_id, 10);
      }

      await metersApi.create(payload);
      setSuccess(true);

      setTimeout(() => {
        navigate('/meters');
      }, 2000);
    } catch (err) {
      console.error('Error creating meter:', err);
      alert('Fehler beim Erstellen des Zählers. Bitte erneut versuchen.');
    } finally {
      setLoading(false);
    }
  };

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
              <h2 className="text-2xl font-bold mb-2">Zähler hinzugefügt!</h2>
              <p className="text-muted-foreground mb-4">
                Der Zähler wurde erstellt und erscheint in der Zählerliste.
              </p>
              <p className="text-sm text-muted-foreground">Weiterleitung zur Zählerliste...</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Neuer Zähler</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="label">Name *</Label>
                  <Input
                    id="label"
                    name="label"
                    type="text"
                    required
                    value={formData.label}
                    onChange={handleChange}
                    placeholder="z. B. Hauptzähler Strom, Kaltwasser, Gasherdkreis"
                    maxLength={100}
                  />
                  <p className="text-sm text-muted-foreground">
                    Beschreibender Name für den Zähler (max. 100 Zeichen)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="meter_number">Zählernummer</Label>
                  <Input
                    id="meter_number"
                    name="meter_number"
                    type="text"
                    value={formData.meter_number}
                    onChange={handleChange}
                    placeholder="z. B. 1EMH0012345678"
                    maxLength={100}
                  />
                  <p className="text-sm text-muted-foreground">
                    Optionale eindeutige Zählernummer des Herstellers
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="meter_type">Zählertyp *</Label>
                    <Select
                      id="meter_type"
                      value={effectiveMeterType}
                      onChange={handleTypeChange}
                    >
                      {meterTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </Select>
                    <p className="text-sm text-muted-foreground">
                      Bestimmt die Messeinheit des Zählers
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Einheit</Label>
                    {selectedType ? (
                      <p className="text-lg">{selectedType.unit}</p>
                    ) : (
                      <p className="text-lg text-muted-foreground">–</p>
                    )}
                    <p className="text-sm text-muted-foreground">
                      Wird automatisch durch den Zählertyp bestimmt
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="replaces_meter_id">Ersetzt Zähler</Label>
                  <Select
                    id="replaces_meter_id"
                    value={formData.replaces_meter_id}
                    onChange={handlePredecessorChange}
                  >
                    <SelectItem value="">— Kein Vorgänger —</SelectItem>
                    {eligiblePredecessors.map((m) => (
                      <SelectItem key={m.id} value={m.id.toString()}>
                        #{m.id} {m.label}
                        {m.meter_number ? ` (${m.meter_number})` : ''}
                      </SelectItem>
                    ))}
                  </Select>
                  <p className="text-sm text-muted-foreground">
                    Optional: der Vorgänger-Zähler, den dieser neue Zähler physisch ersetzt.
                    Die Verbrauchshistorie bleibt dann erhalten.
                  </p>
                  {eligiblePredecessors.length === 0 && hasMeterType && (
                    <p className="text-sm text-muted-foreground italic">
                      Keine austauschbaren Zähler dieses Typs gefunden.
                    </p>
                  )}
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
                    {loading ? 'Speichern...' : 'Zähler erstellen'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            * Pflichtfelder. Zähler werden verwendet, um Zählerstände und Tarifzeiträume zu erfassen.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MeterForm;
