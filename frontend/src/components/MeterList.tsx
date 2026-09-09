import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { metersApi } from '../api/client';
import { Meter } from '../types';

const MeterList: React.FC = () => {
  const [meters, setMeters] = useState<Meter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMeters();
  }, []);

  const fetchMeters = async () => {
    try {
      setLoading(true);
      const data = await metersApi.getAll();
      setMeters(data);
      setError(null);
    } catch (err) {
      setError('Failed to load meters. Please try again.');
      console.error('Error fetching meters:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this meter?')) {
      try {
        await metersApi.delete(id);
        await fetchMeters();
      } catch (err) {
        console.error('Error deleting meter:', err);
        alert('Failed to delete meter. Please try again.');
      }
    }
  };

  if (loading) {
    return <div className="p-8 text-center">Loading meters...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-destructive">{error}</div>;
  }

  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex justify-between items-center">
            <span>All Meters</span>
            <Link to="/meters/new">
              <Button>Add New Meter</Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {meters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No meters found. Add your first meter!
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {meters.map((meter) => (
                <Card key={meter.id}>
                  <CardContent className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-semibold text-lg">{meter.label}</h3>
                        <p className="text-sm text-muted-foreground capitalize">
                          {meter.meter_type}
                        </p>
                      </div>
                      <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                        {meter.unit}
                      </span>
                    </div>
                    <div className="flex justify-between items-center mt-4">
                      <div className="text-xs text-muted-foreground">
                        Created: {new Date(meter.created_at).toLocaleDateString()}
                      </div>
                      <div className="flex gap-2">
                        <Link to={`/meters/${meter.id}`}>
                          <Button variant="outline" size="sm">
                            View
                          </Button>
                        </Link>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(meter.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default MeterList;