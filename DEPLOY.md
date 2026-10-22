# Deploying RestockIQ on Replit

Replit is compulsory for this hackathon (hosting + PostgreSQL + the Replit-managed Claude integration).
One process serves everything: FastAPI answers `/api/*` and serves the built web app at `/`.

> The Replit config files (`.replit`, `replit.nix`) were written from Replit's documented format but could not be
> run on the author's machine. If a step below differs on screen, trust Replit's UI and adjust the file.

## 1. Import the repository

1. On replit.com choose **Create App → Import from GitHub** and pick this repo (it can stay private while you set up).
2. Replit reads `.replit`: Python 3.11, Node 20, PostgreSQL 16.
3. In the workspace **Tools → Shell**, run `python --version`. It must say 3.11.x. (The author's laptop uses 3.13;
   the code works on both, but Replit should be 3.11 to match the declaration.)

## 2. Add the database

1. **Tools → Database → PostgreSQL** (create it). Replit sets `DATABASE_URL` for you.
2. Nothing else is needed: the app creates its tables on start and `python -m app.seed.load --if-empty` loads the
   synthetic demo data the first time (about 10 seconds, it also measures the safety buffers).

## 3. Secrets (**Tools → Secrets**)

Set these in the workspace **and again in the Deployment** (Deployment secrets are separate):

| Secret | Value |
|---|---|
| `TODAY` | optional. `2026-10-22` pins the demo date. Leave it out and use **Settings → Demo date** instead. |
| `LLM_MODEL` | optional. Defaults to `claude-haiku-5-5`. |
| `ANTHROPIC_API_KEY` | optional. Only if you do **not** use the Replit AI integration (step 4). |

Never put a real key in the repo. `.env.example` lists the names only.

## 4. AI (Claude via Replit)

1. **Tools → AI Integrations → Anthropic**, approve it. Replit then provides `AI_INTEGRATIONS_ANTHROPIC_API_KEY`
   and `AI_INTEGRATIONS_ANTHROPIC_BASE_URL` to the app, which `backend/app/ai/llm.py` reads first.
2. Check: sign in as Siti (manager), **Inventory → ⚡ Quick add from a note → Use the example → Read my note**.
   If it says "AI unavailable, enter manually", the integration is not approved in this environment
   (workspace vs deployment) or the model name is not allowed. The rest of the app keeps working without AI.

## 5. Run it in the workspace

Press **Run**. It builds the web app (`cd frontend && npm ci && npm run build`), installs the Python packages,
seeds the database if empty and starts `uvicorn` on `$PORT`. Open the preview and test the journey (step 7).

## 6. Publish (Autoscale deployment)

1. **Publish → Autoscale**. Build command and run command come from `.replit`:
   - build: `cd frontend && npm ci && npm run build && cd ../backend && pip install -r requirements.txt`
   - run: `cd backend && python -m app.seed.load --if-empty && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Add the deployment secrets (step 3) and publish.
3. **Warm it before judging:** Autoscale sleeps when idle. Open the `*.replit.app` URL a few minutes before a demo,
   sign in, press **Generate plan** once. The first request after a sleep takes a few seconds.
4. Open the URL in an **incognito window** to prove it works for a stranger.

## 7. Journey check (about 3 minutes)

As **Ah Hock (Owner)** confirm the one-time stock setup → as **Siti (Manager)** Plan purchases → 3 days → Generate →
Submit → as **Ah Hock** Approve → Send via WhatsApp → as **Siti** Mark received → **Activity** shows every step →
**Dashboard** shows time saved and the 13% vs 28% accuracy card.

## 8. For the submission

- Screenshot the Replit workspace (showing the project) and the Deployment page (showing the live URL) for the
  Tech & Tools Declaration.
- Make the GitHub repo public, confirm `LICENSE` is Apache-2.0, add the committee as collaborators.

## Resetting the demo

**Settings → Reset demo data** (owner) wipes and reloads the synthetic data, including the opening stock.
From a shell: `cd backend && python -m app.seed.load --reset`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Blank page, `/api/health` works | The web app was not built: run `cd frontend && npm ci && npm run build`. |
| `could not connect to server` | `DATABASE_URL` missing in the **deployment** secrets. |
| Plan button says "no sales history" | Seeding was skipped: run `cd backend && python -m app.seed.load --reset`. |
| AI shows "unavailable" | Approve the Anthropic AI integration for the deployment, or set `ANTHROPIC_API_KEY`. |
| Everything is slow after idle | Autoscale cold start: warm it up (step 6.3). |
