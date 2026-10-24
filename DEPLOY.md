# Deploying RestockAI on Replit

Replit is compulsory for this hackathon (hosting + PostgreSQL + the Replit-managed Claude integration).
One process serves everything: FastAPI answers `/api/*` and serves the built web app at `/`.

> The Replit config files (`.replit`, `replit.nix`) were written from Replit's documented format but could not be
> run on the author's machine. If a step below differs on screen, trust Replit's UI and adjust the file.

## 1. Import the repository

1. On replit.com choose **Create App â†’ Import from GitHub** and pick this repo (it can stay private while you set up).
2. Replit reads `.replit`: Python 3.11, Node 20, PostgreSQL 16.
3. In the workspace **Tools â†’ Shell**, run `python --version`. It must say 3.11.x. (The author's laptop uses 3.13;
   the code works on both, but Replit should be 3.11 to match the declaration.)

## 2. Add the database

1. **Tools â†’ Database â†’ PostgreSQL** (create it). Replit sets `DATABASE_URL` for you.
2. Nothing else is needed: the app creates its tables on start and `python -m app.seed.load --if-empty` loads the
   synthetic demo data the first time (about 10 seconds, it also measures the safety buffers).

## 3. Secrets (**Tools â†’ Secrets**)

Set these in the workspace **and again in the Deployment** (Deployment secrets are separate):

| Secret | Value |
|---|---|
| `TODAY` | optional. `2026-10-22` pins the demo date. Leave it out and use **Settings â†’ Demo date** instead. |
| `LLM_MODEL` | optional. Defaults to `claude-haiku-5-5`. |
| `OPENROUTER_API_KEY` | optional. Your OpenRouter key, if you use OpenRouter for the AI (step 4). Never paste it in chat or in the repo. |
| `OPENROUTER_MODEL` | optional. An OpenRouter model id. Defaults to `anthropic/claude-haiku-4.5`. |
| `ANTHROPIC_API_KEY` | optional. Only if you want to call Claude directly instead. |

Never put a real key in the repo. `.env.example` lists the names only.

## 4. AI (which model answers)

AI is used in two places. The **Help chat** (the green Help button) explains the app: common questions are answered from a stored list and never call the AI; only typed questions do, at most 3 per minute per person. **Reading a PDF sales report** (Sales data page) turns a PDF into rows that a person then checks before saving; CSV and Excel files never use AI.
Both use `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (the model id, for example `deepseek/deepseek-v4.1-flash`). Set both in the **Deployment** secrets too. Never paste a key in the repo or in chat.
For a PDF, OpenRouter's own PDF reader (its OCR engine reads scanned pages) extracts the text and passes it to the same model, so no second model setting is needed. Without the key, PDF upload shows "upload a CSV or Excel file instead" and everything else keeps working.
1. Check: open the app, press **Help**, and type a question that is not in the list, such as "where can I see old orders?".
   A short plain answer labelled "AI answer" means it works. If it says the AI helper is not available, the key or the model id is missing in this environment (workspace vs deployment).
   The rest of the app keeps working without AI.

## 5. Run it in the workspace

Press **Run**. It builds the web app (`cd frontend && npm ci && npm run build`), installs the Python packages,
seeds the database if empty and starts `uvicorn` on `$PORT`. Open the preview and test the journey (step 7).

## 6. Publish (Autoscale deployment)

1. **Publish â†’ Autoscale**. Build command and run command come from `.replit`:
   - build: `cd frontend && npm ci && npm run build && cd ../backend && pip install -r requirements.txt`
   - run: `cd backend && python -m app.seed.load --if-empty && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Add the deployment secrets (step 3) and publish.
3. **Warm it before judging:** Autoscale sleeps when idle. Open the `*.replit.app` URL a few minutes before a demo,
   sign in, press **Generate plan** once. The first request after a sleep takes a few seconds.
4. Open the URL in an **incognito window** to prove it works for a stranger.

## 7. Journey check (about 3 minutes)

As **Ah Hock (Owner)** confirm the one-time stock setup â†’ as **Siti (Manager)** Plan purchases â†’ 3 days â†’ Generate â†’
Submit â†’ as **Ah Hock** Approve â†’ Send via WhatsApp â†’ as **Siti** Mark received â†’ **Activity** shows every step â†’
**Plan purchases** shows the forecast accuracy. The order note for the supplier is under **Order history**.

## 8. For the submission

- Screenshot the Replit workspace (showing the project) and the Deployment page (showing the live URL) for the
  Tech & Tools Declaration.
- Make the GitHub repo public, confirm `LICENSE` is Apache-2.0, add the committee as collaborators.

## Resetting the demo

**Settings â†’ Reset demo data** (owner) wipes and reloads the synthetic data, including the opening stock.
From a shell: `cd backend && python -m app.seed.load --reset`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Blank page, `/api/health` works | The web app was not built: run `cd frontend && npm ci && npm run build`. |
| `could not connect to server` | `DATABASE_URL` missing in the **deployment** secrets. |
| Plan button says "no sales history" | Seeding was skipped: run `cd backend && python -m app.seed.load --reset`. |
| AI shows "unavailable" | Approve the Anthropic AI integration for the deployment, or set `ANTHROPIC_API_KEY`. |
| Everything is slow after idle | Autoscale cold start: warm it up (step 6.3). |

## First-time setup and sales upload

- The app opens on a **Sign in** screen (pick a demo user). Signing in as **Ah Hock (Owner)** on a fresh or reset
  database starts the setup: Country (Malaysia) -> Sales history -> Your stock -> Recipes -> Calendar (optional).
  Sales history, stock and recipes are filled in with the demo data and cannot be skipped. Managers and staff are never blocked by it.
- **Settings -> Reset demo data** also resets this wizard, so the demo can be repeated.
- To show the daily routine: **Sales data** -> **Choose a file** (CSV, Excel or PDF) -> check the preview -> **Save these sales**.
  The new days appear under "Covers" and the app's "today" moves forward. A wrong file can be removed and restored.
  If a recording needs a fixed date, set **Settings -> Demo date** first (it wins over the uploaded sales).
- New tables and columns (`sales_imports`, `sales_removals`, `sales_daily_removed`, `sales_drafts`, `sales_daily.import_id`,
  `tenant_setup.sales_*`, `purchase_orders.note_text`) are added automatically on start; no manual migration.
- New Python packages for uploads: `openpyxl` (Excel) and `python-multipart` (file upload); the build installs them from `requirements.txt`.
