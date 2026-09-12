import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectItem } from '../components/ui/select';
import { readingsApi, metersApi } from '../api/client';
import { meterTypeLabel, useMeterTypes } from '../hooks/useMeterTypes';
import { Meter } from '../types';
import { ArrowLeft, AlertTriangle, CheckCircle } from 'lucide-react';

const AddReading: React.FC = () => {
  const navigate = useNavigate();
  const [meters, setMeters] = useState<Meter[]>([]);
  const meterTypes = useMeterTypes();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_id: '',
    value: '',
    reading_date: new Date().toISOString().split('T')[0],
    note: '',
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, meter_id: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.meter_id || !formData.value || !formData.reading_date) {
      alert('Please fill in all required fields');
      return;
    }

    // Warn if the meter has been replaced; the user must confirm to proceed.
    if (isReplaced) {
      const proceed = window.confirm(
        `Achtung: Dieser Zähler wurde durch Zähler #${successor!.id} „${successor!.label}" ersetzt. ` +
        'Neue Ablesungen sollten normalerweise am Nachfolger eingetragen werden. ' +
        'Trotzdem fortfahren?'
      );
      if (!proceed) return;
    }

    try {
      setLoading(true);
      const payload = {
        ...formData,
        meter_id: parseInt(formData.meter_id),
        value: parseFloat(formData.value),
      };

      await readingsApi.create(payload);
      setSuccess(true);

      setTimeout(() => {
        navigate('/meters');
      }, 2000);
    } catch (err) {
      console.error('Error creating reading:', err);
      alert('Failed to create reading. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const selectedMeter = meters.find(m => m.id.toString() === formData.meter_id);

  // Determine if the selected meter has been replaced by a successor
  const successor = selectedMeter
    ? meters.find(m => m.replaces_meter_id === selectedMeter.id)
    : undefined;
  const isReplaced = !!successor;

  return (
    <div className="p-6">
      <Button variant="outline" className="mb-6 gap-2" onClick={() => navigate('/meters')}>
        <ArrowLeft className="h-4 w-4" />
        Back to Meters
      </Button>

      <div className="max-w-2xl mx-auto">
        {success ? (
          <Card>
            <CardContent className="p-8 text-center">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Reading Added Successfully!</h2>
              <p className="text-muted-foreground mb-4">
                The reading has been recorded and will appear in the meter details.
              </p>
              <p className="text-sm text-muted-foreground">Redirecting to meters list...</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Add New Reading</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="meter_id">Meter *</Label>
                  <Select
                    id="meter_id"
                    value={formData.meter_id}
                    onChange={handleSelectChange}
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

                  {/* Warnung, wenn der Zähler bereits ersetzt wurde */}
                  {isReplaced && successor && (
                    <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950 dark:border-amber-700 p-3 text-sm text-amber-800 dark:text-amber-200">
                      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                      <span>
                        Dieser Zähler wurde durch Zähler #{successor.id} „{successor.label}" ersetzt.
                        Neue Ablesungen sollten normalerweise beim Nachfolger-Zähler eingetragen werden.
                      </span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="value">Value *</Label>
                    <Input
                      id="value"
                      name="value"
                      type="number"
                      step="0.001"
                      required
                      value={formData.value}
                      onChange={handleChange}
                      placeholder="e.g., 1234.567"
                    />
                    {selectedMeter && (
                      <p className="text-sm text-muted-foreground">
                        Unit: {selectedMeter.unit}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reading_date">Date *</Label>
                    <Input
                      id="reading_date"
                      name="reading_date"
                      type="date"
                      required
                      value={formData.reading_date}
                      onChange={handleChange}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="note">Note (Optional)</Label>
                  <Textarea
                    id="note"
                    name="note"
                    value={formData.note}
                    onChange={handleChange}
                    placeholder="Add any notes about this reading..."
                    rows={3}
                  />
                </div>

                <div className="flex justify-end gap-4 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/meters')}
                    disabled={loading}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={loading}>
                    {loading ? 'Adding...' : 'Add Reading'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            * Required fields. Readings are stored locally and can be viewed in the meter details page.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AddReading;
