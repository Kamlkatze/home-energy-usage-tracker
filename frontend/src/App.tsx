import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router';
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
import Login from './pages/Login';
import { Home, BarChart2, FileText, Settings, Euro, CalendarDays, CalendarRange, Receipt } from 'lucide-react';
import NavDropdown from './components/NavDropdown';
import ThemeToggle from './components/ThemeToggle';
import Footer from './components/Footer';
import RequireAuth from './components/RequireAuth';
import UserMenu from './components/UserMenu';
import { AuthProvider } from './context/AuthContext';

// Layout of the protected part of the app: header with navigation, the
// routed pages and the footer. Rendered inside <RequireAuth> so every
// business page requires an authenticated session.
const ProtectedLayout: React.FC = () => (
  <div className="min-h-screen bg-background">
    <header className="border-b">
      <div className="container mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-3">
            <BarChart2 className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Home Energy Usage Tracker</h1>
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
            <NavDropdown
              label="Erfassung"
              items={[
                { to: '/readings/new', label: 'Zählerstände', icon: <FileText className="h-4 w-4" /> },
              ]}
            />
            <NavDropdown
              label="Verwaltung"
              items={[
                { to: '/tariffs', label: 'Tarife', icon: <Euro className="h-4 w-4" /> },
                { to: '/advance-payments', label: 'Abschläge', icon: <Receipt className="h-4 w-4" /> },
                { to: '/meters', label: 'Zähler', icon: <Settings className="h-4 w-4" /> },
              ]}
            />
            <ThemeToggle />
            <UserMenu />
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

    <Footer />
  </div>
);

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="*"
            element={
              <RequireAuth>
                <ProtectedLayout />
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </Router>
  );
};

export default App;