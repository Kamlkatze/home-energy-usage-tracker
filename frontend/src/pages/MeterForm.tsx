import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { metersApi } from '../api/client';
import { useMeterTypes } from '../hooks/useMeterTypes';
import { MeterType } from '../types';
import { ArrowLeft, CheckCircle } from 'lucide-react';

const MeterForm: React.FC = () => {
  const navigate = useNavigate();
  const meterTypes = useMeterTypes();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_type: '' as MeterType | '',
    label: '',
  });

  // Select the first meter type once the types have loaded
  useEffect(() => {
    if (meterTypes.length > 0) {
      setFormData((prev) =>
        prev.meter_type === ''
          ? { ...prev, meter_type: meterTypes[0].value }
          : prev
      );
    }
  }, [meterTypes]);

  const selectedType = meterTypes.find(
    (type) => type.value === formData.meter_type
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, meter_type: e.target.value as MeterType }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.meter_type || !formData.label.trim()) {
      alert('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setLoading(true);
      // No "unit" field: the unit is derived server-side from meter_type
      const payload = {
        meter_type: formData.meter_type,
        label: formData.label.trim(),
      };

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
              <CardTitle>Neuen Zähler hinzufügen</CardTitle>
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="meter_type">Zählertyp *</Label>
                    <Select
                      id="meter_type"
                      value={formData.meter_type}
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
