import React from 'react';
import { Link } from 'react-router';
import { Card, CardContent } from '../components/ui/card';
import { Zap, Droplets, Flame, Gauge, FileText, CalendarDays, CalendarRange, Euro, Receipt, ArrowRight } from 'lucide-react';

const HomePage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      <Card className="mb-8">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Zap className="h-8 w-8 text-blue-500" />
                  <h3 className="font-semibold text-lg">Strom</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  Erfasse Bezug, Einspeisung und Erzeugung in kWh und überwache deine Verbrauchsmuster.
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
                  Erfasse deinen Gasverbrauch in m³ – mit Umrechnung in kWh für die Kostenberechnung.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Droplets className="h-8 w-8 text-cyan-500" />
                  <h3 className="font-semibold text-lg">Wasser</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  Verfolge Kalt- und Gartenwasserverbrauch in m³ inklusive Abwasserberechnung.
                </p>
              </CardContent>
            </Card>
          </div>

          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Auswertung
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <Link to="/years-overview" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <CalendarDays className="h-6 w-6 text-purple-500" />
                    <h3 className="font-semibold">Jahresübersicht</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Verbrauch und Kosten pro Jahr im Überblick
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>

            <Link to="/custom-range" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <CalendarRange className="h-6 w-6 text-teal-500" />
                    <h3 className="font-semibold">Zeitraum</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Verbrauch und Kosten in einem individuellen Zeitraum im Überblick
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          </div>

          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Erfassung
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <Link to="/readings/new" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <FileText className="h-6 w-6 text-green-500" />
                    <h3 className="font-semibold">Zählerstände</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Gib neue Zählerstände für alle Zähler ein
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          </div>

          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Verwaltung
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <Link to="/meters" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <Gauge className="h-6 w-6 text-blue-500" />
                    <h3 className="font-semibold">Zähler</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Verwalte deine Strom-, Gas- und Wasserzähler
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>

            <Link to="/tariffs" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <Euro className="h-6 w-6 text-amber-500" />
                    <h3 className="font-semibold">Tarife</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Verwalte Tarife, Grundgebühren und Einspeisevergütungen
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>

            <Link to="/advance-payments" className="group">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <Receipt className="h-6 w-6 text-rose-500" />
                    <h3 className="font-semibold">Abschläge</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Verwalte monatliche Abschlagszahlungen
                  </p>
                  <span className="text-sm text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Öffnen <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default HomePage;