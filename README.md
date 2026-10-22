# RestockAI

Smart purchase planning for restaurants and cafés: from ~2 days of manual calculation to a few minutes.
Built for the SDC Hackathon 2026 (XMUM), Domain 2 "Orbyte Smart SME Challenge".

All data in `data/` is **synthetic**. See `IMPLEMENTATION_PLAN.md` for the design and `CLAUDE.md` for coding rules.

## Run locally

```bash
# Backend (http://localhost:8000)
cd backend
python -m venv .venv && .venv\Scripts\activate    # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:5173, proxies /api to :8000)
cd frontend
npm ci
npm run dev
```

Copy `.env.example` to `.env` for local settings. Load the demo data once with `cd backend && python -m app.seed.load --reset`.
Tests: `cd backend && pytest -q`. To deploy on Replit, follow [DEPLOY.md](DEPLOY.md).

## License

Apache-2.0. See `LICENSE`.
