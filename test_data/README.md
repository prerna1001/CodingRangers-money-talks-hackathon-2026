# Test data

Ready-to-upload CSVs for exercising the pipeline through the dashboard.
Generated deterministically by `backend/data/generate.py`, so every file
here is guaranteed to parse and to produce a known-correct answer.

Regenerate any of them with, e.g.:

```bash
cd backend
.venv/Scripts/python.exe -m data.generate --dataset saas --output-dir ../test_data/01_saas_clean
```

## The datasets

| Folder | Company | What it exercises |
|---|---|---|
| `01_saas_clean` | B2B SaaS | The primary demo. Enterprise expansion across three named accounts, plus cloud hosting rising with usage. |
| `02_ecommerce_clean` | E-commerce | Gross sales up while refunds move separately — exercises the margin story. |
| `03_healthcare_clean` | Healthcare clinic | Patient revenue roughly flat while billing adjustments and contractor labor move. |
| `04_saas_stress_injection_duplicates` | B2B SaaS | **Adversarial.** Contains a prompt-injection string in a memo field and a duplicate transaction. Expect the injection to be quarantined and the duplicate flagged as a data-quality warning. |
| `05_ecommerce_large_refund` | E-commerce | A large refund distorting the revenue picture. |
| `06_healthcare_missing_counterparty` | Healthcare clinic | ~25% of revenue rows are missing a customer name. Expect a data-quality warning and a reduced quality score, not a failed run. |

Each folder has three files:

- **`transactions.csv`** — transaction-level rows. This is the one to upload in the dashboard.
- **`period_summaries.csv`** — the account-level monthly summary. Optional; upload it too (via the API) if you want the reconciliation gate to do real work.
- **`manifest.json`** — the ground truth: which drivers were injected and what the expected variances are. This is what `backend/eval/run.py` scores the engine against.

## Using them

**In the dashboard** (http://localhost:5173): upload any `transactions.csv`.
Periods are inferred from the data (the two most recent), so you don't need
to tell it which months to compare.

**Against the API directly:**

```bash
# Upload transactions
curl -X POST -F "file=@test_data/01_saas_clean/transactions.csv" \
  http://localhost:8000/api/upload

# Analyze (use the file_id from the response)
curl -X POST -H "Content-Type: application/json" \
  -d '{"transaction_file_ids":["<file_id>"]}' \
  http://localhost:8000/api/analyze

# Poll until it returns 200 instead of 202
curl http://localhost:8000/api/runs/<run_id>
```

Uploading **no** file and posting `{}` to `/api/analyze` runs the built-in
demo fixture instead — useful for a quick smoke test.

## CSV format notes

A transactions file needs at minimum a **date** and an **amount** column.
Everything else is optional and improves the analysis:

| Column | Aliases accepted | Notes |
|---|---|---|
| `posted_date` | `date`, `transaction_date` | ISO `YYYY-MM-DD` preferred. `MM/DD/YYYY`, `DD/MM/YYYY` and `Aug 5, 2026` also parse — but note `05-08-2026` is genuinely ambiguous and is read as **May 8**, so prefer ISO. |
| `amount` | `value` | `$20,000.00` and `(500)` for negatives both work. |
| `period_id` | `period`, `month` | Inferred from the date if absent. |
| `account_id` / `account_name` | `account_code` / `account` | Drives account-level variance. |
| `account_type` | `type` | One of `revenue`, `cogs`, `opex`, `asset`, `liability`, `equity`. Defaults to `opex`. |
| `counterparty_name` | `customer`, `vendor`, `name` | Drives driver attribution — without it you get variances but no "who caused it". |
| `category` | `class` | |
| `memo` | `description`, `notes` | Scanned for prompt-injection attempts. |

**The data must span at least two periods** — the whole product is a
period-over-period comparison, so a single month has nothing to compare against.
