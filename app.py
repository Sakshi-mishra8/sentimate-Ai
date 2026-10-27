"""app.py - Flask backend: website pages, login system, public feedback form and REST API."""

import csv
import io
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path

from flask import (Flask, Response, abort, jsonify, redirect, render_template, request,
                   session, url_for)

import database
import insights
import ml_model
import sentiment_engine as engine

def _secret_key():
    """SECRET_KEY from the environment, else a random key saved once in .secret_key.
    (A fixed default key in the source code would let anyone forge a login cookie.)"""
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    path = Path(__file__).with_name(".secret_key")
    try:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        key = secrets.token_hex(32)
        path.write_text(key)
        return key
    except OSError:                                   # read-only disk: fine, sessions just reset on restart
        return secrets.token_hex(32)


app = Flask(__name__)
app.secret_key = _secret_key()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0          # never let the browser keep old CSS/JS
APP_VERSION = "Version 9: bulk upload fixes"
app.jinja_env.globals["app_version"] = APP_VERSION
app.jinja_env.globals["v"] = int(time.time())        # changes at every start: forces fresh files
database.init_db()
ml_model.get_model()  # trains the ML model on first start (takes about 1 second)

CHANNELS = ["Feedback form", "Website", "Amazon", "Play Store", "Social media", "Email"]
TEXT_COLUMNS = ("text", "review", "comment", "feedback", "message", "description")
STATUSES = ("New", "Replied", "Resolved")
MAX_BATCH_ROWS = 300
MAX_REVIEW_CHARS = 3000
# Column-name words that mean "this is NOT the review text" (reviewer_name, Review Title, rating, ...)
NOT_TEXT_WORDS = {"name", "id", "user", "username", "author", "reviewer", "title", "summary", "subject", "rating",
                  "score", "stars", "star", "date", "time", "product", "email", "phone", "url", "link", "helpful",
                  "count", "verified"}

# The Inbox shows ONLY the CSV you uploaded in this login. It is kept in the signed session cookie
# (not in server memory), so it also works when the site runs with several worker processes.

# ------------------------------------------------------------------ small anti-spam limiter
_hits = defaultdict(deque)


def rate_limited(key, limit, window_seconds):
    now = time.time()
    q = _hits[key]
    while q and q[0] < now - window_seconds:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


# ------------------------------------------------------------------ auth helpers
def login_required(page=False):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if "uid" not in session:
                if page:
                    return redirect(url_for("login"))
                return jsonify(error="Please log in again."), 401
            return fn(*a, **kw)
        return wrapper
    return deco


def uid():
    return session["uid"]


def _channel(value):
    return value if value in CHANNELS else "Website"


def current_ds(value=None):
    """Optional ?ds=ID filter (one uploaded CSV, or the customer feedback form source).
    No ds given -> all reviews (Overview, History work as always). Unknown ds -> nothing."""
    raw = value if value is not None else request.args.get("ds", type=int)
    if raw is None:
        return None
    return raw if raw and database.dataset_owned(uid(), raw) else -1


# ------------------------------------------------------------------ pages
@app.get("/")
def landing():
    return render_template("landing.html", logged_in="uid" in session)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if rate_limited(("login", request.remote_addr), 10, 600):
            return render_template("auth.html", mode="login", error="Too many attempts. Please wait a few minutes."), 429
        user = database.verify_user(request.form.get("email", "").strip(), request.form.get("password", ""))
        if user:
            session.clear()                                   # fresh login = fresh session = empty Inbox
            session["uid"], session["name"] = user["id"], user["name"]
            return redirect(url_for("dashboard"))
        error = "Wrong email or password."
    return render_template("auth.html", mode="login", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if len(name) < 2:
            error = "Enter your name or business name."
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            error = "Enter a valid email address."
        elif len(pw) < 6:
            error = "Password must have at least 6 characters."
        elif database.get_user_by_email(email):
            error = "This email is already registered. Log in instead."
        else:
            try:
                new_id = database.create_user(name, email, pw)
            except sqlite3.IntegrityError:                    # two people registered the same email at the same moment
                error = "This email is already registered. Log in instead."
            else:
                session.clear()
                session["uid"], session["name"] = new_id, name
                return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register", error=error)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.get("/app")
@login_required(page=True)
def dashboard():
    return render_template("app.html", name=session.get("name", ""), channels=CHANNELS)


@app.get("/report")
@login_required(page=True)
def report():
    from datetime import datetime
    ds = current_ds()
    st = database.stats(uid(), None, ds)
    return render_template("report.html", name=session.get("name", ""), st=st,
                           ins=insights.compute(uid(), None, ds), summ=insights.summary(uid(), None, ds),
                           now=datetime.now().strftime("%d %B %Y, %H:%M"))


# ------------------------------------------------------------------ PUBLIC: customer feedback form
@app.route("/f/<slug>", methods=["GET", "POST"])
def public_form(slug):
    """Your customers open this link and write feedback. The AI analyzes it and it lands in your inbox."""
    owner = database.get_user_by_slug(slug)
    if not owner:
        abort(404)
    if request.method == "GET":
        return render_template("feedback.html", business=owner["name"])

    data = request.get_json(silent=True) or {}
    if data.get("website"):                       # hidden "honeypot" field: bots fill it, humans do not
        return jsonify(ok=True)
    text = (data.get("text") or "").strip()
    if len(text) < 5:
        return jsonify(error="Please write at least a few words."), 400
    if len(text) > 2000:
        return jsonify(error="Please keep your feedback under 2000 characters."), 400
    if rate_limited(("form", request.remote_addr), 5, 600):
        return jsonify(error="Too many messages. Please try again in a few minutes."), 429

    result = engine.analyze(text)
    database.save(owner["id"], result, "Feedback form",
                  customer_name=(data.get("name") or "").strip()[:80],
                  customer_contact=(data.get("contact") or "").strip()[:120],
                  dataset_id=database.get_or_create_dataset(owner["id"], "form", "Customer feedback form"))
    return jsonify(ok=True)


@app.post("/api/try")
def try_it():
    """Public try-it box on the landing page. Analyzes real text, saves nothing."""
    if rate_limited(("try", request.remote_addr), 20, 600):
        return jsonify(error="Too many tries. Please wait a few minutes or create an account."), 429
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if len(text) < 3:
        return jsonify(error="Paste a customer review first."), 400
    r = engine.analyze(text[:1500])
    return jsonify({k: r[k] for k in ("label", "score", "emotion", "aspects", "priority", "intent", "reply", "language", "mixed", "sarcasm", "explain")})


# ------------------------------------------------------------------ API (login required)
@app.get("/api/status")
@login_required()
def status():
    me = database.get_user(uid())
    return jsonify(transformer=engine.transformer_available(),
                   model=ml_model.model_info(), channels=CHANNELS,
                   feedback_path=url_for("public_form", slug=me["slug"]), version=APP_VERSION,
                   new_count=database.new_form_count(uid()))


@app.post("/api/analyze")
@login_required()
def analyze_one():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="Enter some customer feedback first."), 400
    if len(text) > 3000:
        return jsonify(error="Feedback is too long. Keep it under 3000 characters."), 400
    result = engine.analyze(text, data.get("engine", "ensemble"))
    if data.get("save"):
        ds = database.get_or_create_dataset(uid(), "manual", "Manual reviews")
        result["id"] = database.save(uid(), result, _channel(data.get("channel")), dataset_id=ds)
        result["dataset_id"] = ds
    return jsonify(result)


@app.post("/api/reply")
@login_required()
def reply():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="Enter some customer feedback first."), 400
    return jsonify(insights.reply_studio(engine.analyze(text), data.get("tone", "Professional")))


@app.get("/api/inbox")
@login_required()
def get_inbox():
    mode = request.args.get("filter", "open")
    mode = mode if mode in ("open", "all", "done") else "open"
    ds = session.get("inbox_ds")
    source = next((d for d in database.list_datasets(uid(), "csv") if d["id"] == ds), None) if ds else None
    if not source:                                            # nothing uploaded in this login: empty Inbox
        session.pop("inbox_ds", None)
        return jsonify(source=None, counts={"New": 0, "Replied": 0, "Resolved": 0},
                       summary={"open": 0, "done": 0, "all": 0}, rows=[])
    return jsonify(source={"id": source["id"], "name": source["name"], "count": source["count"]},
                   counts=database.status_counts(uid(), ds), summary=database.inbox_counts(uid(), ds),
                   rows=database.inbox(uid(), mode, 200, ds))


@app.post("/api/inbox/clear")
@login_required()
def clear_inbox():
    """Empties the Inbox view only. Nothing is deleted: the reviews stay in History and the CSV dashboard."""
    session.pop("inbox_ds", None)
    return jsonify(ok=True)


@app.post("/api/review/<int:review_id>/status")
@login_required()
def set_review_status(review_id):
    new = (request.get_json(silent=True) or {}).get("status")
    if new not in STATUSES:
        return jsonify(error="Invalid status."), 400
    if not database.set_status(uid(), review_id, new):
        return jsonify(error="Review not found."), 404
    return jsonify(ok=True)


def _read_csv_text(raw):
    """bytes -> text. Excel often saves CSV as cp1252, so try UTF-8 first, then Windows encodings."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def _pick_text_column(fields, sample):
    """Index of the column that holds the review text.
    1) a column named exactly text/review/comment/feedback/message/description
    2) a column whose name contains one of those words, but is not a name/id/title/rating column
    3) otherwise the column with the longest text."""
    low = [f.strip().lower() for f in fields]
    for key in TEXT_COLUMNS:
        if key in low:
            return low.index(key)
    for i, name in enumerate(low):
        words = set(re.split(r"[^a-z0-9]+", name))
        if any(k in name for k in TEXT_COLUMNS) and not (words & NOT_TEXT_WORDS):
            return i

    def avg_len(i):
        vals = [r[i].strip() for r in sample if i < len(r) and r[i].strip()]
        return sum(len(v) for v in vals) / len(vals) if vals else 0
    return max(range(len(fields)), key=avg_len)


@app.post("/api/batch")
@login_required()
def analyze_batch():
    file = request.files.get("file")
    eng = request.form.get("engine", "ensemble")
    channel = _channel(request.form.get("channel"))
    name = (file.filename or "") if file else ""
    if not file or not name:
        return jsonify(error="Choose a .csv file first."), 400
    if name.lower().endswith((".xlsx", ".xls")):
        return jsonify(error="Excel files cannot be read directly. In Excel use File > Save As > CSV UTF-8, then upload that file."), 400
    if not name.lower().endswith(".csv"):
        return jsonify(error="Upload a .csv file."), 400

    raw = file.read()
    if b"\x00" in raw[:8192]:                                      # real CSV is text; this is a binary file (e.g. .xlsx renamed)
        return jsonify(error="This is not a text CSV file (it looks like an Excel or binary file). In Excel use Save As > CSV UTF-8."), 400
    content = _read_csv_text(raw).lstrip("\ufeff")
    if content[:4].lower() == "sep=":                                # Excel writes a first line like  sep=;
        content = content.split("\n", 1)[1] if "\n" in content else ""
    if not content.strip():
        return jsonify(error="The file is empty. Save it again as CSV (UTF-8) with a header row such as: review"), 400

    head = content.split("\n", 1)[0]                               # comma, semicolon, tab or pipe: the one most used in the header
    delim = max(",;\t|", key=head.count) if any(d in head for d in ",;\t|") else ","
    try:
        rows = [r for r in csv.reader(io.StringIO(content), delimiter=delim) if any(c.strip() for c in r)]
    except csv.Error as exc:
        return jsonify(error=f"The CSV could not be read ({exc}). Check that quotes are closed, or save it again as CSV (UTF-8)."), 400
    if not rows:
        return jsonify(error="The CSV has no rows."), 400

    header, body = rows[0], rows[1:]
    # a one-column file whose first line is already a review (no header row): keep that line as data
    headerless = (len(header) == 1 and len(header[0].split()) >= 3
                  and not any(k in header[0].lower() for k in TEXT_COLUMNS))
    if headerless:
        header, body = ["review"], rows
    fields = [(f.strip() or f"column {i + 1}") for i, f in enumerate(header)]

    if len(fields) == 1:                                            # single column: rejoin text that has unquoted commas
        glue = ", " if delim == "," else delim
        column = fields[0]
        all_texts = [glue.join(c.strip() for c in r).strip() for r in body]
    else:
        idx = _pick_text_column(fields, body[:50])
        column = fields[idx]
        all_texts = [(r[idx].strip() if idx < len(r) else "") for r in body]
    all_texts = [t[:MAX_REVIEW_CHARS] for t in all_texts if t]
    if not all_texts:
        return jsonify(error=f'No review text found in column "{column}". Put the reviews in a column named review.'), 400

    texts = all_texts[:MAX_BATCH_ROWS]
    results = [engine.analyze(t, eng) for t in texts]               # analyze first: a failure leaves no half-saved file

    ds_name = os.path.basename(name)[:80]
    ds = database.create_dataset(uid(), ds_name, "csv")             # every CSV is its own separate data source
    try:
        database.save_many(uid(), results, channel, ds)
    except Exception:
        database.delete_dataset(uid(), ds)
        raise
    session["inbox_ds"] = ds                                        # ...and the Inbox now shows exactly this file

    counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for r in results:
        counts[r["label"]] += 1
    out = [{"text": r["text"][:160], "label": r["label"], "score": r["score"], "emotion": r["emotion"]["dominant"],
            "risk": r["risk"]["level"], "intent": r["intent"], "language": r["language"]} for r in results]
    return jsonify(column=column, count=len(out), counts=counts, average=round(sum(r["score"] for r in results) / len(results)),
                   rows=out, dataset_id=ds, dataset_name=ds_name, rows_in_file=len(all_texts),
                   truncated=len(all_texts) > MAX_BATCH_ROWS, limit=MAX_BATCH_ROWS, headerless=headerless)


@app.get("/api/stats")
@login_required()
def get_stats():
    return jsonify(database.stats(uid(), request.args.get("channel"), current_ds()))


@app.get("/api/insights")
@login_required()
def get_insights():
    return jsonify(insights.compute(uid(), request.args.get("channel"), current_ds()))


@app.get("/api/summary")
@login_required()
def get_summary():
    return jsonify(insights.summary(uid(), request.args.get("channel"), current_ds()))


@app.post("/api/chat")
@login_required()
def chat():
    body = request.get_json(silent=True) or {}
    q = (body.get("question") or "").strip()
    if not q:
        return jsonify(error="Type a question first."), 400
    out = insights.chat(uid(), q[:500], None, current_ds(body.get("ds")), (body.get("prev") or "")[:500])
    out["answer"] += out.pop("note", "")
    return jsonify(out)


@app.get("/api/history")
@login_required()
def get_history():
    return jsonify(database.history(uid(), 500, request.args.get("channel"), current_ds()))


def _csv_safe(value):
    """Customers can type anything into the public form. A cell that starts with = + - @ is run as a
    formula by Excel, so we put an apostrophe in front of it."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@app.get("/api/export.csv")
@login_required()
def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "channel", "customer", "contact", "review", "sentiment", "score", "emotion", "intent",
                "priority", "churn_risk", "language", "status"])
    for r in database.history(uid(), 1000, None, current_ds()):
        w.writerow([r["created_at"], r["channel"], _csv_safe(r["customer_name"]), _csv_safe(r["customer_contact"]), _csv_safe(r["text"]), r["label"],
                    r["score"], r["emotion"], r["intent"], r["priority"], r["risk_level"], r["language"], r["status"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sentiment_report.csv"})


@app.get("/api/datasets")
@login_required()
def get_datasets():
    return jsonify(database.list_datasets(uid(), request.args.get("kind")))


@app.post("/api/dataset/<int:dataset_id>/delete")
@login_required()
def delete_dataset(dataset_id):
    if not database.delete_dataset(uid(), dataset_id):
        return jsonify(error="Data source not found."), 404
    if session.get("inbox_ds") == dataset_id:
        session.pop("inbox_ds", None)
    return jsonify(ok=True)


@app.post("/api/clear")
@login_required()
def clear_all():
    database.clear(uid())
    session.pop("inbox_ds", None)
    return jsonify(ok=True)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="File is too large (max 2 MB). Split it into smaller files."), 413


@app.errorhandler(500)
def server_error(_):
    # The page script expects JSON; an HTML error page only showed "Something went wrong".
    if request.path.startswith("/api/") or request.method == "POST":
        return jsonify(error="The server hit a problem with this request. The reason is printed in the black window."), 500
    return "Server error. See the black window for details.", 500


if __name__ == "__main__":
    # HOST=0.0.0.0 lets other devices on your Wi-Fi open the feedback link.
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("DEBUG") == "1")
