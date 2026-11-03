import { LogOut } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../hooks/useAuth';

// Header widget showing the logged-in user and the logout button.
export default function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground" data-testid="header-username">
        {user.username}
      </span>
      <Button variant="ghost" size="sm" className="gap-2" onClick={() => void logout()}>
        <LogOut className="h-4 w-4" />
        Abmelden
      </Button>
    </div>
  );
}