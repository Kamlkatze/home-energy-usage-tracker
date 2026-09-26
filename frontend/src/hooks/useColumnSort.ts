import { useState } from 'react';

export type SortDir = 'asc' | 'desc';

export interface ColumnSort {
  key: string;
  dir: SortDir;
}

export function useColumnSort(initialKey: string, initialDir: SortDir = 'desc') {
  const [sort, setSort] = useState<ColumnSort>({ key: initialKey, dir: initialDir });

  const toggleSort = (key: string) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'desc' }
    );

  return { sort, toggleSort };
}

export function sortRows<T>(
  rows: T[],
  sort: ColumnSort,
  getValue: (row: T, key: string) => string | number | null,
): T[] {
  return [...rows].sort((a, b) => {
    const va = getValue(a, sort.key);
    const vb = getValue(b, sort.key);
    let cmp: number;
    if (va === null && vb === null) cmp = 0;
    else if (va === null) cmp = 1;
    else if (vb === null) cmp = -1;
    else if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb;
    else if (typeof va === 'number') cmp = -1;
    else if (typeof vb === 'number') cmp = 1;
    else cmp = String(va).localeCompare(String(vb));
    return sort.dir === 'asc' ? cmp : -cmp;
  });
}