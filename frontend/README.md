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
| `/meters` | `components/MeterList.tsx` | Lists all meters in a card grid. Shows label, type, unit, predecessor/successor chain. Supports **delete** (with confirmation). "Add New Meter" link. |
| `/meters/new` | `pages/MeterForm.tsx` | Create meter form: label, meter number (optional), type (select from server‑fetched types), predecessor (optional, same‑type only). Unit is read-only (server-derived). Submits to `POST /api/meters/`. |
| `/meters/:id` | `pages/MeterDetail.tsx` | Single meter detail: line chart of readings (recharts), meter info panel (type, unit, number, created date, total count), recent readings table (last 5, newest first). Fetches `GET /api/meters/:id` + `GET /api/meters/:id/readings`. |
| `/readings/new` | `pages/AddReading.tsx` | Create reading form: meter selector, numeric value, date, optional note. Warns if the selected meter has been replaced by a successor. Submits to `POST /api/readings/`. |
| `/tariffs/new` | `pages/TariffForm.tsx` | Create tariff period form: meter, tariff kind (consumption/feed_in/self_consumption/wastewater), validity range, price per unit, optional base + metering fee. Submits to `POST /api/tariffs/`. Handles empty meter list gracefully. |

## 3. Existing Components

### Reusable UI primitives (`components/ui/`)
All follow the shadcn/ui pattern (Tailwind + `cn()` helper, forwardRef, displayName):

| Component | File | Notes |
|---|---|---|
| `Button` | `button.tsx` | 6 variants (default, destructive, outline, secondary, ghost, link), 4 sizes (default, sm, lg, icon). Uses `cva`. |
| `Card` / `CardHeader` / `CardTitle` / `CardDescription` / `CardContent` / `CardFooter` | `card.tsx` | Standard card composition. |
| `Input` | `input.tsx` | Wraps `<input>` with base styling. |
| `Label` | `label.tsx` | Wraps `<label>` with base styling. |
| `Select` / `SelectItem` (and unused `SelectTrigger` / `SelectContent` / `SelectValue`) | `select.tsx` | Custom native `<select>` wrapper with chevron icon. The shadcn‑style `SelectTrigger`/`SelectContent`/`SelectValue` components are **exported but never imported** in any page – dead code. |
| `Table` / `TableHeader` / `TableBody` / `TableFooter` / `TableHead` / `TableRow` / `TableCell` / `TableCaption` | `table.tsx` | Full shadcn-style table suite. |
| `Textarea` | `textarea.tsx` | Wraps `<textarea>` with base styling. |

### Business components (`components/`)
| Component | File | Notes |
|---|---|---|
| `MeterList` | `MeterList.tsx` | **Functions as a page** (used as `<Route>` element), not as an embeddable component. |

### Hooks
| Hook | File | Notes |
|---|---|---|
| `useMeterTypes` | `hooks/useMeterTypes.ts` | Fetches meter types from `GET /api/meters/types` once per session (module-level cache). Returns `MeterTypeInfo[]`. Also exports `meterTypeLabel()` helper. |

### Types (`types/index.ts`)
Defines: `MeterType`, `TariffKind`, `MeterTypeInfo`, `Meter`, `Reading`, `TariffPeriod` – aligned with backend schemas.

## 4. API Integration

- **Pattern:** Plain axios instance (`api/client.ts`) with module-level API objects (no React Query, no generated client, no custom fetch wrapper).
- **Base URL:** `import.meta.env.VITE_API_URL || ''` – empty string means same-origin, relying on the Vite dev proxy or nginx reverse proxy in production.
- **Dev proxy** (`vite.config.ts`): `/api` → `http://localhost:8000`.

### API objects and endpoints consumed

| Object | Endpoints | Used in |
|---|---|---|
| `metersApi` | `GET /types`, `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id`, `GET /:id/readings` | `useMeterTypes`, `MeterList`, `MeterDetail`, `MeterForm`, `AddReading`, `TariffForm` |
| `readingsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `AddReading` (only `POST`) |
| `tariffsApi` | `GET /`, `GET /:id`, `POST /`, `PUT /:id`, `DELETE /:id` | `TariffForm` (only `POST`) |
| `healthApi` | `GET /health` | **Not used** anywhere in components |

**Notable:** `metersApi.update` and `readingsApi.update`/`delete` are defined but never called. `healthApi` is defined but never imported.

## 5. Styling Approach

- **Tailwind CSS** exclusively (no plain CSS files, no CSS modules, no styled-components).
- **shadcn/ui design tokens** via CSS custom properties in `index.css` (──background, --foreground, --primary, --border, --radius, etc.) with a `.dark` variant.
- **Component compositions:** All UI elements are `className`-styled with Tailwind utilities, composed via `cn()` from `lib/utils.ts`.
- **Theme:** Light-by-default, dark mode supported via `.dark` class (no toggle component).

## 6. Gaps vs. Backend

The following backend endpoints/features have **zero** frontend representation:

| Area | Backend endpoints missing from frontend |
|---|---|
| **Advance payments** | `GET/POST/PUT/DELETE /api/advance-payments/` – no list, no create, no detail page |
| **Cost calculations** | `GET /api/costs/`, `/costs/wastewater`, `/costs/yearly-projection`, `/costs/advance-payment-diff`, `/costs/years-overview` – no UI at all |
| **Electricity: feed-in compensation** | `GET /api/electricity/feed-in-compensation` – no UI |
| **Projections** | `GET /api/projections/meters/{meter_id}/projection` – no UI |
| **Consumption timeseries** | No frontend endpoint consumer for aggregated timeseries data (backend may not even have this endpoint yet) |
| **Tariff list / edit / delete** | Only `POST /api/tariffs/` is used; no page to view, edit, or delete tariffs |
| **Reading list / edit / delete** | Only `POST /api/readings/` is used; no reading browse, edit, or delete |
| **Meter edit** | `PUT /api/meters/` is defined in apiClient but no page uses it |

## 7. Known Issues / TODOs

1. **Mixed language UI:** `AddReading.tsx` uses English labels/prompts ("Meter *", "Cancel", "Adding...") while `MeterForm.tsx` and `TariffForm.tsx` use German ("Name *", "Abbrechen", "Speichern..."). The AGENTS.md mandates "UI strings in German".

2. **`select.tsx` dead code:** The file exports `SelectTrigger`, `SelectContent`, `SelectValue` (shadcn-style custom dropdown components) but none are imported anywhere – only the native `<select>`-based `Select`/`SelectItem` are used. Those unused components have no corresponding Radix UI peer dependency.

3. **`date-fns` not used:** Installed in package.json but zero imports across all source files.

4. **`healthApi` dead code:** Defined in `client.ts` but never imported or used.

5. **`MeterList` misplaced:** Lives in `components/` but used as a route-level page (`/meters`). Convention suggests it should be in `pages/`.

6. **`index.html` language:** `<html lang="en">` does not match the German-majority UI.

7. **Vite dev proxy target:** Hardcodes `http://localhost:8000` while `docker-compose.dev.yml` serves the backend at `http://backend:8000` inside the Docker network. The env var `VITE_PROXY_TARGET` is read but not propagated correctly – the default `localhost:8000` will not work from inside the frontend container.

8. **No loading states on meter fetch in `MeterForm`:** `metersApi.getAll()` call (line 39) has no loading/error handling (unlike `TariffForm` which does).

9. **No tariff period list page:** The only tariff UI is the create form; users have no way to browse, edit, or delete existing tariffs from the frontend.

10. **No reading list/edit/delete:** Readings are only visible as the last 5 in `MeterDetail`; there is no full reading list, no edit, no delete.

11. **No dark mode toggle:** CSS variables exist for both themes but there is no UI control to switch.

12. **`dist/` directory present** in the repository (build artefact) – should be in `.gitignore` (verify).