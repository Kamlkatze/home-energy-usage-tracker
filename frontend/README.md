# Home Energy Usage Tracker – Frontend

## 1. Tech Stack (actual, verified)

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | React | ^19.3.0 | SPA, no SSR/Next.js; upgraded from 18.2.0 on Sept 22, 2026 (see section 11) |
| Build tool | Vite | ^7.3.6 | + `@vitejs/plugin-react` |
| Language | TypeScript | ^5.9.3 | strict mode via tsconfig |
| Routing | react-router-dom | ^6.20.1 | `<BrowserRouter>` with `<Routes>`; `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}` enables the v7 opt-in flags and silences the v7 deprecation warnings (also set on the test `MemoryRouter`s) |
| HTTP client | axios | ^1.6.0 | single `apiClient` instance |
| Charting | recharts | ^2.10.0 | `LineChart` on meter detail page |
| Icons | lucide-react | ^1.47.0 | used in nav, home cards, forms; upgraded from 0.303.0 for React 19 peer support (all previously used icon exports still exist) |
| Date utils | – | – | not used (`date-fns` was removed in "Removed unused imports and dead code from frontend") |
| CSS | Tailwind CSS | ^3.3.6 | with `tailwindcss-animate`, `postcss` + `autoprefixer` |
| UI primitives | shadcn/ui style | – | hand-written, not installed via CLI (button, card, checkbox, input, label, select, table, textarea) |
| Utility | class-variance-authority | ^0.7.0 | used in button variants |
| Utility | clsx + tailwind-merge | ^2.0.0 | `cn()` helper in `lib/utils.ts` |
| Linting | ESLint | ^9.39.5 (flat config `eslint.config.js`) | Uses `@eslint/js`, `typescript-eslint`, `eslint-plugin-react`, `react-hooks@7.x`, `react-refresh`, `jsx-a11y`; no Prettier; see **ESLint React Hooks Status** below |
| Testing | Vitest | ^3.2.7 | + `@testing-library/react` ^16 (with explicit peer `@testing-library/dom` ^10) + `jsdom` 30+; smoke tests only (see section 8) |

**Not used:** no date utility library is installed.

## 2. Existing Pages / Routes

| Route | File | Description |
|---|---|---|
| `/` | `pages/Home.tsx` | Landing page with description cards (electricity, gas, water) and nav links. Static content only – no live data or summary queries. |
| `/meters` | `pages/MeterList.tsx` | Lists all meters in a card grid. Shows label, type, unit, predecessor/successor chain. Supports **edit** (inline modal) and **delete** (Dialog with confirmation). "Neuer Zähler" link. German UI. |
| `/meters/new` | `pages/MeterForm.tsx` | Create meter form: label, meter number (optional), type (select from server‑fetched types), predecessor (optional, same‑type only). Unit is read-only (server-derived). Submits to `POST /api/meters/`. |
| `/meters/:id` | `pages/MeterDetail.tsx` | Single meter detail: line chart of readings (recharts), meter info panel (type, unit, number, created date, total count), recent readings table (last 5, newest first). Fetches `GET /api/meters/:id` + `GET /api/meters/:id/readings`. |
| `/readings/new` | `pages/AddReading.tsx` | Multi-meter reading entry form: single date for all meters, per-meter checkbox + value + optional note + last-reading reference. Shows all meters (replaced ones hidden by default) via `GET /api/meters/` with an "Alte Zähler anzeigen" toggle. Replaced meters are visually marked with an `(ersetzt)` badge and amber border. Checkbox selection persisted in localStorage. Submits `POST /api/readings/` per selected meter with value. Shows success/partial-failure results with ✅/❌ per meter. |
| `/tariffs` | `pages/TariffList.tsx` | Tariff overview table with all periods: kind label, meter, valid-from/until, price, base fee, metering fee (monthly or yearly), gas factors, optional comment, **comment** column. Category filter buttons (Strom Bezug/Gas/Wasser) above the table — the "Strom Erzeugung" type is excluded. **Sortable columns** (click any header to sort asc/desc) + **free-text search** (matches meter label/number, provider/comment, tariff kind); default order groups by meter, then newest `valid_from` first, until a column is clicked. Supports **edit** (inline modal with dynamic tariff-kind fields, optional comment editable) and **delete** (with usage check). |
| `/tariffs/new` | `pages/TariffForm.tsx` | Create tariff period form: meter selector, tariff kind (consumption/feed_in/self_consumption/wastewater/feed_in_eeg2009), validity range, dynamic fields per kind (price per unit, optional base + metering fees, gas Z-Zahl/Brennwert for gas meters, EEG 2009 block with tier rates + yearly metering fee), optional comment field. German labels/helper text throughout. EEG 2009 meter selection includes a hint to pick the feed-in meter. Handles empty meter list gracefully. |
| `/advance-payments` | `pages/AdvancePaymentList.tsx` | Advance payment overview with 5 filter buttons (Alle/Gas/Kaltwasser/Abwasser/Strom Bezug). Per-filter table: assigned meter(s), valid-from/until (two separate columns), monthly amount, **comment** column. Default sort is **newest `valid_from` first** (like tariffs); **sortable columns** (meter, valid-from/until, monthly amount, comment) + **free-text search** (matches meter label, provider/comment, category). Supports **edit** via inline modal (validity period + monthly amount + optional comment, meter relations read-only). |
| `/advance-payments/new` | `pages/AdvancePaymentForm.tsx` | Create advance payment form: category selector (4 values), dynamic meter dropdowns per category (gas → gas meter, cold_water → water_cold meter, power_import → electricity_import meter, wastewater → required water_cold + optional water_garden meter), validity range, monthly amount, optional comment. Submits to `POST /api/advance-payments/` with correct payload per category. Shows backend 422 errors. |
| `/years-overview` | `pages/YearsOverview.tsx` | Year-over-year consumption table + separate line charts per energy type (Strom, Wasser, Gas) for all logical meters (chain-resolved via backend). m³/water values are shown with one decimal (`toFixed(1)`) in both the table cells and the chart tooltip; kWh values are rounded to integers. Years link to `/years/:year`. |
| `/years/:year` | `pages/YearDetail.tsx` | Year detail page grouped by category (Strom, Wasser, Gas). **Strom** uses MeterBlock per meter + EEG-Einspeisevergütung card (total broken down into gross compensation and the deducted metering point fee). **Wasser** uses combined WaterSection (consumption strip, dual-line chart, paired comparison grids for Frischwasser + Abwasser). **Gas** uses GasSection (consumption strip, chart, readings table, comparison grid per meter). Readings are editable/deletable via inline dialog in all tables. |
| `/custom-range` | `pages/CustomRange.tsx` | Custom time-range analysis: from/to date inputs (default: current year, via module-level constants) + meter-type toggles (Strom/Wasser/Gas). Fetches `GET /api/costs/consumption-timeseries` — one unfiltered request when all three types are active, otherwise one parallel request per type — and renders one card per active area (`AreaBlock`) with a combined multi-line chart (consumption between readings, no projections) and **one table per meter** laid out side-by-side (grid: Datum/Zählerstand/"Verbrauch seit letzter Ablesung"). The cost column header is **"Vergütung seit letzter Ablesung"** for Einspeisung/Erzeugung meters and **"Kosten seit letzter Ablesung"** otherwise; for cost meters each value shows a second line with the breakdown Arbeitspreis / Grundpreis / Messstellenbetrieb (`energy_cost_since_previous` / `base_fee_since_previous` / `metering_fee_since_previous`), and Einspeisung/Erzeugung without a pure `feed_in` tariff renders "-" instead of the "—" used for missing data. When production + export meters exist and Strom is active, a **"EEG-Einspeisevergütung (EEG 2009)"** summary card shows the period total via `GET /api/electricity/feed-in-compensation` (range-based, requires a `feed_in_eeg2009` tariff on the export meter), with the total broken down into gross compensation and the deducted metering point fee. Quick-select buttons ("1 Monat", "3 Monate", "6 Monate", "Jahr"), "Anwenden" applies the entered range, plus loading/error/empty states. |

**Chart implementation notes (MeterBlock):**
- **Projection line via `combinedData`:** Dashed projection does NOT use separate `<Line data={...}>` – Recharts only creates tooltip hit targets in the primary `data` array. All points are merged into `combinedData`: main Line uses `dataKey="value"`, projection Line uses `dataKey="projectedValue"`. End-of-year point carries `value: undefined` (invisible) and `isProjectionEnd: true`.
- **Consumption mode toggle ("seit 01.01."):** New in this iteration. Each chart (MeterBlock, GasMeterView, WaterSection combined chart) has a toggle button to switch between absolute meter readings and cumulative consumption since Jan 1. In consumption mode, every reading value is offset by `start_reading_value` (from the projection response) — the chart starts at 0 and the Y-axis lower bound is fixed at 0. Projection line uses `projected_annual_consumption` instead of `projected_meter_reading_end_of_year`. Default is consumption mode (`useState(true)`).
- **Nice Y-axis bounds:** New helper `niceAxisBounds()` in `components/shared/chartHelpers.ts` (extracted from `year-detail/utils.ts`) computes data-min/max → even-number axis bounds with a constant step (2, 4, 10, 20, 40, 100, …). The lower bound is never negative. Replaces the old 10 % dynamic padding approach.
- **Custom tooltip `ChartTooltip`** (`components/shared/ChartTooltip.tsx`, module level): dark-mode via `hsl(var(--popover))` / `hsl(var(--popover-foreground))`. "Hochrechnung" only rendered when hovered point is in the future. Values formatted unit-aware: kWh → `Math.round()`, m³ → `toFixed(1)`. Used by MeterBlock, GasSection, WaterSection, and the custom-range AreaBlock (unit passed via props).
- **Dark-mode axes:** explicit `stroke`/`tick.fill` using `hsl(var(--muted-foreground))`. YAxis tick values rounded to whole numbers.
- **Unit-aware formatting:** kWh → integers (`Math.round`), m³ → one decimal (`toFixed(1)`). EEG kWh → `toFixed(0)`. Same in `YearsOverview.tsx`.

**YearsOverview chart split:** The years-overview page shows three separate `ChartCard` components (Strom, Wasser, Gas) instead of a single combined chart. Each card uses the same `ChartTooltip`, dark-mode styling, and unit-aware formatting. Meters are grouped by `meter_type` using `ELECTRIC_TYPES` (electricity_import, electricity_export, electricity_production) and `WATER_TYPES` (water_cold, water_garden). The X-axis is sorted ascending (oldest year first).

## 3. Existing Components

### Reusable UI primitives (`components/ui/`)
All follow the shadcn/ui pattern (Tailwind + `cn()` helper, forwardRef, displayName):

| Component | File | Notes |
|---|---|---|
| `Button` | `button.tsx` | 6 variants (default, destructive, outline, secondary, ghost, link), 4 sizes (default, sm, lg, icon). Uses `cva`. |
| `Card` / `CardHeader` / `CardTitle` / `CardDescription` / `CardContent` / `CardFooter` | `card.tsx` | Standard card composition. |
| `Input` | `input.tsx` | Wraps `<input>` with base styling. |
| `Label` | `label.tsx` | Wraps `<label>` with base styling. |
| `Select` / `SelectItem` | `select.tsx` | Custom native `<select>` wrapper with chevron icon. |
| `Table` / `TableHeader` / `TableBody` / `TableFooter` / `TableHead` / `TableRow` / `TableCell` / `TableCaption` | `table.tsx` | Full shadcn-style table suite. |
| `Checkbox` | `checkbox.tsx` | Simple `<input type="checkbox">` wrapper with Tailwind styling, following shadcn/ui pattern with forwardRef and `cn()`. |

### Business components (`components/`)
| Component | File | Notes |
|---|---|---|
| `EditMeterModal` | `EditMeterModal.tsx` | Dialog for editing a meter: name, number, predecessor dropdown. Meter type and unit are read-only. The predecessor dropdown only lists same-type meters and excludes the meter itself (a meter can never be its own predecessor); it keeps the currently selected predecessor selectable. |
| `ThemeToggle` | `ThemeToggle.tsx` | Dark/light mode toggle button in nav bar. Stores preference in `localStorage.theme`. |
| `SortableHeader` | `SortableHeader.tsx` | Reusable sortable table header. Renders a real `<button>` (a11y-friendly) with an arrow indicator (↑/↓ when active, dimmed ↑↓ otherwise). Props: `label`, `sortKey`, `sort`, `onSort`. Used by `TariffList` and `AdvancePaymentList`. |
| `TableSearch` | `TableSearch.tsx` | Reusable free-text search `Input` with a search icon and an X to clear (`aria-label="Suche zurücksetzen"`). Props: `value`, `onChange`, `placeholder`. Used by `TariffList` and `AdvancePaymentList`. |

#### Year Detail (`components/year-detail/`)
| Module | Description |
|---|---|
| `types.ts` | Shared interfaces: `MeterSection`, `AdvancePaymentDiffs` |
| `utils.ts` | Helper: `basisLabel()` (formatting/axis helpers were extracted to `components/shared/chartHelpers.ts`) |
| `MeterBlock.tsx` | Single meter card: chart, readings table with edit/delete buttons, projection. Contains all Recharts logic (combinedData, ChartTooltip, dark-mode styling, unit-aware formatting). |
| `ElectricitySection.tsx` | Strom category: all electricity meters + EEG Einspeisevergütung card (with gross-compensation / metering-fee-deduction breakdown). |
| `WaterSection.tsx` | Wasser category: combined consumption strip (FW/GW/AW actual + projected), dual-line chart (Frischwasser + Gartenwasser with projections), paired 3×2 comparison grids (Frischwasser costs + Abwasserkosten with advance payment diffs), and separate Zählerstände tables for both Frischwasser and Gartenwasser with edit/delete buttons. No longer uses individual MeterBlocks. |
| `GasSection.tsx` | Gas section: separate consumption strip (Verbrauch tats./prog.), chart + readings table with edit/delete buttons per meter, and comparison grid (Kosten tats./prog. + Abschlagsdifferenz). |
| `ReadingEditDialog.tsx` | Reusable dialog for editing or deleting a single reading. Opens from pencil/trash icons in any readings table. Contains edit form (date, value, note) and delete confirmation view. Calls `readingsApi.update()` / `readingsApi.delete()`. |

#### Shared chart helpers (`components/shared/`)
| Module | Description |
|---|---|
| `chartHelpers.ts` | Shared chart/formatting helpers used by both `year-detail/` and `custom-range/`: `COLORS`, `formatEuro()`, `formatConsumption(value, unit)`, `formatReadingValue(value, unit)`, `niceAxisBounds()`. |
| `ChartTooltip.tsx` | Module-level Recharts tooltip (dark-mode styling, projection-line filtering for past dates, unit-aware value formatting). |

#### Custom Range (`components/custom-range/`)
| Module | Description |
|---|---|
| `AreaBlock.tsx` | One card per active area on the custom-range page: combined multi-line chart (one line per logical meter, `consumption_since_previous`, no projections) + a responsive grid of **one table per meter** (Datum/Zählerstand/"Verbrauch seit letzter Ablesung"); the cost column header is "Vergütung seit letzter Ablesung" for `electricity_export`/`electricity_production`, "Kosten seit letzter Ablesung" otherwise. Cost meters render the total plus a breakdown line (Arbeitspreis · Grundpreis · Messstellenbetrieb) via the local `CostCell`; Einspeisung/Erzeugung without a pure `feed_in` tariff show "-", missing data shows "—". Uses the shared ChartTooltip and helpers. |

### Hooks
| Hook | File | Notes |
|---|---|---|
| `useMeterTypes` | `hooks/useMeterTypes.ts` | Fetches meter types from `GET /api/meters/types` once per session (module-level cache). Returns `MeterTypeInfo[]`. Also exports `meterTypeLabel()` helper. |
| `useFetch` | `hooks/useFetch.ts` | Generic data-fetching hook used by **all 11 route pages**: `useFetch<T>(fetchFn, deps) => { data, loading, error }`. Auto-fetches on mount and whenever `deps` change. All state updates happen inside Promise callbacks (React 19 lint-compliant, no `set-state-in-effect` violations), stale/abandoned responses are ignored via an `active` flag, errors land in `error` (message string) and are logged centrally once via `console.error`. See section 11 for the rationale and usage patterns. |
| `useColumnSort` | `hooks/useColumnSort.ts` | Reusable sorting state for tables. `useColumnSort(initialKey, initialDir='desc') => { sort, toggleSort }` + the pure helper `sortRows(rows, sort, getValue)`. `getValue(row, key)` returns `string | number | null` per sort key (nulls sort last); dates are compared as strings (works for `YYYY-MM-DD`). Used by `TariffList` (manual override of a default composite sort) and `AdvancePaymentList` (default newest first). |

### Lib
| File | Description |
|---|---|
| `lib/tariffFields.ts` | Shared helper for tariff field visibility/labels per `TariffKind` and meter type. Exports `getTariffFields(kind, meterType, meterUnit)`, `getPriceUnitLabel(kind, meterType, meterUnit)`, `TARIFF_KIND_LABELS`, `TARIFF_KINDS`, and the `FieldConfig` interface. Used by both `TariffForm.tsx` and `TariffList.tsx`. |
| `lib/advancePaymentFields.ts` | Shared helper for advance payment category labels and meter field visibility. Exports `ADVANCE_PAYMENT_CATEGORY_LABELS`, `ADVANCE_PAYMENT_CATEGORIES`, `getMeterFieldsForCategory(category)` (returns which meter dropdowns to show per category), `filterMetersForCategory(meters, field)`. Used by both `AdvancePaymentForm.tsx` and `AdvancePaymentList.tsx`. |
| `lib/utils.ts` | `cn()` helper combining `clsx` and `tailwind-merge`. |

### Types (`types/index.ts`)
Defines: `MeterType`, `TariffKind`, `MeterTypeInfo`, `Meter`, `Reading`, `TariffPeriod` (incl. `comment`), `TariffUsage`, `AdvancePaymentCategory`, `AdvancePayment` (incl. `comment`), `YearEntry`, `YearsOverviewItem`, `YearlyProjection` (incl. `start_reading_value`, `start_reading_date`), `FeedInCompensation`, `WastewaterCosts`, `ConsumptionTimeseriesPoint`, `ConsumptionTimeseriesItem` (timeseries from `GET /api/costs/consumption-timeseries` — incl. `meter_label`, `meter_type`, `unit`, per-point `consumption_since_previous` / `cost_since_previous` plus the breakdown fields `base_fee_since_previous`, `metering_fee_since_previous`, `energy_cost_since_previous`) — aligned with backend schemas.

## 4. API Integration

- **Pattern:** Plain axios instance (`api/client.ts`) with module-level API objects (no React Query, no generated client, no custom fetch wrapper).
- **Base URL:** `import.meta.env.VITE_API_URL || ''` – empty string means same-origin, relying on the Vite dev proxy or nginx reverse proxy in production.
- **Dev proxy** (`vite.config.ts`): `/api` → `process.env.VITE_PROXY_TARGET` (falls back to `http://localhost:8000`). Containerized dev (`docker-compose.dev.yml`) sets `VITE_PROXY_TARGET: http://backend:8000` so the frontend container reaches the backend via its docker-compose service name; the backend mounts routes under `/api`, so the path is passed through without rewriting.

### API objects and endpoints consumed

| Object | Endpoints | Used in |
|---|---|---|
| `metersApi` | `GET /types`, `GET /`, `GET /current`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id`, `GET /:id/readings` | `useMeterTypes`, `MeterList`, `EditMeterModal`, `MeterDetail`, `MeterForm`, `AddReading` (uses `getAll` with toggle for replaced meters + `getLastReading`), `TariffForm`, `YearDetail` (chain resolution + readings fetch) |
| `readingsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `AddReading` (POST), `ReadingEditDialog` in `YearDetail` (PUT, DELETE) |
| `tariffsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `TariffForm` (POST), `TariffList` (GET, PUT, DELETE) |
| `advancePaymentsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `AdvancePaymentForm` (POST), `AdvancePaymentList` (GET, PUT) |
| `costsApi` | `GET /years-overview`, `GET /yearly-projection`, `GET /wastewater/`, `GET /advance-payment-diff-by-category`, `GET /consumption-timeseries` | `YearsOverview`, `YearDetail` (projections, wastewater + advance payment diffs), `CustomRange` (time series) |
| `electricityApi` | `GET /feed-in-compensation`, `GET /feed-in-compensation-projection` | `YearDetail` (EEG feed-in compensation) |

## 5. Styling Approach

- **Tailwind CSS** exclusively (no plain CSS files, no CSS modules, no styled-components).
- **shadcn/ui design tokens** via CSS custom properties in `index.css` (──background, --foreground, --primary, --border, --radius, etc.) with a `.dark` variant.
- **Component compositions:** All UI elements are `className`-styled with Tailwind utilities, composed via `cn()` from `lib/utils.ts`.
- **Theme:** Dark-first with user-toggleable light/dark mode via `.dark` class on `<html>` (toggle stored in `localStorage.theme`). An inline script in `index.html` applies the saved theme before React mounts to prevent flash of wrong theme.
- **Favicon:** Custom SVG (`public/favicon.svg`) — stylized house with lightning bolt on dark blue background.

## 6. Gaps vs. Backend

The following backend endpoints/features have **zero** frontend representation:

| Area | Backend endpoints missing from frontend |
|---|---|
| **Cost calculations** | `GET /api/costs/` (general), `/costs/advance-payment-diff` – no UI; `/costs/years-overview` ✅, `/costs/yearly-projection` ✅, `/costs/wastewater/` ✅ (implemented in `YearDetail`) |
| **Electricity: feed-in compensation** | `GET /api/electricity/feed-in-compensation` — ✅ implemented in `YearDetail` as part of Strom category |
| **Projections** | `GET /api/meters/{meter_id}/projection` – no UI (separate from `/costs/yearly-projection`) |
| **Consumption timeseries** | ✅ Implemented – `CustomRange` consumes `GET /api/costs/consumption-timeseries` (see `/custom-range` route above) |
| **Tariff list / edit / delete** | ✅ Implemented – see `/tariffs` route above |
| **Reading list / edit / delete** | ✅ Implemented – see year detail page tables |
| **Meter edit** | `PUT /api/meters/` via `EditMeterModal` in `MeterList` |
| **Advance payment list / create / edit** | ✅ Implemented – see `/advance-payments` and `/advance-payments/new` routes above |

## 7. Linting (ESLint)

- **Config:** Flat config `eslint.config.js` (ESLint 9, since the Sept 2026 toolchain upgrade — the old `.eslintrc.cjs` was removed). Plugins: `@eslint/js`, `typescript-eslint`, `react`, `react-hooks@7.x`, `react-refresh`, `jsx-a11y`.
- **Scripts:** `npm run lint` (fails on warnings via `--max-warnings 0`), `npm run lint:fix` (safe autofix only).
- **Rule philosophy:** Recommended sets for TS/React/React-hooks/jsx-a11y are enabled. Noisy/strict stylistic rules are relaxed (`explicit-module-boundary-types` off, `no-explicit-any` as warning, `react/prop-types` off since TypeScript validates). `jsx-a11y/recommended` rules are all set to **warn** (not error) so a11y issues don't block the build for a solo dev. There is **no Prettier** in this project.
- **No autofixer for `react/no-unescaped-entities`:** this rule is not auto-fixable, so `npm run lint:fix` cannot repair it — such occurrences must be escaped manually (e.g. `"` → `&quot;`) in JSX text.
- **Handling `jsx-a11y` warnings:** fix them in the order below, then confirm `npm run lint` is clean:
  1. **Prefer a semantic fix** when the element is genuinely misused (e.g. a clickable non-interactive `<div>` → a real `<button type="button">`, as done for the dialog backdrop). This is the durable solution and keeps the markup honest.
  2. **If the component is a shared primitive** (shadcn-style `forwardRef` that spreads `{...props}`) and the property can only be verified at the caller's site (heading content, label association), the warning is a known false positive. Silence it with a single `// eslint-disable-next-line jsx-a11y/<rule>, jsx-a11y/<rule>` placed immediately above the element, **always** with a one-line comment explaining why the association happens downstream.
  3. Do not add these rules to a global ignore file or downgrade them further — the explicit inline disable keeps the intent visible and the rest of the repo checked.

## 8. Tests (Vitest)

Vitest is the render-safety net for dependency migrations (Vite 7, React 19) — the smoke tests exist to detect *"the app no longer renders"*. In addition, a set of **focused component tests** (`src/test/*.test.tsx`) assert specific behaviours of key interactions (e.g. the meter-form predecessor filter and the YearsOverview m³ formatting), and **unit tests** (`src/test/*.test.ts`) cover the API layer (`client`, `advancePaymentsApi` — the global API mocks are disabled per file and the `axios` module is mocked instead, so the real client runs against a stubbed HTTP layer) and `useColumnSort`.

**Stack (current):** `vitest ^3.2.7`, `@vitest/ui ^3`, `@vitest/coverage-v8 ^3.2.7`, `@testing-library/react ^16` (+ explicit peer `@testing-library/dom ^10`), `@testing-library/jest-dom ^6`, `@testing-library/user-event ^14`, `jsdom ^30`. Note: `@testing-library/dom` must stay an explicit devDependency — `@testing-library/react` only declares it as a peer, and installs with `--legacy-peer-deps` (or `--omit=peer`) silently drop it.

**`vite.config.ts` rule:** type the `test` block with `/// <reference types="vitest/config" />` and import `defineConfig` from `'vite'` — never from `'vitest/config'`. The dev container runs vite from a persistent `node_modules` volume, and a runtime import of vitest makes the whole dev server crash at config load if that volume predates Vitest (see AGENTS.md learning 30). `Dockerfile.dev` mitigates this by running `npm ci` on start whenever `node_modules` is missing or `package-lock.json` is newer than the install marker.

**Config:** Lives in the `test` block of `vite.config.ts` (no separate `vitest.config.ts`): `environment: 'jsdom'`, `globals: true`, `setupFiles: ['./src/test/setup.ts']`, `css: false`.

### Commands

| Command | What it does |
|---|---|
| `npm run test` | Run the full suite once (CI-friendly). |
| `npm run test:coverage` | Run the full suite once with V8 code coverage; prints a `text` summary and writes an interactive HTML report to `coverage/`. |
| `npm run test:watch` | Watch mode, re-runs on file changes. |
| `npm run test:ui` | Interactive browser UI (via `@vitest/ui`). |

Currently: **128 tests, all green** — 14 smoke tests across `src/test/smoke/` (one per top-level route component), 49 focused component tests in `src/test/*.test.tsx` (AddReading, EditMeterModal, MeterForm, TariffForm, YearDetail, YearsOverview), and 65 unit tests for the API layer and hooks in `src/test/*.test.ts` (client, advancePaymentsApi, useColumnSort).

**Coverage (Sept 27 2026):** overall **72.1 % statements/lines**, **74.2 % branches**, **53.1 % functions** (`@vitest/coverage-v8`, provider `v8`). Configured in the `test.coverage` block of `vite.config.ts` — `reporter: ['text', 'html']`, report written to `coverage/`. Excluded from the report: `src/test/`, `*.test.*`, `*.d.ts`, `src/main.tsx` (entry point), `src/vite-env.d.ts`, `dist/`, and config files (`vite.config.ts`, `tailwind.config.*`, `postcss.config.*`, `eslint.config.*`). `src/api/client.ts`, `src/api/advancePaymentsApi.ts` and `src/hooks/useColumnSort.ts` are at **100 %** across all metrics; the remaining gaps are page/component rendering logic that is only smoke-tested.

### How the suite is organised

```
src/test/
├── setup.ts          # jest-dom matchers + global API mocks (+ per-test reset)
├── mocks/
│   └── api.ts        # mock implementations of all API client objects
├── utils.tsx         # renderWithProviders() helper
├── *.test.ts(x)      # focused component tests + unit tests for API layer/hooks
│                     #   (AddReading, EditMeterModal, MeterForm, TariffForm,
│                     #   YearDetail, YearsOverview; client, advancePaymentsApi,
│                     #   useColumnSort)
└── smoke/            # one *.test.tsx per route component
```

- **`setup.ts`** imports `@testing-library/jest-dom/vitest` and registers `vi.mock(...)` for `src/api/client` and `src/api/advancePaymentsApi` **globally**, so no route component ever hits the network. A global `beforeEach` resets every mock to its default implementation for isolation.
- **`mocks/api.ts`** implements every function of `metersApi`, `readingsApi`, `tariffsApi`, `costsApi`, `electricityApi`, and `advancePaymentsApi` as `vi.fn()`. Defaults resolve to empty/minimal data so pages render their empty state (and Recharts never mounts, since it renders poorly in jsdom). `resetApiMocks()` restores these defaults before each test.
- **`utils.tsx`** exports `renderWithProviders(ui, { path, initialEntries })`. The app's only global provider (besides `React.StrictMode` in `main.tsx`) is the router — there is no QueryClient or custom context — so the helper wraps the component in a `MemoryRouter` (with `Routes` + a matching `path`) so `useParams`/`useNavigate` work.

### Writing a new test

1. Import the real component from `pages/` and use `renderWithProviders`.
2. Assert **only** that the component renders without throwing and that **one stable element** is present (a heading, landmark, or role). For route-parameterised pages, pass `path` and `initialEntries` (e.g. `{ path: '/years/:year', initialEntries: ['/years/2024'] }`).
3. Use `findBy*` (async) when the page has a loading gate, `getBy*` when it renders synchronously.
4. Prefer exact heading names when the title text is the whole accessible name. For `CardTitle` headings that also embed an action link (e.g. `MeterList`'s "Alle Zähler" + "Neuer Zähler"), match the name with a regex (`{ name: /Alle Zähler/ }`).

**Constraints that must hold:**
- The smoke-test rules (1–4) are deliberately minimal and must **not** assert on specific numbers, formatted values, dates, currency, or Tailwind classes — these are expected to change during the migration. Focused **component tests** (in `src/test/*.test.tsx`) may assert such specifics when the behaviour under test is exactly that value or option (e.g. the predecessor dropdown exclude-self logic or the m³ `toFixed(1)` formatting).
- Do **not** assert on chart internals; if Recharts data is involved, assert on the surrounding container instead.
- If data is needed beyond the defaults, override a mock per-test via `vi.mocked(metersApi.getById).mockResolvedValue(...)` importable from `src/test/mocks/api`.
- Do not modify application source code to make a test pass. If a route cannot be tested without refactoring app code, skip it and note why instead.

## 9. ESLint React Hooks Status (Sept 2026)

**Toolchain Upgrade (Sept 22, 2026):**
- Upgraded Vite: 5.0.0 → 7.3.6
- Upgraded Vitest: 2.0.0 → 3.2.7
- Upgraded TypeScript: 5.2.2 → 5.9.3
- Upgraded ESLint: 8.53.0 → 9.39.5 with **flat config format** (`eslint.config.js`)
- Upgraded `eslint-plugin-react-hooks`: 4.6.0 → 7.1.1 (multiple new strict rules)
- Added new dependencies: `@eslint/js@9.39.5`, `globals@17.12.0`, `typescript-eslint@8.70.1`
- Removed old `.eslintrc.cjs` file

**ESLint Configuration Correction (Sept 22, 2026):**

The migration to `eslint-plugin-react-hooks` 7.x introduced four new strict rules:
- `react-hooks/set-state-in-effect`: Detects synchronous `setState()` calls in effect bodies (performance anti-pattern)
- `react-hooks/immutability`: Detects variable mutations and functions accessed before declaration
- `react-hooks/refs`: Detects ref mutations or accesses during render
- `react-hooks/purity`: Detects pure function violations in effects

**Status (updated Sept 22, 2026): ✅ RESOLVED.** The 18 errors (9× `set-state-in-effect`, 5× `immutability`, 3× `purity`, 1× `refs`) across the 10 pages above plus 5 component errors were fixed as part of the React 18 → 19 upgrade with the new `useFetch` hook — see **section 11**. Current lint state: **0 errors, 38 warnings**.

**Remaining Warnings (38):**
- `@typescript-eslint/no-explicit-any`: 29 (pre-existing, out of scope; the custom-range/shared refactor removed 12 further `any` usages that were duplicated in the three year-detail tooltip components)
- `no-console`: 8 (was 14 — the migration removed 7 per-page fetch logs; `useFetch` adds 1 central error log)
- `react-refresh/only-export-components`: 1 (pre-existing)

The 3 pre-existing `react-hooks/exhaustive-deps` warnings were eliminated alongside the migration.

**Configuration Files:**
- `eslint.config.js`: Flat config format for ESLint 9+ (replaces `.eslintrc.cjs`)
- `vite.config.ts`: Includes test globals for Vitest (describe, it, expect, etc.)
- `tsconfig.json`: Unchanged, compatible with TypeScript 5.9.3

## 10. Known Issues / TODOs

1. ~~**Mixed language UI:** Several pages (e.g. Home, AddReading) still use English labels — meters pages are fully translated to German.~~ Home page, AddReading, and meters pages are now fully German.
2. ~~**`select.tsx` dead code:** Unused `SelectTrigger`, `SelectContent`, `SelectValue` exports.~~ Removed — those three components were unused and now deleted.
3. ~~**`MeterList` misplaced:** Lives in `components/` but used as route page.~~ Moved to `pages/MeterList.tsx`.
4. ~~**`index.html` language:** `<html lang="en">` doesn't match German UI.~~
5. ~~**Vite dev proxy target:** containerized dev sets `VITE_PROXY_TARGET: http://backend:8000` via `docker-compose.dev.yml`; the `vite.config.ts` default of `http://localhost:8000` is only used for native development.~~
6. ~~**No reading list/edit/delete.**~~
7. ~~**No dark mode toggle.**~~
8. ~~**`dist/` directory** present in repository (build artefact).~~
9. ~~**jsx-a11y baseline warnings:** `jsx-a11y/recommended` currently reports 5 warnings across `components/ui/`. Resolved in `components/ui/dialog.tsx` (semantic fix), `components/ui/card.tsx` and `components/ui/label.tsx` (justified disable comments).~~ Baseline is now clean — no `jsx-a11y` warnings remain.

## 11. React 19 Upgrade & `useFetch` Migration (Sept 22, 2026)

### Versions

| Package | Before | After |
|---|---|---|
| react / react-dom | ^18.2.0 (18.3.1) | **^19.3.0** |
| @types/react / @types/react-dom | ^18.x | **^19.3.0** |
| lucide-react | ^0.303.0 | **^1.47.0** — 0.303 declares peer `react ≤18` only and broke `npm ci` in both Dockerfiles (ERESOLVE); 1.x declares React 19. All 26 icons used in the app still exist (tsc-verified, browser-verified). |
| @testing-library/dom | (transitive only) | **^10.4.2 explicit** — peer of RTL 16; had been dropped by a `--legacy-peer-deps` install |
| react-router-dom, recharts, vite | unchanged | unchanged |

`main.tsx` (`createRoot`) is React 19-compatible without changes. UI, routes and behaviour are visually identical.

### New hook: `src/hooks/useFetch.ts`

`useFetch<T>(fetchFn, deps = []) => { data, loading, error }` — now used by **all 11 route pages** (AddReading, AdvancePaymentForm, AdvancePaymentList, CustomRange, MeterDetail, MeterForm, MeterList, TariffForm, TariffList, YearDetail, YearsOverview).

Design constraints (driven by `eslint-plugin-react-hooks@7.1.1` rules):
- All `setState` calls happen **only inside Promise callbacks** — never synchronously in the effect body (`set-state-in-effect`). The `loading` reset on dep-change/refetch uses a microtask (`void Promise.resolve().then(...)`).
- `fetchFn` is kept in a ref written **from inside the effect** (`react-hooks/refs`); the effect depends on a stable deps identifier.
- An `active` flag prevents state updates after unmount or after deps changed mid-flight; an internal request counter ignores stale responses.
- Error handling is centralised: the original `console.error` per page collapsed into exactly one in the hook; `error` exposes `err.message`. Page-specific messages ("Ungültige Zähler-ID", "Fehler beim Laden der Zähler…") are preserved by rethrowing `new Error('<text>')` inside the page's `fetchFn` — user-visible strings are unchanged.
- Refetch after mutations: list pages hold a `reloadKey` state (`useFetch` deps) and bump it after create/delete/update — replaces the old `await fetchData()` calls that were flagged as effects-calling-component-scope-functions (`immutability`).

### Error-fix patterns (all 18 errors + 5 component errors)

- **9× `set-state-in-effect`** → `useFetch` (7 pages) or removal of the sync `setState` (2 forms).
- **5× `immutability`** → functions no longer declared after the effect that used them (`useFetch` takes them as an argument).
- **1× `refs`** (`YearDetail.tsx`: `sectionsRef.current = sections` during render) → moved into `useEffect([sections])`.
- **3× `purity`** (`Date.now()` during render in `GasSection`/`MeterBlock`/`WaterSection` tooltip) → module-level `const LOAD_TIME_MS = Date.now()`. Trade-off: the "future point" check in tooltips is now relative to page load instead of hover time (invisible in practice).
- **`MeterForm`/`TariffForm`/`AdvancePaymentForm`**: `setFormData`-style sync effects replaced by **pure render-time derivation** (defaults + override state), so no effect needs to write state.
- **`EditMeterModal`/`ReadingEditDialog`**: the "initialise form state when dialog opens" effects were removed via the **keyed inner component pattern** (`<EditMeterForm key={meter.id} />`) — remount initialises fresh state from props.

### Container build lesson (`npm ci` vs `--legacy-peer-deps`)

`frontend/Dockerfile` and `frontend/Dockerfile.dev` run `npm ci` with **strict peer resolution**. A local `npm install --legacy-peer-deps` masks peer conflicts — after the React 19 bump, both image builds failed with `ERESOLVE` (lucide-react). Verified fix procedure: bump the offending dependency, then `npm ci` in a scratch copy of `package.json`+`package-lock.json`, then `docker compose build`. Both dev and prod images build and run against the live backend afterwards.

### Known non-regressions

- React 19 dev console warning `Each child in a list should have a unique "key" prop … from Line` (Recharts 2.15 internals): **pre-existing**, reproduced identically with the old code under React 19. Recharts 3.x would remove it but is out of scope.
- Validation after migration: `npm run build` ✅, `tsc --noEmit` ✅, 12/12 Vitest smoke tests ✅, ESLint 0 errors, prod container verified in headless Chromium (MeterList, YearDetail render live data; no unexpected console errors).