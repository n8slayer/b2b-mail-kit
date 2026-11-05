# Osprey Outreach

Upload a B2B contact CSV, get each contact enriched from their company's
public website, judged for fit against Osprey Systems' ideal customer
profile, and a personalized cold-email subject + body drafted. Review and
copy/paste from the browser — this tool never sends email itself.

## Setup

```
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in ANTHROPIC_API_KEY
```

## Run

```
python app.py
```

Open http://localhost:5050 and upload a CSV. `sample_input.csv` is included
as an example (required column: `email`; optional: `name`, `company`).

## Notes

- Company info comes from free web scraping of the contact's email domain
  (homepage + `/about`), not a paid enrichment API.
- Every contact gets a draft regardless of fit (Good/Maybe/Unlikely/Unknown)
  — fit is a label to filter/skip by, not a gate.
- Batches of ~50-300 contacts are processed concurrently (8 workers) with a
  live progress bar.
