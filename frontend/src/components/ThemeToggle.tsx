import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { Button } from './ui/button';

const ThemeToggle: React.FC = () => {
  const [dark, setDark] = React.useState(() => {
    return (localStorage.getItem('theme') || 'dark') === 'dark';
  });

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
  };

  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label="Theme umschalten">
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
};

export default ThemeToggle;