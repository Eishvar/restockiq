# RestockIQ — Implementation Plan (SDC Hackathon 2026, Domain 2)

> Working name "RestockIQ". To rename it, change only `README.md`, the app title and `config.py`.

## ★ Handoff prompt (paste into any NEW chat/session first)

```
Context: I'm building "RestockIQ" for the SDC Hackathon 2026 (XMUM), Domain 2 "Orbyte Smart SME
Challenge". It's a web app that plans restaurant inventory purchases; the demo tenant is a campus
kopitiam next to AIMST University (Kedah), but it's designed for any café/restaurant. Main selling point:
it cuts the owner's purchase planning from ~2 days of manual calculation to a few minutes (SDG 8.2).

How it works: the owner records current inventory once (quantity, last purchase date, shelf life per
item; editable later). They pick a horizon of 1–7 days. The forecaster ("calendar_topdown") predicts
how busy each day will be (recent level × weekday pattern × learned calendar effects: periods like
semester/break/intake or school holidays, public holidays, local events) and splits that into dishes by
recent popularity. Dishes → ingredients via recipes. Each ingredient gets a SAFETY BUFFER measured
from the restaurant's own past forecast errors (backtest) at a service level that depends on shelf life
and the owner's risk setting. Then the app simulates stock day by day (expired stock excluded,
perishables bought in trips), rounds up to supplier packs and shows a priced shopping list per supplier
with a "Why?". Manager submits → owner approves → WhatsApp → activity log. The LLM only turns messy
stock notes into inventory rows and suggests shelf lives; a human confirms; the LLM never sets quantities.

Constraints: synthetic data only (data/ in the repo, from synthetic_data/; data/reference_forecast.py
is the validated prototype of the forecaster + buffer maths). The real restaurant files in
"sales history/" are PRIVATE: never read or commit them. Replit is compulsory (hosting + Postgres +
Replit-managed Claude). No GPU, so no RunPod. Apache-2.0 LICENSE, one commit per module, no secrets.
Preliminary deadline: Sun 25 Oct 2026, 07:59 AM MYT.

Do this now: read IMPLEMENTATION_PLAN.md (repo root, or one folder up) and CLAUDE.md if it exists. Run
`git log --oneline` to see which modules (M0–M8, B1–B12) are done; each is one commit "Mx: ...". Then
tell me in ≤8 lines what's done, what's next and any risk, and wait for my go.
```

**How to use this file with Sonnet:** build one module at a time, in order. Paste each module's **Sonnet prompt** into a fresh Claude Code (Sonnet) session opened in the repo. Commit after each module as `Mx: <title>`; this also gives you the steady commit history the judges check. For anything not in this plan, use §9.

---

## 0. Deadlines (today: Thu 22 Oct 2026)

| When (MYT) | What |
|---|---|
| **Sun 25 Oct, 07:59:59 AM** | Preliminary submission closes. **Submit Sat 24 Oct evening.** Repo frozen afterwards. |
| 28 Oct 8 PM → 29 Oct 12 PM | Finalists confirm |
| 28–30 Oct | Phase 2 upgrading (finalists) |
| 31 Oct 09:30 → 1 Nov 07:59:59 | 24 h physical hackathon; final deliverables |
| 1 Nov | 10 min live pitch + 5 min Q&A; slides as **.pptx** |

**Tier A (M0–M8) must be live by Sat 24 Oct.** Tier B is for Phase 2 and the physical round.

---

## 1. Product

**Selling point (the "wow"): time.** Today the owner spends **~2 days** working out what to buy. RestockIQ produces a priced, explained shopping list in **seconds**, and the owner approves it in **minutes** (SDG 8.2 productivity). A data-driven buffer means the restaurant rarely runs out, and shelf-life awareness stops buying perishables that would expire (SDG 12.3).

**First use: "Set up your inventory" (one time).** Item, quantity, **date last bought**, **shelf life (days)**. The demo is pre-filled with synthetic inventory. Afterwards the **Inventory** page lets the owner add/remove items, edit quantities and shelf lives, and see expiry status (OK / Expiring soon / Expired → discard).

**Every cycle: "Plan purchases".**
1. Today (demo: Thu 22 Oct 2026) + **horizon 1 · 2 · 3 · 4 · 5 · 6 · 7 days** (starting tomorrow). Generate.
2. Results in seconds:
   - **Time-saved banner**: "Done in 2.1 s · 4,700 calculations · about 2 days of manual work."
   - **Forecast card**: expected dishes per day with driver chips (e.g. "Semester break + intake", "Friday", "Public holiday") and a chart of the last 4 weeks actual + the forecast days.
   - **Discard list** (expired stock).
   - **One purchase list per supplier**: item · forecast need · **safety buffer (%)** · usable stock · buy (packs) · when (perishables may be bought in several trips) · pack price · line total; subtotal; **grand total RM**; a **"Why?"** per line.
3. Edit → **Submit** (manager) → **Approve / Reject** (owner) → **Send via WhatsApp** → **Mark received** (adds to inventory and sets the last-bought date).

**Domain 2 journey mapping (scored):**

| Required step | RestockIQ |
|---|---|
| 1. Trigger | The owner picks a horizon → Generate (Tier B: nightly automatic 3-day draft) |
| 2. Connected data | Daily sales history, menu, recipes, inventory with purchase dates & shelf lives, supplier packs & prices, business calendar |
| 3. Decision logic | Forecast learned from the restaurant's own history (statistics, CPU) → recipes → safety buffer from measured forecast error → shelf-life-aware stock simulation → packs → cost. LLM only for messy input (stock notes, shelf-life suggestions), always confirmed |
| 4. Human approval | Staff (view, update stock) / Manager (generate, edit, submit) / Owner (approve, reject, send, settings) |
| 5. Outcome + log | WhatsApp order per supplier, status tracking, inventory updated on receipt, every action logged |

---

## 2. Data (ready: `synthetic_data/`, copied to `restockiq/data/`)

Generated by `generate.py` (seed 42): a campus kopitiam next to AIMST, **365 days of daily sales 2025-10-22 → 2026-10-21**, 143 menu items, ~29k rows, RM641k/year, ~260 dishes/day on average.

| File | Content |
|---|---|
| `daily_sales.csv` | date, item_id, item_name, category, qty, unit_price_rm, net_sales_rm. Rows only when qty > 0 (missing = 0) |
| `menu_items.csv` | item_id, name, category, price_rm, launch_date (2 items launched in 2026) |
| `ingredients.csv` | 74 raw items: supplier_id, storage, base_uom, pack_uom, pack_size_base, pack_price_rm, **shelf_life_days**, waste_pct (unused) |
| `recipes.csv` | item_id → ingredient_id, qty_per_serving |
| `suppliers.csv` | SUP-FRZ frozen, SUP-DRY dry goods & beverages, SUP-FRS fresh produce/bakery/ice; fake WhatsApp numbers |
| `inventory.csv` | Opening inventory on **2026-10-22**: qty_base, **last_purchased_date**. Deep stock of long-life items, thin perishables; **fresh milk, bread, mango already expired; eggs expire in 2 days** (demo cases) |
| `calendar_events.csv` | **Generic business calendar**: `type` = `period` (with `label` semester / break / intake), `public_holiday`, `local_event`; includes upcoming dates. Another restaurant would use labels like `school_holidays`, `ramadan`, `peak_season` |
| `reference_forecast.py` | **Validated prototype** of the forecaster, backtest and safety-buffer maths (§4). M4 ports it |

**Validated results (reference_forecast.py on this data):** 7-day forecast error on daily totals **13.1% WAPE**, vs ~19–23% for "same weekday last week" and ~26–28% for "4-week average". Single dishes are noisy (~63% WAPE); that's why the planning is done at ingredient level, where errors partly cancel.

**Real restaurant data** (`sales history/`) only shaped the synthetic menu profile (private script). Never copy it into the repo, app, video or slides.

---

## 3. Architecture (frozen)

| Layer | Choice |
|---|---|
| Backend | Python 3.11 + FastAPI |
| DB | SQLAlchemy 2.0 + `DATABASE_URL` (Replit PostgreSQL in prod, SQLite locally); `create_all()` + reseed from `data/` |
| Engine | pandas/numpy pure functions. CPU only, **no RunPod** |
| LLM | `app/ai/llm.py`: Replit-managed Anthropic integration → own `ANTHROPIC_API_KEY` → "AI off" fallback |
| Frontend | React 18 + Vite + TypeScript + Tailwind + Recharts + React Router + TanStack Query |
| Packaging | One process: FastAPI serves `frontend/dist` at `/` and the API at `/api` |
| Hosting | Replit Deployment (Autoscale; warm it before judging) |
| Auth | Simulated role switcher (Owner "Ah Hock" / Manager "Siti" / Staff "Ravi", fictional) via `X-User-Id` + `require_role()` |

### Repo layout (repo = new folder `restockiq/` inside the hackathon folder)

```
restockiq/
├─ CLAUDE.md  IMPLEMENTATION_PLAN.md  README.md  LICENSE (Apache-2.0)  .gitignore  .env.example
├─ data/                       # copy of synthetic_data/ (CSVs, generate.py, reference_forecast.py, README)
├─ backend/app/
│  ├─ main.py  config.py  db.py
│  ├─ core/auth.py  core/activity.py  core/units.py
│  ├─ engine/                  # PURE functions, no DB/HTTP/LLM, unit-tested
│  │  ├─ calendar.py           # calendar_features(): state labels, holiday & event flags per date
│  │  ├─ forecast.py           # calendar_topdown + baselines (naive_last_week, flat_avg_4w)
│  │  ├─ backtest.py           # rolling-origin errors, WAPE
│  │  ├─ safety.py             # service levels + buffer per ingredient & horizon
│  │  ├─ requirements.py       # dishes -> ingredients per day
│  │  └─ purchasing.py         # buffer + shelf-life-aware stock simulation, packs, cost, explanations
│  ├─ ai/llm.py  ai/prompts/*.md
│  ├─ modules/                 # models.py schemas.py service.py router.py per feature
│  │  ├─ __init__.py           # ROUTERS = [...]
│  │  ├─ catalog/ sales/ inventory/ calendar/ planning/ assistant/ activity/ dashboard/ settings/ jobs/
│  └─ seed/load.py
│  tests/
└─ frontend/src/  api/client.ts  components/ui/  layout/  features/<name>/
```

**Module contract:** `models.py` (tables with `tenant_id`), `schemas.py`, `service.py` (logic; engine for maths; `log_action()` for consequential actions), `router.py` (thin, `/api/<module>`, role checks). Register in `modules/__init__.py`.

### Core tables (frozen: add, never rename)

| Table | Key columns |
|---|---|
| tenants | id, name, timezone, **risk_profile** (`lean` / `balanced` / `never_run_out`, default `balanced`), **manual_planning_hours** (default 16), onboarded_at |
| users | id, tenant_id, name, role |
| menu_items | id, tenant_id, name, category, price_rm, launch_date, active |
| suppliers | id, tenant_id, name, category, delivery_days, lead_time_days, min_order_rm, whatsapp |
| ingredients | id, tenant_id, name, supplier_id, storage, base_uom, pack_uom, pack_size_base, pack_price_rm, **shelf_life_days**, active |
| recipes | id, menu_item_id, ingredient_id, qty_per_serving, status, source |
| sales_daily | tenant_id, date, menu_item_id, qty, net_sales_rm; unique(tenant_id, date, menu_item_id) |
| inventory_items | id, tenant_id, ingredient_id (unique per tenant), qty_base, **last_purchased_on**, updated_at, updated_by (expiry = last_purchased_on + shelf_life_days, computed) |
| inventory_movements | id, tenant_id, ingredient_id, date, change_base, reason (`onboarding` / `adjust` / `received` / `discard_expired` / `removed`), user_id, note |
| calendar_events | id, tenant_id, type (`period` / `public_holiday` / `local_event`), label, start_date, end_date, name, status (`approved` / `suggested`), source (`seed` / `manual` / `ai`) |
| safety_profiles | tenant_id, ingredient_id, horizon_days (1–7), service_level, buffer_pct, n_samples, method (`measured` / `default`), computed_at |
| forecast_quality | tenant_id, computed_at, model_name, horizon_days, wape_total, wape_items, baseline_naive_wape, baseline_flat_wape |
| plan_runs | id, tenant_id, created_at, created_by, trigger, today, horizon_days, risk_profile, duration_ms, calc_count, summary (json) |
| forecast_lines | run_id, date, menu_item_id, qty, drivers (json: state, weekday factor, holiday/event effect) |
| purchase_orders | id, tenant_id, run_id, supplier_id, status (`draft` → `pending_approval` → `approved` → `sent` → `received`, or `rejected`), total_rm, reject_reason, submitted_at, approved_by, approved_at |
| po_lines | id, po_id, ingredient_id, need_base, buffer_pct, buffer_base, usable_stock_base, buy_schedule (json [{date, packs}]), suggested_packs, final_packs, pack_price_rm, line_total_rm, leftover_base, explanation (json) |
| ai_suggestions | id, tenant_id, kind, input_text, payload (json), status, model, decided_by |
| activity_log | id, tenant_id, ts, user_id, role, action, entity_type, entity_id, details (json) |

---

## 4. Decision logic (port `data/reference_forecast.py`; keep the numbers matching)

### 4.1 Forecast: `calendar_topdown` (`engine/calendar.py`, `engine/forecast.py`)
Using only history before the forecast start:
1. **Daily total** T(d) = dishes sold (zero-filled).
2. **Weekday profile**: median of T(d) / centred 7-day mean per weekday, normal days only, normalised to mean 1.
3. **Learned calendar effects**: public holiday (incl. the day before/after) and local-event ratios vs the surrounding 15-day median, shrunk toward 1 with few samples: `(n·r + 3)/(n + 3)`.
4. **Period levels**: deseasonalised total per calendar **state** = sorted combination of active period labels (e.g. `break+intake`; `normal` if none). Level = median per state.
5. **Boundary smoothing**: level(d) = mean of the state levels over d ± 4 days (customers drift in/out around period boundaries; this cut the worst transition errors).
6. **Recent strength** = median over the last 14 days of (deseasonalised total / level). This captures growth or decline automatically, so **no manual growth assumption is needed**, and it works for any restaurant.
7. T̂(d) = level(d) × strength × weekday(d) × holiday/event effect.
8. **Dishes** = T̂(d) × item share (0.7 × last 28 days + 0.3 × all history; items launched < 60 days ago: last 28 days only) × category weekday adjustment (e.g. breakfast on weekdays), renormalised to T̂(d).
9. Each forecast line stores its drivers, which the UI shows as chips.

Baselines for the accuracy card: `naive_last_week`, `flat_avg_4w`. A cold start (< 8 weeks of history) uses `flat_avg_4w` × weekday profile and flags it.

### 4.2 Requirements (`engine/requirements.py`)
`need[g, d] = Σ dishes[item, d] × qty_per_serving[item, g]`. Dishes without a recipe → exceptions.

### 4.3 Safety buffer (`engine/backtest.py`, `engine/safety.py`)
**Why not a fixed %?** How much extra you need depends on how unpredictable each ingredient is, how many days you buy for, and whether leftovers are wasted. Measured on our data: a flat +10% would cover demand only about 60–65% of the time for main ingredients.
1. **Backtest**: rolling origins every 7 days over the last 26 weeks (≥ 12 origins); for each origin and horizon 1–7, compute each ingredient's relative error `actual_need / forecast_need − 1`. These errors include the model's bias, so the buffer also corrects systematic under-forecasting.
2. **Service level** (= share of cases where the buffer is enough) from shelf life × the owner's risk profile. Shortages cost more than leftovers (a lost Sambal Chicken Rice ≈ RM5.60 margin vs ≈ RM2.20 ingredients), and leftovers of long-life items aren't wasted:

   | Risk profile | Short life (< 7 d) | Medium (7–29 d) | Long (≥ 30 d) |
   |---|---|---|---|
   | Lean (minimise waste) | 70% | 80% | 90% |
   | **Balanced (default)** | **80%** | **90%** | **95%** |
   | Never run out | 90% | 95% | 98% |

3. **Buffer** for ingredient g at horizon h = the empirical quantile of g's errors at its service level; clipped to [0%, 60%]. With < 12 samples (new restaurant / new ingredient) → **default 15%**, flagged "default until we learn your pattern".
4. Computed at seed time and nightly (B1) into `safety_profiles` + `forecast_quality`; plans only read the table (fast).

Reference values on our data (Balanced, 3-day horizon): chicken breast ~29%, rice ~32%, eggs ~29%, fresh chicken leg ~37%, ice ~17%; low-volume items are often larger, but pack rounding covers them anyway. Shorter horizons need a larger % (errors average out over more days).

### 4.4 Purchasing with buffer + shelf life (`engine/purchasing.py`)
Per ingredient, from today (today's expected use is included because today's sales consume stock before tomorrow) to the end of the horizon:
1. **Expired stock is excluded** (`last_purchased_on + shelf_life_days ≤ today`) → Discard list.
2. **Day-by-day simulation**: lots with expiry dates; each day drop expired lots, then use the oldest stock first.
3. When a day ≥ tomorrow would run short → **buy on that day** to cover `d … min(d + shelf_life − 1, end)`: `target = need_window × (1 + buffer[g, len(window)])`, `packs = ceil((target − usable) / pack_size)`. The lot expires at d + shelf_life. Leftovers (buffer + pack rounding) carry forward while fresh, so later trips buy less.
4. Line output: forecast need, buffer % and amount, usable stock (with expiry), today's expected use, `buy_schedule`, packs, cost, leftover, explanation, e.g.:
   *"Forecast for Fri 23 – Sun 25: 1,800 g. Safety buffer +29% (enough in 95% of past cases) = 2,322 g. Stock 700 g (good until 17 Jan) − today's use 600 g = 100 g usable. Buy 2,222 g → 2 PKT (2 kg) = RM40.30. 1,778 g left over for next week."*
5. Supplier subtotal, grand total, warnings (below min order; ingredient unused by any recipe), `calc_count` for the time-saved banner.

### 4.5 AI (LLM): only for messy human input, always confirmed
| ID | Feature | Tier |
|---|---|---|
| A1 | **Quick stock entry**: paste a messy note in BM/English ("beras 12 bag, telur 3 tray beli semalam, ayam 2 ctn isnin") → mapped to ingredients, base units, dates → editable rows → Confirm | A |
| A2 | **Shelf-life & unit suggestion** when adding a new item ("Kicap manis 2L bottle" → 730 days, dry, ml) | A |
| A3 | **Notes → calendar suggestions** ("Orientation for new students on Monday", "Ramadan starts 18 Feb") → period/holiday/event entries that feed the forecaster | B |
| A4 | Supplier invoice reader → draft "received" entries + price updates | B |
| A5 | Recipe drafter for new dishes | B |

---

## 5. CLAUDE.md (M0 creates this file in the repo)

```markdown
# RestockIQ: rules for AI coding sessions
Read IMPLEMENTATION_PLAN.md §1–§4 before changing anything.

## Hackathon brief (Domain 2, "Orbyte Smart SME Challenge"): every feature must serve this
Problem statement: "a reliable, easy-to-learn automation product for the Orbyte ecosystem that removes one recurring operational burden for micro and small businesses, improves accuracy and consistency, and keeps people in control, so it can serve many SMEs." Users: Malaysian micro/small business owners and small teams who rely on WhatsApp, spreadsheets and paper, with mixed digital confidence.

The product must demonstrate ONE complete journey (judges check each step live):
1. Trigger: a business event/request starts the work (here: the owner picks a horizon and clicks Generate; nightly run later).
2. Connected data: the automation pulls together the relevant business information (sales, recipes, inventory, suppliers, calendar).
3. Decision logic: rules, or AI ONLY where it adds value (here: statistical forecast + rules; the LLM only for messy input).
4. Human approval: a person with the right role approves the consequential action (owner approves the purchase order).
5. Visible outcome: the action completes, the user sees the result, and it is recorded in an activity log.

Must-have features (all six; missing one costs marks):
1. One clear SME problem: manual inventory purchase planning (~2 days per cycle).
2. Core automated journey from business input to a useful outcome, AI only where it adds value.
3. Accuracy and ease of learning: more accurate and consistent than doing it by hand, usable WITHOUT formal training (plain words, sensible defaults, tooltips, empty states, no jargon in the UI).
4. People stay in control: who may view/act on data (roles), human approval before consequential actions, a simple activity/audit record. Login/RBAC may be simulated.
5. Orbyte fit and reuse: works as a module of a shared business hub and can be adapted for many SMEs (multi-tenant, no restaurant-specific code, reusable API).
6. Business benefit + SDG: measurable benefit (time saved, errors avoided) and the SDG link (8.2, 8.3; 12.3).

Good-to-have (boost Innovation / Problem-Solution Fit): real-world validation with SME owners; automatic triggers (schedules/rules) with human oversight; explainable decisions that hand missing info/exceptions to a human; a reusable building block (connector/module/API); a business model (freemium/usage/partner); a growth path to other SMEs and markets.

Boundaries (do not violate):
- Synthetic data only; no real personal, customer or company records anywhere in the repo, app or demo. Explain PDPA (Malaysia) handling for a real deployment.
- Out of scope: processing real payments, statutory filings, legal or financial advice. The app prepares orders; it never pays or transfers money.
- Add a distinct SME capability; do NOT rebuild Orbyte's existing HR/admin functions.
- Fit the hub (connected functions and data), not an unrelated standalone tool. Design for many SMEs, not one shop's internal process.
- Focus: demo one clear use case well; broader ideas go to the roadmap (Tier B).
- No live Orbyte access is needed; invent clean interfaces/API assumptions.

Preliminary rubric: Innovation & Creativity 30% (specific pain point, original, AI only where it adds value, not a re-skinned chatbot) · Problem-Solution Fit 25% (removes a recurring burden, accurate, easy to learn, permissions + approval + activity record, Orbyte fit, reusable, within boundaries) · Feasibility of Build 25% (the trigger→data→decision→approval→outcome journey running live, backed by this GitHub repo; synthetic data and own API assumptions in place; hardest risk named with a fallback) · Clarity of Proposal 20%.
Event rules that affect the code: Replit must be used (deployment); GPU work must use RunPod (we have none); public repo with an Apache-2.0 LICENSE; steady commits (no giant last-minute commit); never commit API keys or secrets; every team member must be able to explain every major component, so keep code readable and documented.

## Architecture rules (do not break)
- Backend FastAPI in backend/app; frontend React+Vite+TS+Tailwind in frontend/src. One process: FastAPI serves frontend/dist at "/" and APIs at "/api/*".
- engine/ = PURE functions (pandas/numpy). No DB, HTTP or LLM in engine/. The forecaster, backtest and safety maths must match data/reference_forecast.py (tests compare against it).
- Each feature = backend/app/modules/<name>/ (models, schemas, service, router) registered in modules/__init__.py, plus frontend/src/features/<name>/.
- Every table has tenant_id. Do not rename or drop core tables (IMPLEMENTATION_PLAN.md §3); add new ones.
- No restaurant-specific assumptions in code (no "students", no AIMST, no fixed growth %). Everything restaurant-specific lives in data: calendar_events, recipes, shelf lives, tenant settings.
- Safety buffers come from safety_profiles (measured from backtest errors, service level from shelf life × tenant.risk_profile; default 15% when < 12 samples). Show the buffer % in every purchase line.
- Purchasing must respect shelf life: expired stock is never counted; perishables are bought in trips.
- Consequential actions (generate plan, edit line, submit/approve/reject/send/receive, inventory add/edit/remove/discard, settings or calendar change, accept AI suggestion) MUST call core.activity.log_action(). Inventory quantity changes also write inventory_movements.
- Role checks only via Depends(require_role(...)); owner > manager > staff.
- LLM only via app/ai/llm.py complete_json(); prompts in app/ai/prompts/. LLM output = pending ai_suggestions until a human confirms. The LLM never decides purchase quantities.
- AI unavailable => graceful fallback (manual forms still work).
- Data from data/*.csv (synthetic). Never read or commit files outside the repo. No secrets in code.
- "Today" defaults to the day after the latest sales date (2026-10-22), overridable via env TODAY or Settings. Horizon 1–7 days starting tomorrow.

## Conventions
- Python type hints, pydantic v2, SQLAlchemy 2.0 Mapped[] style, dates in Asia/Kuala_Lumpur.
- Quantities in base units (g/ml/pcs) internally; display via core/units.py.
- snake_case JSON; TanStack Query hooks in features/<name>/api.ts; components/ui; mobile-friendly; loading/empty/error states.
- pytest for engine/ (required) and the happy path of each router.

## Commands
- Backend: cd backend && uvicorn app.main:app --reload --port 8000
- Frontend: cd frontend && npm run dev   (proxy /api -> :8000)
- Reset demo DB (also recomputes safety profiles): cd backend && python -m app.seed.load --reset
- Tests: cd backend && pytest -q
- Build: cd frontend && npm ci && npm run build
```

---

## 6. Tier A modules: preliminary MVP (live by Sat 24 Oct)

### M0. Scaffold + repo (~30 min)
Create `restockiq/`; copy `../synthetic_data/*` → `restockiq/data/` and `../IMPLEMENTATION_PLAN.md` → root; CLAUDE.md (§5); Apache-2.0 LICENSE; .gitignore (Python, Node, .env, *.db, frontend/dist); .env.example (DATABASE_URL, TODAY, LLM_MODEL, ANTHROPIC_API_KEY, JOB_TOKEN). FastAPI `/api/health`; Vite React AppShell with sidebar **Plan purchases, Inventory, Orders, Dashboard, Calendar, Recipes, Activity, Settings** (placeholders); Vite proxy; components/ui (Button, Card, Badge, Chip, Table, Modal, Stat, EmptyState, SegmentedControl, Tooltip, Toast).
**Accept:** both servers run; `/api/health` OK; `git init` + first commit, pushed to a **private** GitHub repo (it goes public at submission).

> **Sonnet prompt (M0)** (open Claude Code in the hackathon folder for this one; from M1 on, open it inside `restockiq/`): "Read IMPLEMENTATION_PLAN.md fully. Do module M0 only, exactly as in §6 M0 and §3: create restockiq/, copy the synthetic data and the plan in, write CLAUDE.md with the exact content of §5, scaffold backend and frontend. No business logic. List the created files at the end."

### M1. Data model, simulated auth, activity log (~1 h)
All core tables (§3); `core/auth.py`, `core/activity.py`, `core/units.py` ("2.4 kg", "1.5 L", "38 pcs", "3 CTN (6x2kg)"); `GET /api/me`, `/api/users`, `/api/activity` (manager+). Frontend: RoleSwitcher + Activity page.
**Accept:** switching role changes `/api/me`; staff → 403 on `/api/activity`; units tests pass.

> **Sonnet prompt (M1):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §3. Do M1 only: all core tables as SQLAlchemy 2.0 models in module folders (create_all on startup), core/auth.py, core/activity.py, core/units.py, the three endpoints, RoleSwitcher + Activity page. pytest for require_role, log_action and units."

### M2. Seed loader + catalog API (~45 min)
`seed/load.py --reset|--if-empty`: tenant "Kopitiam Demo (AIMST)" (risk `balanced`, manual hours 16, **onboarded_at null** so onboarding shows in the demo), users, menu, suppliers, ingredients, recipes, sales_daily, calendar_events, inventory_items (+ `onboarding` movements). Calls the M4 safety computation if engine exists (guard with try/import so M2 works before M4). `POST /api/admin/reset` (owner, logged). `GET /api/catalog/menu|ingredients|suppliers|recipes`.
**Accept:** counts match the CSVs (test); total sales ≈ RM641k; works on SQLite and Postgres.

> **Sonnet prompt (M2):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §2–§3 and M2. Do M2 only: seed/load.py with pandas + bulk inserts, the admin reset endpoint and catalog endpoints. pytest that loads into SQLite and checks counts against the CSVs."

### M3. Inventory module: onboarding + inventory page (~2.5 h)
Backend `modules/inventory`: `GET /api/inventory` (qty + display qty, last_purchased_on, shelf_life_days, **expires_on**, **days_left**, status `ok` / `expiring_soon` (≤ 2 days) / `expired`, supplier, pack info); `POST /api/inventory/items` (add a raw item: name, unit, supplier, pack size & price, shelf life, qty, last bought; manager+); `PATCH /api/inventory/{ingredient_id}` (qty, last_purchased_on, shelf_life_days, pack price; staff: qty only); `DELETE` (soft; manager+); `POST /api/inventory/{id}/discard-expired`; `POST /api/inventory/onboarding/confirm` (owner). Every change → movement + log.
Frontend: **Onboarding wizard** (when onboarded_at is null): "Tell RestockIQ what you have in stock (one time)", grouped by storage, editable qty (unit picker: packs or kg/L/pcs), last bought, shelf life, "+ Add item", Confirm. **Inventory page:** search, status/storage filters, badges, "Expired: discard?" banner, Add-item modal, inline edit, remove, a movement history drawer.
**Accept:** the demo shows 3 expired items + eggs "expiring in 2 days"; editing shelf life updates the status; changes appear in the activity log.

> **Sonnet prompt (M3):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §1, §3 and M3. Do M3 only: inventory endpoints with role rules, movements and logging; the onboarding wizard and Inventory page as described. Expiry = last_purchased_on + shelf_life_days; expiring_soon when ≤ 2 days. pytest for status computation, role rules and movements."

### M4. Engine: calendar, forecast, backtest, safety, requirements, purchasing (~3 h; the core)
Port `data/reference_forecast.py` into `engine/calendar.py`, `forecast.py`, `backtest.py`, `safety.py`; add `requirements.py` and `purchasing.py` (§4.2, §4.4). Signatures:
`forecast(sales_df, menu_df, calendar_df, start, horizon) -> DataFrame[date, item_id, qty, drivers]`;
`backtest(...) -> errors_df`; `safety_profiles(errors_df, ingredients_df, risk_profile) -> DataFrame`;
`plan_purchases(need_df, inventory_df, ingredients_df, suppliers_df, safety_df, today, horizon) -> {suppliers: [{supplier_id, lines, subtotal_rm, warnings}], discard, grand_total_rm, exceptions, calc_count}`.
Service `modules/planning/quality.py`: `recompute_safety(tenant)` fills safety_profiles + forecast_quality (called from seed and from Settings when the risk profile changes).
**Accept (pytest):** weekday pattern, a learned holiday dip, a period switch (break → semester) with boundary smoothing, new-item handling; **on data/ the daily-total WAPE is within ±1 point of the reference (≈13.1%) and beats both baselines**; buffers for chicken breast / rice / eggs at h = 3 within ±5 points of the reference; < 12 samples → 15% default; expired stock excluded; short-shelf-life items produce several dated buys; long-life item with enough stock → no buy; leftovers carried forward; a 7-day plan < 1 s; recompute_safety < 60 s.

> **Sonnet prompt (M4):** "Read CLAUDE.md, IMPLEMENTATION_PLAN.md §4 and data/reference_forecast.py. Do M4 only: port the reference into pure engine modules with the signatures in M4 (refactor for clarity and speed, keep the maths identical), add requirements.py and purchasing.py per §4.2/§4.4 with structured explanations (forecast need, drivers, buffer % + service level + sample count, stock and expiry, today's use, trips, packs, leftover), and modules/planning/quality.py recompute_safety. Write every pytest case in M4, including the comparison against reference_forecast.py outputs."

### M5. Planning workflow API (~2 h)
`modules/planning`: `POST /api/planning/plans {today?, horizon_days 1–7}` (manager+) → engine → save plan_run (duration_ms, calc_count, risk_profile), forecast_lines (with drivers), one draft purchase_order per supplier with po_lines; log `plan_generated`. `GET /api/planning/plans/{id}`: summary, per-day forecast with drivers + last 28 days actual totals, POs, discard list, exceptions, forecast_quality. `GET /api/planning/orders?status=`. `PATCH /orders/{id}/lines/{line_id}` (final_packs; draft only; logged before/after). `POST /orders/{id}/submit` (manager+), `/approve`, `/reject` (owner; reason), `/send` (owner → WhatsApp text + `https://wa.me/<num>?text=`), `/receive` (manager+ → inventory += packs × size, last_purchased_on = today, movement `received`). Invalid transition → 409.
**Accept:** a pytest full journey: generate 3-day plan → edit → submit → staff approve = 403 → owner approve → send link → receive updates inventory → the activity log has every step with the right user.

> **Sonnet prompt (M5):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §4 and M5. Do M5 only: wire the engine into modules/planning with the endpoints and state machine in M5, inventory updates on receive, logging with before/after, and the full-journey pytest. WhatsApp text: greeting, 'Order for <date(s)>', one line per item '<name> – <N> <pack_uom>' (grouped by buy date for trips), subtotal RM, sign-off."

### M6. Plan purchases page + Dashboard (~3 h; the demo)
**Plan purchases:** "Today: Thu 22 Oct 2026" + horizon SegmentedControl **1–7** + Generate.
1. **Time-saved banner** ("Done in 2.1 s · 4,712 calculations · ~2 days of manual work").
2. **Forecast card**: per-day expected dishes with driver chips (period, weekday, holiday/event); a Recharts line chart of the last 28 days actual + forecast days; expandable per-dish table.
3. **Discard list**.
4. **Supplier cards**: Item · Forecast need · **Buffer % (tooltip: "Covers X% of past cases, based on N weeks of your data")** · Usable stock (expiry) · Buy (packs, editable for manager+ while draft) · When · Pack price · RM; the "Why?" sentence; warnings; status stepper; role-aware actions (Submit / Approve / Reject (reason) / Send via WhatsApp (open + copy) / Mark received); toasts.
5. **Grand total** sticky footer.
**Dashboard:** big **"Time saved"** tile (plans × manual hours − measured review time from generated→approved), average review time, **forecast accuracy card** (daily-total WAPE vs the two baselines, from forecast_quality, in plain words: "Our forecast is off by ~13% on a typical day; a simple 4-week average is off by ~27%"), last plan status per supplier, inventory health (expired / expiring soon), top 5 spend items.
**Accept:** a first-time user goes from Generate to a sent, approved order in < 2 minutes; at 390 px everything is usable.

> **Sonnet prompt (M6):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §1, §4.3 and M6. Do M6 only: features/planning (Plan purchases) and features/dashboard using the M5 endpoints (add GET /api/dashboard in a 'dashboard' module). Implement every element listed, including driver chips, the buffer column with tooltip, the Why-sentence renderer, the discard list, role-aware buttons (disabled + tooltip naming the role), toasts and loading/empty/error states. Mobile-friendly."

### M7. AI: quick stock entry (A1) + shelf-life suggestion (A2) (~1.5 h)
`ai/llm.py complete_json(prompt_name, variables, schema)` → dict | None (Replit-managed Anthropic → `ANTHROPIC_API_KEY` → None; `LLM_MODEL` default `claude-haiku-5-5`; 20 s timeout; schema-validated; usage logged).
- `prompts/stock_note.md`: inputs = today, the ingredient list (id, name, aliases, base_uom, pack info), the note → rows [{ingredient_id | null, raw_text, qty, unit, qty_base, last_purchased_on, confidence}]; unknown → suggested new item. Rules: resolve "semalam/yesterday/isnin/Monday" relative to today, never invent quantities, mark low confidence.
- `prompts/shelf_life.md`: name + description → {shelf_life_days, storage, base_uom, rationale}.
- `modules/assistant`: `POST /api/assistant/stock-note` (staff+) → pending ai_suggestion; `POST /suggestions/{id}/apply` (manager+, edited rows) → inventory + movements + log; `POST /api/assistant/shelf-life` → suggestion only.
- UI: "⚡ Quick add from a note" on Onboarding and Inventory (textarea → review table with confidence badges → Apply); "Suggest" next to the shelf-life field in Add-item.
**Accept:** the example note gives correct rows for rice/eggs/chicken with dates; Apply updates inventory; with AI off, both show "AI unavailable, enter manually".

> **Sonnet prompt (M7):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §4.5 and M7. Do M7 only: llm.py with the provider chain isolated in one function, the two prompts, the assistant endpoints and the UI. AI output is always reviewed before applying. Mock the LLM in tests (happy path, unknown item, AI unavailable)."

### M8. Settings, Calendar, Orders, Replit deploy (~2 h)
**Settings (owner):** risk profile (Lean / Balanced / Never run out, with the service-level table from §4.3 explained in plain words; changing it calls recompute_safety), manual planning hours baseline, "Today" override for demos, suppliers (WhatsApp, min order), reset demo data. **Calendar page (manager+):** list/add/edit/delete periods (with label), public holidays and local events; a note that changes improve the next forecast; "Recompute" button. **Orders page:** POs with status filter + detail. All changes logged.
**Deploy:** push to GitHub → Replit *Import from GitHub* → **set the Replit Python version to 3.11 (local dev machine is 3.13)** → add PostgreSQL (`DATABASE_URL`) → Secrets in workspace **and** deployment → build `cd frontend && npm ci && npm run build && cd ../backend && pip install -r requirements.txt` → run `cd backend && python -m app.seed.load --if-empty && uvicorn app.main:app --host 0.0.0.0 --port $PORT` → approve the Anthropic AI integration → Publish (Autoscale). Screenshot the Replit project + deployment for the declaration.
**Accept:** the `*.replit.app` URL works in incognito; onboarding → inventory → plan → approve → WhatsApp → receive works on Postgres.

> **Sonnet prompt (M8):** "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §4.3 and M8. Do M8 only: Settings, Calendar and Orders pages with endpoints (all changes logged; risk-profile and calendar changes trigger recompute_safety), plus Replit deployability (.replit, replit.nix with Python 3.11 + Node 20, PORT from env, seed --if-empty) and DEPLOY.md with the steps in M8. Must work on SQLite and Postgres."

**Tier A finish line (Sat 24 Oct):** live Replit URL with the full journey · repo public + LICENSE + committee collaborators + one commit per module · six submission items (§8).

---

## 7. Tier B modules (Phase 2 / physical round; each independent)

| ID | Feature | Notes |
|---|---|---|
| B1 | Nightly job | 21:00: recompute safety profiles + create a 3-day draft plan (Replit Scheduled Deployment → `python -m app.modules.jobs.nightly`); a dashboard notification |
| B2 | Notes → calendar suggestions (A3) | "Orientation on Monday" / "Ramadan from 18 Feb" → suggested calendar entries → accept → re-plan shows the RM difference |
| B3 | Daily sales import + automatic stock deduction | POS CSV upload → inventory decreases by recipe usage; variance vs physical count flagged; triggers a plan |
| B4 | Batch (lot) tracking | Multiple purchase dates per item (FIFO) |
| B5 | Snap buy dates to supplier delivery days | e.g. frozen only Mon/Thu → merge trips within shelf life |
| B6 | Supplier invoice reader (A4) | PDF → draft "received" + price-change alerts |
| B7 | Recipe editor + AI recipe drafter (A5) | |
| B8 | Accuracy page | Full backtest charts: forecast vs actual, buffer hit rate (how often the buffer was enough vs target), RM over/under-bought |
| B9 | Waste report | RM of discarded stock per month (from movements) → SDG 12.3 evidence |
| B10 | Multi-tenant + templates | Kopitiam / café / bakery templates (calendar labels, typical shelf lives) → Orbyte "serves many SMEs" |
| B11 | Orbyte connector API | `/api/v1`, OpenAPI page, `po.approved` webhook |
| B12 | BM / 中文 UI toggle | |

**RunPod:** not used (no GPU workload). State this in the declaration.

---

## 8. Submission checklist (preliminary, via sdchack.my)

1. **PRD** on the official template → `SDC2026_TeamName_Preliminary.pdf` (problem 250 words, AI solution 300, design-thinking 200). SDG **8.2** + 8.3 + 12.3. **Baseline:** ~2 days (≈16 h) of manual planning per cycle (owner interview, anonymised). **KPIs:** minutes from Generate to Approved; forecast error (13% vs 27% for a 4-week average); share of days fully covered by the buffer. **Phase 2 target:** ≥ 95% less planning time; ≥ 90% of days without a stock-out on core ingredients; 0 expired items counted as stock.
2. **Pitch deck** matching the video.
3. **Live prototype URL** (Replit).
4. **Tech & Tools Declaration** → `SDC2026_TeamName_TechDeclaration.pdf`: Replit proof, Anthropic model via Replit AI Integrations (stock notes, shelf-life suggestions), Claude Code (Opus 5.5 planning, Sonnet 5.5 implementation) with the extent of use, libraries + licenses (FastAPI MIT, SQLAlchemy MIT, pandas BSD-3, numpy BSD-3, React MIT, Vite MIT, Tailwind MIT, Recharts MIT, TanStack Query MIT, matplotlib PSF-style), dataset "self-generated synthetic, no personal data", RunPod "not used: no GPU workload", the AI-review paragraph.
5. **GitHub repo**: public, Apache-2.0 LICENSE, committee collaborators, one commit per module, no secrets, no real data.
6. **YouTube video, 5–7 min** with the live demo (> 7 min costs −1 point per 30 s).

Then open every link in incognito.

**Pitch flow (~6 min), built around TIME:** stopwatch hook ("2 days by hand; watch this take under 2 minutes") → problem and user → **demo**: one-time inventory setup (⚡ paste a messy stock note → AI fills the table → expired milk flagged) → pick 3 days → Generate (2 s) → forecast card with drivers ("semester break + intake, Friday") → supplier lists: buffer % per item, trips for perishables, nothing for rice → "Why?" → submit → owner approves → WhatsApp → activity log → Dashboard (time saved, forecast 13% vs 27%) → people in control → Orbyte fit (works for any restaurant: calendar labels + recipes + shelf lives are data; multi-tenant; freemium for 1 outlet, then per outlet per month) → SDG 8.2 / 12.3 → hardest risk + fallback (new restaurants have little history → default 15% buffer + 4-week-average forecast until enough data; period changes are hard → boundary smoothing + the owner can add calendar entries; AI off → manual entry still works).

---

## 9. Prompts for later changes

**Add-a-feature:**
> "Read CLAUDE.md and IMPLEMENTATION_PLAN.md §3–§4. I want to add: **<feature>**. First tell me in ≤10 lines which module it belongs to (existing, or a new modules/<name> + features/<name>), which new tables/columns/endpoints/components it needs, and confirm it doesn't rename core tables, change the engine signatures or maths (vs data/reference_forecast.py), or change the PO state machine. Wait for my OK. Then implement it following the module contract, register the router, add log_action calls, tests and seed data if needed, and add one line to §7 of IMPLEMENTATION_PLAN.md. Don't refactor unrelated code."

**Bug fix:**
> "Read CLAUDE.md. Bug: <steps, expected, actual, error text>. Find the root cause, fix it with the smallest change, add a regression test, and don't touch unrelated files."

**Regenerate data:** edit `data/generate.py`, run `python generate.py` and `python reference_forecast.py` inside `data/` (check the printed accuracy), then `python -m app.seed.load --reset`.
