import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ChevronDown } from 'lucide-react';
import { Button } from './ui/button';

interface NavDropdownItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

interface NavDropdownProps {
  label: string;
  items: NavDropdownItem[];
}

const NavDropdown: React.FC<NavDropdownProps> = ({ label, items }) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="gap-2"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        {label}
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </Button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1 min-w-44 rounded-md border bg-popover p-1 shadow-md"
        >
          {items.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              role="menuitem"
              className="flex items-center gap-2 rounded-sm px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
              onClick={() => setOpen(false)}
            >
              {item.icon}
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default NavDropdown;
