# Forecast audit harness

Test bench used to check the RestockAI forecaster (`backend/app/engine`). Everything here is **simulated, synthetic data**. No real restaurant data was used or exists. The plain-language summary is in [FORECAST_AUDIT.md](FORECAST_AUDIT.md); this file explains the scripts.

Nothing in `research/` is imported by the app. Delete the folder and the product still runs.

## Why a separate generator

`world.py` is deliberately **not** the app's own data generator (`data/generate.py`). It uses different drivers (smoother and noisier), so a good score cannot come only from the model matching the way the demo data was made. It builds a "messy restaurant" with: weekday shapes by dish category, holidays and owner-labelled periods, unknown events, outlier days, a level shift or growth trend, closed weekdays, missing days, stock-out censoring, discontinued and new dishes. It returns both what the owner would see (`q`) and what customers really wanted (`q_true`), which gives a "noise floor" (the `oracle` column).

## Files

| File | What it does |
|---|---|
| `world.py` | The independent messy-restaurant generator |
| `variant.py` | A lab copy of `forecast.py` with on/off switches, so each possible fix is tested alone |
| `audit_main.py` | Audit 1: app vs 6 standard methods (daily-total error, bias, holiday days, by horizon) and whether the safety buffers hold on unseen days |
| `audit_variants.py` | Audit 2: which parts of the forecaster earn their place, and which small changes would help |
| `audit_buffers.py` | Audit 3: is "90% buffer" enough about 90% of the time on days it was not measured on? Compares the current method with conformal, recency and pooled corrections |
| `audit_history.py` | Audit 4: how much sales history is needed (14 to 540 days) |
| `audit_cold.py` | Audit 5: how to treat the weekday pattern on a very short history |
| `audit_repo.py`, `audit_repo_buffers.py`, `audit_repo_variants.py` | The same comparisons on the app's own synthetic data (`data/*.csv`) |
| `check_variant.py` | Sanity check that the lab copy matches the app's engine |
| `edge_cases.py` | Awkward-data checks (random closures, missing days, very short history, catering spike, no calendar, data hole, new calendar label). Prints results; no saved output file |
| `results/` | Saved outputs. `v2_*` are the corrected runs on simulated restaurants; `repo_*` are runs on the app's own data |

## How to run

Needs Python with `numpy pandas statsmodels scikit-learn scipy` (see `requirements-audit.txt`). Run from this folder. The scripts find `backend/` themselves.

```bash
python audit_main.py                  # all 8 restaurant types
python audit_main.py typical calm     # chosen types only
```

Useful settings (environment variables):

- `AUDIT_SEEDS=0,1` : random seeds per restaurant type (default `0,1,2`). The saved `v2_main` and `v2_buffers` runs used `0,1`.
- `VARIANT_SET=final` : the smaller list of variants in `audit_variants.py`.

A full `audit_main.py` run took about 6 minutes on a laptop using several worker processes. After any run, check that no stray `python` worker processes are left over.

`edge_cases.py` imports the app engine, so run it with the project venv and `PYTHONPATH=backend`.

## Reading the numbers

- **WAPE** = total absolute error divided by total actual sales (lower is better). Measured on daily totals of 7-day plans over the last 52 weeks. Each plan only sees the past.
- **Coverage** = how often the purchased amount (need plus safety buffer) was enough on days the buffer was not measured on. Target 80/90/95%.
- **Shortage / leftover** = how much was too little / too much, as % of the need.

## Limits

- Simulated data can only show that the method is sensible and where it is fragile. It cannot show accuracy on a real kitchen.
- Seeds are few (2 per type for the saved runs), so differences of about 0.3 points or less between methods are not meaningful.
- `results/v2_variants.txt` is the complete run of `audit_variants.py` with `VARIANT_SET=final`: 10 restaurant types x 3 seeds = 30 simulated restaurants x 10 variants, 387 s. (An earlier run of the same script crashed in its last section and was replaced; the script has been fixed.) The script also writes `results_variants.json` next to itself; that raw dump is not kept in git.
- In that table, `engine (today)` means the forecaster as it was before the two fixes, `robust` is a lab version with only the closed-day fix, and `fixed engine` is the current engine. `repo_variants_output.txt` is the same comparison on the app's own demo data.
