# Home Energy Usage Tracker – Frontend

## 1. Tech Stack (actual, verified)

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | React | ^18.2.0 | SPA, no SSR/Next.js |
| Build tool | Vite | ^5.0.0 | + `@vitejs/plugin-react` |
| Language | TypeScript | ^5.2.2 | strict mode via tsconfig |
| Routing | react-router-dom | ^6.20.1 | `<BrowserRouter>` with `<Routes>` |
| HTTP client | axios | ^1.6.0 | single `apiClient` instance |
| Charting | recharts | ^2.10.0 | `LineChart` on meter detail page |
| Icons | lucide-react | ^0.303.0 | used in nav, home cards, forms |
| Date utils | date-fns | ^3.0.0 | installed but **not imported** in any component |
| CSS | Tailwind CSS | ^3.3.6 | with `tailwindcss-animate`, `postcss` + `autoprefixer` |
| UI primitives | shadcn/ui style | – | hand-written, not installed via CLI (button, card, input, label, select, table, textarea) |
| Utility | class-variance-authority | ^0.7.0 | used in button variants |
| Utility | clsx + tailwind-merge | ^2.0.0 | `cn()` helper in `lib/utils.ts` |

**Not used (installed but 0 imports):** `date-fns`.

## 2. Existing Pages / Routes

| Route | File | Description |
|---|---|---|
| `/` | `pages/Home.tsx` | Landing page with description cards (electricity, gas, water) and nav links. Static content only – no live data or summary queries. |
| `/meters` | `components/MeterList.tsx` | Lists all meters in a card grid. Shows label, type, unit, predecessor/successor chain. Supports **edit** (inline modal) and **delete** (Dialog with confirmation). "Neuer Zähler" link. German UI. |
| `/meters/new` | `pages/MeterForm.tsx` | Create meter form: label, meter number (optional), type (select from server‑fetched types), predecessor (optional, same‑type only). Unit is read-only (server-derived). Submits to `POST /api/meters/`. |
| `/meters/:id` | `pages/MeterDetail.tsx` | Single meter detail: line chart of readings (recharts), meter info panel (type, unit, number, created date, total count), recent readings table (last 5, newest first). Fetches `GET /api/meters/:id` + `GET /api/meters/:id/readings`. |
| `/readings/new` | `pages/AddReading.tsx` | Multi-meter reading entry form: single date for all meters, per-meter checkbox + value + optional note + last-reading reference. Shows only current (non-replaced) meters via `GET /api/meters/current`. Checkbox selection persisted in localStorage. Submits `POST /api/readings/` per selected meter with value. Shows success/partial-failure results with ✅/❌ per meter. |
| `/tariffs` | `pages/TariffList.tsx` | Tariff overview table with all periods: kind label, meter, valid-from/until, price, base fee, metering fee (monthly or yearly), gas factors. Supports **edit** (inline modal with dynamic tariff-kind fields) and **delete** (with usage check). |
| `/tariffs/new` | `pages/TariffForm.tsx` | Create tariff period form: meter selector, tariff kind (consumption/feed_in/self_consumption/wastewater/feed_in_eeg2009), validity range, dynamic fields per kind (price per unit, optional base + metering fees, gas Z-Zahl/Brennwert for gas meters, EEG 2009 block with tier rates + yearly metering fee). German labels/helper text throughout. EEG 2009 meter selection includes a hint to pick the feed-in meter. Handles empty meter list gracefully. |
| `/years-overview` | `pages/YearsOverview.tsx` | Year-over-year consumption table + line chart for all logical meters (chain-resolved via backend). Years link to `/years/:year`. |
| `/years/:year` | `pages/YearDetail.tsx` | Year detail page grouped by category (Strom, Wasser, Sonstige). Each meter shows: consumption overview (with chain-resolved readings), line chart, readings table, cost projection per meter. **Strom category** includes EEG-Einspeisevergütung card (from `GET /api/electricity/feed-in-compensation`) and hides consumption cost display for export/production meters. **Wasser category** includes Abwasserkosten (from `GET /api/costs/wastewater/`) and Gesamtwasserkosten (Frischwasser + Abwasser). Meter "Kosten" labels renamed to "Frischwasserkosten" for water meters. |

## 3. Existing Components

### Reusable UI primitives (`components/ui/`)
All follow the shadcn/ui pattern (Tailwind + `cn()` helper, forwardRef, displayName):

| Component | File | Notes |
|---|---|---|
| `Button` | `button.tsx` | 6 variants (default, destructive, outline, secondary, ghost, link), 4 sizes (default, sm, lg, icon). Uses `cva`. |
| `Card` / `CardHeader` / `CardTitle` / `CardDescription` / `CardContent` / `CardFooter` | `card.tsx` | Standard card composition. |
| `Input` | `input.tsx` | Wraps `<input>` with base styling. |
| `Label` | `label.tsx` | Wraps `<label>` with base styling. |
| `Select` / `SelectItem` (and unused `SelectTrigger` / `SelectContent` / `SelectValue`) | `select.tsx` | Custom native `<select>` wrapper with chevron icon. |
| `Table` / `TableHeader` / `TableBody` / `TableFooter` / `TableHead` / `TableRow` / `TableCell` / `TableCaption` | `table.tsx` | Full shadcn-style table suite. |
| `Checkbox` | `checkbox.tsx` | Simple `<input type="checkbox">` wrapper with Tailwind styling, following shadcn/ui pattern with forwardRef and `cn()`. |

### Business components (`components/`)
| Component | File | Notes |
|---|---|---|
| `MeterList` | `MeterList.tsx` | **Functions as a page** (used as `<Route>` element), not as an embeddable component. |
| `EditMeterModal` | `EditMeterModal.tsx` | Dialog for editing a meter: name, number, predecessor dropdown. Meter type and unit are read-only. |

### Hooks
| Hook | File | Notes |
|---|---|---|
| `useMeterTypes` | `hooks/useMeterTypes.ts` | Fetches meter types from `GET /api/meters/types` once per session (module-level cache). Returns `MeterTypeInfo[]`. Also exports `meterTypeLabel()` helper. |

### Lib
| File | Description |
|---|---|
| `lib/tariffFields.ts` | Shared helper for tariff field visibility/labels per `TariffKind` and meter type. Exports `getTariffFields(kind, meterType, meterUnit)`, `getPriceUnitLabel(kind, meterType, meterUnit)`, `TARIFF_KIND_LABELS`, `TARIFF_KINDS`, and the `FieldConfig` interface. Used by both `TariffForm.tsx` and `TariffList.tsx`. |
| `lib/utils.ts` | `cn()` helper combining `clsx` and `tailwind-merge`. |

### Types (`types/index.ts`)
Defines: `MeterType`, `TariffKind`, `MeterTypeInfo`, `Meter`, `Reading`, `TariffPeriod`, `TariffUsage`, `YearEntry`, `YearsOverviewItem`, `YearlyProjection`, `FeedInCompensation`, `WastewaterCosts` — aligned with backend schemas.

## 4. API Integration

- **Pattern:** Plain axios instance (`api/client.ts`) with module-level API objects (no React Query, no generated client, no custom fetch wrapper).
- **Base URL:** `import.meta.env.VITE_API_URL || ''` – empty string means same-origin, relying on the Vite dev proxy or nginx reverse proxy in production.
- **Dev proxy** (`vite.config.ts`): `/api` → `http://localhost:8000`.

### API objects and endpoints consumed

| Object | Endpoints | Used in |
|---|---|---|
| `metersApi` | `GET /types`, `GET /`, `GET /current`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id`, `GET /:id/readings` | `useMeterTypes`, `MeterList`, `EditMeterModal`, `MeterDetail`, `MeterForm`, `AddReading` (uses `getCurrent` + `getLastReading`), `TariffForm`, `YearDetail` (chain resolution + readings fetch) |
| `readingsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `AddReading` (only `POST`) |
| `tariffsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `TariffForm` (POST), `TariffList` (GET, PUT, DELETE) |
| `costsApi` | `GET /years-overview`, `GET /yearly-projection`, `GET /wastewater/` | `YearsOverview`, `YearDetail` (projections + wastewater) |
| `electricityApi` | `GET /feed-in-compensation` | `YearDetail` (EEG feed-in compensation) |
| `healthApi` | `GET /health` | **Not used** anywhere in components |

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
| **Advance payments** | `GET/POST/PUT/DELETE /api/advance-payments/` – no list, no create, no detail page |
| **Cost calculations** | `GET /api/costs/` (general), `/costs/advance-payment-diff` – no UI; `/costs/years-overview` ✅, `/costs/yearly-projection` ✅, `/costs/wastewater/` ✅ (implemented in `YearDetail`) |
| **Electricity: feed-in compensation** | `GET /api/electricity/feed-in-compensation` — ✅ implemented in `YearDetail` as part of Strom category |
| **Projections** | `GET /api/projections/meters/{meter_id}/projection` – no UI (separate from `/costs/yearly-projection`) |
| **Consumption timeseries** | No frontend endpoint consumer for aggregated timeseries data |
| **Tariff list / edit / delete** | ✅ Implemented – see `/tariffs` route above |
| **Reading list / edit / delete** | Only `POST /api/readings/` is used; no reading browse, edit, or delete |
| **Meter edit** | `PUT /api/meters/` via `EditMeterModal` in `MeterList` |

## 7. Known Issues / TODOs (unchanged)

1. ~~**Mixed language UI:** Several pages (e.g. Home, AddReading) still use English labels — meters pages are fully translated to German.~~ Home page is now fully German; AddReading still has some English labels.
2. **`select.tsx` dead code:** Unused `SelectTrigger`, `SelectContent`, `SelectValue` exports.
3. **`date-fns` not used:** Installed but zero imports.
4. **`healthApi` dead code:** Defined but never imported.
5. **`MeterList` misplaced:** Lives in `components/` but used as route page.
6. ~~**`index.html` language:** `<html lang="en">` doesn't match German UI.~~
7. **Vite dev proxy target issue:** Default `localhost:8000` won't work from inside frontend container.
8. **No reading list/edit/delete.**
9. ~~**No dark mode toggle.**~~
10. **`dist/` directory** present in repository (build artefact).