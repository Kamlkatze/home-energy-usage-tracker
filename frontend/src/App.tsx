import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Button } from './components/ui/button';
import HomePage from './pages/Home';
import MeterList from './pages/MeterList';
import MeterDetail from './pages/MeterDetail';
import MeterForm from './pages/MeterForm';
import AddReading from './pages/AddReading';
import TariffForm from './pages/TariffForm';
import TariffList from './pages/TariffList';
import AdvancePaymentList from './pages/AdvancePaymentList';
import AdvancePaymentForm from './pages/AdvancePaymentForm';
import YearsOverview from './pages/YearsOverview';
import YearDetail from './pages/YearDetail';
import CustomRange from './pages/CustomRange';
import BackupRestore from './pages/BackupRestore';
import { Home, BarChart2, FileText, Settings, Euro, CalendarDays, CalendarRange, DatabaseBackup } from 'lucide-react';
import ThemeToggle from './components/ThemeToggle';

const App: React.FC = () => {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="container mx-auto px-4 py-4">
            <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
              <div className="flex items-center gap-3">
                <BarChart2 className="h-6 w-6 text-primary" />
                <h1 className="text-2xl font-bold">Energy Tracker</h1>
              </div>
              <nav className="flex gap-2">
                <Link to="/">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <Home className="h-4 w-4" />
                    Home
                  </Button>
                </Link>
                <Link to="/years-overview">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <CalendarDays className="h-4 w-4" />
                    Jahresübersicht
                  </Button>
                </Link>
                <Link to="/custom-range">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <CalendarRange className="h-4 w-4" />
                    Zeitraum
                  </Button>
                </Link>
                <Link to="/readings/new">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <FileText className="h-4 w-4" />
                    Zählerstände
                  </Button>
                </Link>
                <Link to="/tariffs">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <Euro className="h-4 w-4" />
                    Tarife
                  </Button>
                </Link>
                <Link to="/advance-payments">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <Euro className="h-4 w-4" />
                    Abschläge
                  </Button>
                </Link>
                <Link to="/meters">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <Settings className="h-4 w-4" />
                    Zähler
                  </Button>
                </Link>
                <Link to="/backup-restore">
                  <Button variant="ghost" size="sm" className="gap-2">
                    <DatabaseBackup className="h-4 w-4" />
                    Backup/Restore
                  </Button>
                </Link>
                <ThemeToggle />
              </nav>
            </div>
          </div>
        </header>
        
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/meters" element={<MeterList />} />
            <Route path="/meters/new" element={<MeterForm />} />
            <Route path="/meters/:id" element={<MeterDetail />} />
            <Route path="/readings/new" element={<AddReading />} />
            <Route path="/tariffs" element={<TariffList />} />
            <Route path="/tariffs/new" element={<TariffForm />} />
            <Route path="/advance-payments" element={<AdvancePaymentList />} />
            <Route path="/advance-payments/new" element={<AdvancePaymentForm />} />
            <Route path="/years-overview" element={<YearsOverview />} />
            <Route path="/years/:year" element={<YearDetail />} />
            <Route path="/custom-range" element={<CustomRange />} />
            <Route path="/backup-restore" element={<BackupRestore />} />
          </Routes>
        </main>
        
        <footer className="border-t mt-8 py-6">
          <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
            <p>Home Energy Usage Tracker • Local deployment • No cloud services</p>
            <p className="mt-2">Data stays on your machine</p>
          </div>
        </footer>
      </div>
    </Router>
  );
};

export default App;