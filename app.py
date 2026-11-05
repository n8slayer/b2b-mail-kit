import csv
import io
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from enrichment import extract_fields, map_columns, parse_contact, scrape_company_site
from generator import generate_draft

load_dotenv()

app = Flask(__name__)

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
MAX_WORKERS = 8

FIT_ORDER = {"Good": 0, "Maybe": 1, "Unlikely": 2, "Unknown": 3}
OUTPUT_COLUMNS = [
    "name", "email", "company", "domain", "fit", "fit_reason", "subject", "body",
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY is not set (check your .env file)"}), 400

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        text = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        reader.fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
        raw_rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as e:
        return jsonify({"error": f"Could not parse CSV: {e}"}), 400

    column_map = map_columns(reader.fieldnames or [], raw_rows)
    if not column_map.get("email"):
        return jsonify({"error": "Could not find a column with email addresses in this CSV"}), 400

    rows = [extract_fields(r, column_map) for r in raw_rows]
    rows = [r for r in rows if r["email"]]
    if not rows:
        return jsonify({"error": "No rows with a usable email address found"}), 400

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "processing", "done": 0, "total": len(rows), "results": []}

    thread = threading.Thread(target=_run_job, args=(job_id, rows), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "total": len(rows)})


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    payload = {"status": job["status"], "done": job["done"], "total": job["total"]}
    if job["status"] == "done":
        results = sorted(job["results"], key=lambda r: FIT_ORDER.get(r["fit"], 9))
        payload["results"] = results
    return jsonify(payload)


@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Job not ready"}), 404

    results = sorted(job["results"], key=lambda r: FIT_ORDER.get(r["fit"], 9))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=OUTPUT_COLUMNS)
    writer.writeheader()
    for row in results:
        writer.writerow({k: row.get(k, "") for k in OUTPUT_COLUMNS})

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=osprey-outreach-{job_id[:8]}.csv"},
    )


def _run_job(job_id: str, rows: list[dict]):
    def process(row: dict) -> dict:
        contact = parse_contact(row)
        site_text = None
        if not contact["is_free_email"] and contact["domain"]:
            site_text = scrape_company_site(contact["domain"])

        draft = generate_draft(contact, site_text)

        with JOBS_LOCK:
            JOBS[job_id]["done"] += 1

        return {**contact, **draft}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(process, rows))

    with JOBS_LOCK:
        JOBS[job_id]["results"] = results
        JOBS[job_id]["status"] = "done"


if __name__ == "__main__":
    app.run(debug=True, port=5050)
