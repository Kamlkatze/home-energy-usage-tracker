import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Home, Zap, Droplets, Flame } from 'lucide-react';

const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-secondary/20">
      <div className="container mx-auto px-4 py-12">
        <Card className="mb-8">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Home className="h-8 w-8 text-primary" />
              <div>
                <CardTitle className="text-3xl">Home Energy Usage Tracker</CardTitle>
                <CardDescription>
                  Track your electricity, gas, and water consumption with ease
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-6">
              Monitor your household energy usage, record meter readings, and visualize consumption trends over time.
              Simple, local, and privacy-focused.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <Zap className="h-8 w-8 text-blue-500" />
                    <h3 className="font-semibold text-lg">Electricity</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Track your electricity consumption in kWh, monitor usage patterns, and record monthly readings.
                  </p>
                </CardContent>
              </Card>
              
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <Flame className="h-8 w-8 text-orange-500" />
                    <h3 className="font-semibold text-lg">Gas</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Monitor gas usage in m³, record meter readings, and track consumption for heating and cooking.
                  </p>
                </CardContent>
              </Card>
              
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <Droplets className="h-8 w-8 text-cyan-500" />
                    <h3 className="font-semibold text-lg">Water</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Track water consumption in m³, monitor usage patterns, and identify potential leaks or waste.
                  </p>
                </CardContent>
              </Card>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Link to="/meters" className="w-full">
                <Button size="lg" className="w-full">
                  View All Meters
                </Button>
              </Link>
              <Link to="/readings/new" className="w-full">
                <Button variant="outline" size="lg" className="w-full">
                  Add New Reading
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
        
        <div className="text-center text-sm text-muted-foreground">
          <p>This application runs locally on your machine. No cloud services, no data sharing.</p>
        </div>
      </div>
    </div>
  );
};

export default HomePage;