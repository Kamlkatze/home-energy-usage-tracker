import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { sortRows, useColumnSort, type SortDir } from '../hooks/useColumnSort';

interface Row {
  name: string;
  value: number | null;
}

const ROWS: Row[] = [
  { name: 'beta', value: 10 },
  { name: 'alpha', value: 5 },
  { name: 'gamma', value: null },
  { name: 'delta', value: 5 },
];

// Mirrors how the sortable list pages extract the value for a column key:
// dates/strings via the key directly, amounts via parseFloat (here: numbers).
const getValue = (row: Row, key: string): string | number | null =>
  key === 'name' ? row.name : row.value;

describe('sortRows', () => {
  it('sorts rows by a numeric key in ascending order with nulls last', () => {
    const result = sortRows(ROWS, { key: 'value', dir: 'asc' }, getValue);
    expect(result.map((row) => row.name)).toEqual([
      'alpha',
      'delta',
      'beta',
      'gamma',
    ]);
  });

  it('sorts rows by a numeric key in descending order (nulls first in desc)', () => {
    const result = sortRows(ROWS, { key: 'value', dir: 'desc' }, getValue);
    // With dir 'desc' the comparator is negated, which flips the null-last
    // ordering into null-first. Documented here so a change is intentional.
    expect(result.map((row) => row.name)).toEqual([
      'gamma',
      'beta',
      'alpha',
      'delta',
    ]);
  });

  it('sorts rows by a string key in ascending order', () => {
    const result = sortRows(ROWS, { key: 'name', dir: 'asc' }, getValue);
    expect(result.map((row) => row.name)).toEqual([
      'alpha',
      'beta',
      'delta',
      'gamma',
    ]);
  });

  it('sorts rows by a string key in descending order', () => {
    const result = sortRows(ROWS, { key: 'name', dir: 'desc' }, getValue);
    expect(result.map((row) => row.name)).toEqual([
      'gamma',
      'delta',
      'beta',
      'alpha',
    ]);
  });

  it('places numbers before strings for a mixed-type column in ascending order', () => {
    const mixed: Array<{ id: string; value: number | string | null }> = [
      { id: 'c', value: 'hello' },
      { id: 'a', value: 42 },
      { id: 'b', value: null },
    ];
    const getMixed = (row: { value: number | string | null }, key: string) =>
      row[key as keyof typeof row] as string | number | null;

    const result = sortRows(
      mixed,
      { key: 'value', dir: 'asc' },
      getMixed,
    );
    expect(result.map((row) => row.id)).toEqual(['a', 'c', 'b']);
  });

  it('does not mutate the input array', () => {
    const input = [...ROWS];
    sortRows(input, { key: 'value', dir: 'asc' }, getValue);
    expect(input.map((row) => row.name)).toEqual([
      'beta',
      'alpha',
      'gamma',
      'delta',
    ]);
  });

  it('treats two null values as equal and keeps their relative order', () => {
    const input: Row[] = [
      { name: 'a', value: null },
      { name: 'b', value: null },
    ];
    const result = sortRows(input, { key: 'value', dir: 'asc' }, getValue);
    expect(result.map((row) => row.name)).toEqual(['a', 'b']);
  });

  it('sorts a non-null value before a null value', () => {
    const input: Row[] = [
      { name: 'a', value: null },
      { name: 'b', value: 1 },
    ];
    const result = sortRows(input, { key: 'value', dir: 'asc' }, getValue);
    expect(result.map((row) => row.name)).toEqual(['b', 'a']);
  });

  it('sorts a number before a string', () => {
    const input: Array<{ id: string; value: number | string }> = [
      { id: 'n', value: 42 },
      { id: 's', value: 'hello' },
    ];
    const getMixed = (row: { value: number | string }, key: string) =>
      row[key as keyof typeof row] as string | number;

    const result = sortRows(input, { key: 'value', dir: 'asc' }, getMixed);
    expect(result.map((row) => row.id)).toEqual(['n', 's']);
  });

  it('returns an empty array for an empty input', () => {
    expect(sortRows([], { key: 'value', dir: 'asc' }, getValue)).toEqual([]);
  });

  it('returns a single-element array unchanged', () => {
    const single = [{ name: 'alpha', value: 5 }];
    expect(
      sortRows(single, { key: 'value', dir: 'asc' }, getValue).map(
        (row) => row.name,
      ),
    ).toEqual(['alpha']);
  });
});

describe('useColumnSort', () => {
  it('initialises with the given key and a default descending direction', () => {
    const { result } = renderHook(() => useColumnSort('valid_from'));
    expect(result.current.sort).toEqual({ key: 'valid_from', dir: 'desc' });
  });

  it('initialises with an explicit direction', () => {
    const { result } = renderHook(() => useColumnSort('valid_from', 'asc'));
    expect(result.current.sort).toEqual({ key: 'valid_from', dir: 'asc' });
  });

  it('toggles the direction when toggling the same column', () => {
    const { result } = renderHook(() => useColumnSort('valid_from'));

    act(() => result.current.toggleSort('valid_from'));
    expect(result.current.sort).toEqual({ key: 'valid_from', dir: 'asc' });

    act(() => result.current.toggleSort('valid_from'));
    expect(result.current.sort).toEqual({ key: 'valid_from', dir: 'desc' });
  });

  it('switches to a new column and resets the direction to descending', () => {
    const { result } = renderHook(() => useColumnSort('valid_from'));

    act(() => result.current.toggleSort('valid_from'));
    expect(result.current.sort).toEqual({ key: 'valid_from', dir: 'asc' });

    act(() => result.current.toggleSort('price_per_unit'));
    expect(result.current.sort).toEqual({
      key: 'price_per_unit',
      dir: 'desc' as SortDir,
    });
  });
});
