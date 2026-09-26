import { type ColumnSort } from '../hooks/useColumnSort';
import { cn } from '../lib/utils';
import { TableHead } from './ui/table';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

interface SortableHeaderProps {
  label: string;
  sortKey: string;
  sort: ColumnSort;
  onSort: (key: string) => void;
  className?: string;
}

export function SortableHeader({
  label,
  sortKey,
  sort,
  onSort,
  className,
}: SortableHeaderProps) {
  const active = sort.key === sortKey;
  const Icon = active ? (sort.dir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <TableHead className={className}>
      <button
        type="button"
        className={cn(
          'inline-flex items-center gap-1 align-middle font-medium transition-colors hover:text-foreground',
          active ? 'text-foreground' : 'text-muted-foreground'
        )}
        onClick={() => onSort(sortKey)}
        title={`Nach ${label} sortieren`}
      >
        {label}
        <Icon className={cn('h-3.5 w-3.5 shrink-0', !active && 'opacity-40')} />
      </button>
    </TableHead>
  );
}