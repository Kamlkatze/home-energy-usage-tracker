import { Link } from 'react-router';
import { LogOut, User } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../hooks/useAuth';

// Header widget showing the logged-in user, a link to the profile page
// and the logout button.
export default function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2">
      <Link to="/profile">
        <Button variant="ghost" size="sm" className="gap-2">
          <User className="h-4 w-4" />
          {user.username}
        </Button>
      </Link>
      <Button variant="ghost" size="sm" className="gap-2" onClick={() => void logout()}>
        <LogOut className="h-4 w-4" />
        Abmelden
      </Button>
    </div>
  );
}