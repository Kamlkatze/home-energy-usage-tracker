# Frontend Agent Instructions

Applies to everything under `frontend/`, **in addition to** the root `AGENTS.md`
(hard rules, commands, workflow, Docker/infra learnings).

## Layout & stack

- React 19 + TypeScript + Vite; Tailwind + shadcn-style primitives in `src/components/ui/`
- API client/hooks in `src/hooks/`, pages in `src/pages/`
- Prod image: `frontend/Dockerfile` (multi-stage, served by nginx); dev image: `frontend/Dockerfile.dev`
- API base URL: production uses `/api` (nginx proxy), development uses `http://backend:8000`
- Money/quantity values arrive from the API as **Decimal strings in JSON** – keep them as strings
  in TS types and format only for display (UI strings in German, see root AGENTS.md)

## Data fetching (React 19 + useFetch)

- All page data fetching goes through `src/hooks/useFetch.ts`
  (`useFetch<T>(fetchFn, deps) => {data, loading, error}`)
- React 19 lint rules (`eslint-plugin-react-hooks@7`) require: `setState` only in Promise callbacks
  (never sync in effect bodies; loading-reset via microtask), fetchFn ref written inside effects,
  no render-phase ref writes, no `Date.now()`/impure calls in render (use module-level constants)
- Dialog/modal form state: initialise via **keyed inner component remount**
  (`<InnerForm key={item.id}/>`) instead of setState-in-effect; preselect/defaults via render-time
  derivation (defaults + override state)
- Refetch after mutations: bump a `reloadKey` state passed in deps
- Details in `frontend/README.md` section 11

## Sortable / searchable tables

- Reuse the shared building blocks instead of reimplementing per page:
  `hooks/useColumnSort.ts` (`useColumnSort` + pure `sortRows`) and
  `components/SortableHeader.tsx` / `components/TableSearch.tsx` (used by `TariffList`
  and `AdvancePaymentList`).
- `SortableHeader` renders a real `<button type="button">` (a11y rule: no clickable
  `<th>` without a button); pass the active sort via `sort={{ key, dir }}` and add an
  arrow icon (`ArrowUp`/`ArrowDown` when active, dimmed `ArrowUpDown` otherwise).
- `getValue(row, key)` must return `string | number | null` (dates as `YYYY-MM-DD`
  string, amounts via `parseFloat`) so `sortRows` compares never-mixed types; `null`
  sorts last.
- Default sort convention (user-facing): **newest / currently valid first** —
  `valid_from` descending. UIs that display validity periods show them as **two
  separate columns** ("Gültig von" / "Gültig bis"), each independently sortable, and
  keep the meter column leftmost. Example: both `/tariffs` and `/advance-payments`.
- Free-text search matches the human-readable fields (meter label/number, comment,
  category/kind label), lowercased, via `haystack.includes(query)`.

## Charts (Recharts 2.15)

- A separate `<Line data={projectionData}>` only creates tooltip hit targets at points of the
  primary `data` array passed to `<LineChart>`. Fix: merge all points into `combinedData` and use
  `dataKey="projectedValue"` on the projection Line instead of a separate `data` prop
  (main Line: `dataKey="value"`)
- Custom tooltip components must be defined at **module level** (not inside the render function) to
  avoid reference changes that make Recharts lose tooltip state. Pass dynamic values like `unit`
  as props: `<Tooltip content={<ChartTooltip unit={unit} />} />`
- Dark-mode styling: XAxis/YAxis need explicit `stroke="hsl(var(--muted-foreground))"` and
  `tick={{ fill: 'hsl(var(--muted-foreground))' }}`; Tooltip uses `background: hsl(var(--popover))`,
  `color: hsl(var(--popover-foreground))`, `border: 1px solid hsl(var(--border))`; YAxis
  `tickFormatter` for integer ticks: `(v) => Math.round(v).toString()`
- Known **pre-existing** dev-only warning `Each child in a list should have a unique "key" prop …
  from Line` (React 19 + recharts 2.15, Recharts-internal ForwardRef): reproduced with old page
  code – do not chase as a regression; recharts 3.x would be the real fix

## Formatting & lint conventions

- Unit-aware formatting: kWh displays as integers (`Math.round`), m³ with decimals (`toFixed(1)`) –
  applies to consumption/projection cards, EEG kWh (hardcoded `toFixed(0)`), readings table,
  YearsOverview; helpers `formatConsumption(value, unit)` / `formatReadingValue(value, unit)` in
  `YearDetail.tsx`
- `jsx-a11y`: prefer a **semantic fix** (e.g. clickable non-interactive `<div>` → real
  `<button type="button">`, as done for the dialog backdrop in `src/components/ui/dialog.tsx`).
  For shared shadcn-style `forwardRef` primitives where the property is only verifiable at the
  call site, that's a known false positive – silence with a single inline
  `// eslint-disable-next-line jsx-a11y/<rule>` plus a one-line comment (see `card.tsx`,
  `label.tsx`). Never add these rules to a global ignore file. Baseline: 0 `jsx-a11y` warnings in
  `src/`
- ESLint 9 flat config (`eslint.config.js`); `npm run lint` exits 1 if any warning – target is
  **0 errors**, 38 known warnings
- TS build hygiene: keep `src/vite-env.d.ts` present; don't leave unused deps (removed
  `@radix-ui/react-slot`)

## Dependencies & containers

- `Dockerfile{,.dev}` run `npm ci` with **strict peer resolution** – local
  `npm install --legacy-peer-deps` masks peer conflicts and previously broke both image builds
  after the React 19 bump (`lucide-react@0.303` peer ≤ React 18 → ERESOLVE). Never "fix" by adding
  `--legacy-peer-deps` to the Dockerfile; upgrade the offending dependency instead (lucide-react
  ^1.47 supports React 19, icon exports unchanged). After any dependency major bump, verify with
  `npm ci` in a scratch copy of package.json+lock before `docker compose build`
- `@testing-library/react@16` needs `@testing-library/dom` as an **explicit** devDependency under
  such installs
- Dev-container crash `Cannot find package 'vitest' imported from /app/vite.config.ts` (:3000 dead,
  host dev works): the dev compose mounts `./frontend:/app` with `/app/node_modules` as an
  **anonymous volume that podman-compose reuses forever** – not refreshed by `--build` or `up`, so
  it kept a pre-Vitest snapshot. Fixed: (a) `vite.config.ts` must not **runtime-import** vitest –
  use `defineConfig` from `'vite'` + `/// <reference types="vitest/config" />` (types only);
  (b) `Dockerfile.dev` CMD self-heals: runs `npm ci` when `node_modules` is missing or
  `package-lock.json` is newer than `node_modules/.package-lock.json`. Prod is unaffected (fresh
  multi-stage `npm ci` build, no node_modules mount). Don't "fix" port issues by remapping ports –
  `curl localhost:3000` returning 000/refused can mean the vite container simply exited
- SIGTERM handling: `exec` for nginx and npm commands in the Dockerfiles ensures clean shutdown
