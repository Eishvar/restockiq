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
- LLM only via app/ai/llm.py (complete_json, and complete_json_with_pdf for PDF sales reports); prompts in app/ai/prompts/. AI is used in exactly two places: (1) the Help chat (modules/help): it explains how to use the app, sees no business data and changes nothing; (2) reading a PDF sales report (modules/sales_data): the PDF goes to OpenRouter's PDF reader and the same OPENROUTER_MODEL as the Help chat, the answer is a strict-schema proposal, and a person checks and can fix it in the preview before anything is saved. The earlier stock-note reader and shelf-life suggester were removed on purpose (the ai_suggestions table is kept, unused). The LLM never decides purchase quantities.
- AI unavailable => graceful fallback (manual forms still work).
- Data from data/*.csv (synthetic). Never read or commit files outside the repo. No secrets in code.
- "Today" defaults to the day after the latest sales date (2026-10-22 with the demo data), overridable via env TODAY or Settings. Horizon 1–7 days starting tomorrow. Uploading a day of sales therefore moves "today" forward by itself, and removing the latest days moves it back (the daily-use behaviour).
- First-time setup (modules/setup, table tenant_setup) is country -> sales history (at least 28 days) -> stock -> recipes -> optional calendar; the frontend sends the owner there until it is done. Malaysia sets MYR and adds data/calendar_my.csv holidays (no duplicates).
- Help chat (modules/help, frontend features/help): FAQ answers live in modules/help/faq.py and cost nothing; the AI answers only questions not on the list (3 per person per minute), from that same text, in short plain text (the prompt asks for it and `clean_answer` strips markdown), and sends no business data. Suppliers and storage places (where an item is kept) are lists people add to and rename (modules/catalog/service.py). When a screen changes, update the matching FAQ answer.
- Sales arrive by uploading CSV, Excel or PDF files (modules/sales_data; there is no POS connection and no FeedMe): the file is read into a draft, a person checks and can fix it in the preview (map dishes, change a date or number, leave rows out), then confirms. Unknown dishes and bad rows are listed and left out, never guessed; a day in the file replaces that day. Whatever is replaced or removed moves to sales_daily_removed so it can be restored; only the owner's "Delete forever" erases it. Any change sets tenant_setup.sales_changed_at, so plans and draft orders made earlier show a warning.
- The order note (planning/whatsapp.py build_order_note) is written when the owner approves and saved in purchase_orders.note_text; sending uses that saved text. It is a purchase order note, never called an invoice.

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
