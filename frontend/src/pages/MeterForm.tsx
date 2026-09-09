import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectItem } from '../components/ui/select';
import { metersApi } from '../api/client';
import { MeterType } from '../types';
import { ArrowLeft, CheckCircle } from 'lucide-react';

const METER_TYPE_LABELS: Record<MeterType, string> = {
  electricity: 'Electricity',
  gas: 'Gas',
  water: 'Water',
};

const METER_TYPES = Object.keys(METER_TYPE_LABELS) as MeterType[];

const MeterForm: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    meter_type: 'electricity' as MeterType,
    label: '',
    unit: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, meter_type: e.target.value as MeterType }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.meter_type || !formData.label.trim() || !formData.unit.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      setLoading(true);
      const payload = {
        meter_type: formData.meter_type,
        label: formData.label.trim(),
        unit: formData.unit.trim(),
      };
      
      await metersApi.create(payload);
      setSuccess(true);
      
      setTimeout(() => {
        navigate('/meters');
      }, 2000);
    } catch (err) {
      console.error('Error creating meter:', err);
      alert('Failed to create meter. Please try again.');
    } finally {
      setLoading(false);
    }
  };

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
              <h2 className="text-2xl font-bold mb-2">Meter Added Successfully!</h2>
              <p className="text-muted-foreground mb-4">
                The meter has been created and will appear in the meters list.
              </p>
              <p className="text-sm text-muted-foreground">Redirecting to meters list...</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Add New Meter</CardTitle>
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
                    placeholder="e.g., Main electricity meter, Water supply, Gas heater"
                    maxLength={100}
                  />
                  <p className="text-sm text-muted-foreground">
                    Descriptive name for the meter (max 100 characters)
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="meter_type">Meter Type *</Label>
                    <Select
                      id="meter_type"
                      value={formData.meter_type}
                      onChange={handleTypeChange}
                    >
                      {METER_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {METER_TYPE_LABELS[type]}
                        </SelectItem>
                      ))}
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="unit">Unit *</Label>
                    <Input
                      id="unit"
                      name="unit"
                      type="text"
                      required
                      value={formData.unit}
                      onChange={handleChange}
                      placeholder="e.g., kWh, m³, l"
                      maxLength={20}
                    />
                    <p className="text-sm text-muted-foreground">
                      Unit of measurement (max 20 characters)
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
                    Cancel
                  </Button>
                  <Button type="submit" disabled={loading}>
                    {loading ? 'Creating...' : 'Create Meter'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            * Required fields. Meters are used to track consumption readings and tariffs.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MeterForm;