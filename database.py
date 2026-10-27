"""database.py - SQLite storage: user accounts + every analysis (per user)."""

import json
import secrets
import sqlite3
from contextlib import contextmanager
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = Path(__file__).with_name("sentiment.db")


@contextmanager
def _conn():
    """Open a connection, commit on success, roll back on error and ALWAYS close it.
    (A plain `with sqlite3.connect()` never closes the connection, which leaks file handles and
    causes 'database is locked' errors on Windows.)"""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'Website',
            label TEXT NOT NULL,
            score INTEGER NOT NULL,
            emotion TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            risk_points INTEGER NOT NULL DEFAULT 0,
            intent TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT 'English',
            aspects TEXT NOT NULL,
            engine TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_an_user ON analyses(user_id, id)")
        # upgrade older databases: add the columns that newer features need
        _add_column(c, "users", "slug", "TEXT")
        _add_column(c, "analyses", "status", "TEXT NOT NULL DEFAULT 'New'")
        _add_column(c, "analyses", "customer_name", "TEXT NOT NULL DEFAULT ''")
        _add_column(c, "analyses", "customer_contact", "TEXT NOT NULL DEFAULT ''")
        c.execute("""CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        _add_column(c, "analyses", "dataset_id", "INTEGER")
        # reviews saved by older versions have no data source: put them in one "Earlier data" source
        for row in c.execute("SELECT DISTINCT user_id FROM analyses WHERE dataset_id IS NULL").fetchall():
            cur = c.execute("INSERT INTO datasets (user_id,name,kind,created_at) VALUES (?,?,?,?)",
                            (row["user_id"], "Earlier data", "earlier", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("UPDATE analyses SET dataset_id=? WHERE user_id=? AND dataset_id IS NULL", (cur.lastrowid, row["user_id"]))
        for row in c.execute("SELECT id FROM users WHERE slug IS NULL OR slug=''").fetchall():
            c.execute("UPDATE users SET slug=? WHERE id=?", (secrets.token_urlsafe(6), row["id"]))
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_slug ON users(slug)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_an_ds ON analyses(dataset_id)")


def _add_column(c, table, column, ddl):
    existing = [r["name"] for r in c.execute(f"PRAGMA table_info({table})")]
    if column not in existing:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


# ---------------- users ----------------
def create_user(name, email, password):
    with _conn() as c:
        cur = c.execute("INSERT INTO users (name,email,password_hash,created_at,slug) VALUES (?,?,?,?,?)",
                        (name, email.lower(), generate_password_hash(password),
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), secrets.token_urlsafe(6)))
        return cur.lastrowid


def verify_user(email, password):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user_by_email(email):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    return dict(row) if row else None


def get_user(user_id):
    with _conn() as c:
        row = c.execute("SELECT id,name,email,slug FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_slug(slug):
    with _conn() as c:
        row = c.execute("SELECT id,name,slug FROM users WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else None


# ---------------- datasets (each CSV = one data source) ----------------
def create_dataset(user_id, name, kind):
    with _conn() as c:
        return c.execute("INSERT INTO datasets (user_id,name,kind,created_at) VALUES (?,?,?,?)",
                         (user_id, name, kind, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))).lastrowid


def get_or_create_dataset(user_id, kind, name):
    with _conn() as c:
        row = c.execute("SELECT id FROM datasets WHERE user_id=? AND kind=?", (user_id, kind)).fetchone()
    return row["id"] if row else create_dataset(user_id, name, kind)


def list_datasets(user_id, kind=None):
    with _conn() as c:
        rows_ = [dict(r) for r in c.execute(
            """SELECT d.id, d.name, d.kind, d.created_at,
                      (SELECT COUNT(*) FROM analyses a WHERE a.dataset_id=d.id) AS count,
                      (SELECT COUNT(*) FROM analyses a WHERE a.dataset_id=d.id AND a.status='New') AS new_count
               FROM datasets d WHERE d.user_id=? ORDER BY d.id DESC""", (user_id,)).fetchall()]
    return [r for r in rows_ if kind is None or r["kind"] == kind]


def dataset_owned(user_id, dataset_id):
    with _conn() as c:
        return c.execute("SELECT 1 FROM datasets WHERE id=? AND user_id=?", (dataset_id, user_id)).fetchone() is not None


def delete_dataset(user_id, dataset_id):
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE dataset_id=? AND user_id=?", (dataset_id, user_id))
        return c.execute("DELETE FROM datasets WHERE id=? AND user_id=?", (dataset_id, user_id)).rowcount


def new_form_count(user_id):
    """New messages from the public feedback link (shown as the red badge on Inbox)."""
    with _conn() as c:
        return c.execute("""SELECT COUNT(*) FROM analyses a JOIN datasets d ON d.id=a.dataset_id
                            WHERE a.user_id=? AND d.kind='form' AND a.status='New'""", (user_id,)).fetchone()[0]


# ---------------- analyses ----------------
def save(user_id, result, channel="Website", created_at=None, customer_name="", customer_contact="", dataset_id=None):
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO analyses (user_id,text,channel,label,score,emotion,risk_level,risk_points,
               intent,priority,language,aspects,engine,created_at,customer_name,customer_contact,dataset_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, result["text"], channel, result["label"], result["score"],
             result["emotion"]["dominant"], result["risk"]["level"], result["risk"]["points"],
             result["intent"], result["priority"], result["language"],
             json.dumps(result["aspects"]), result["engine"],
             created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"), customer_name, customer_contact, dataset_id))
        return cur.lastrowid


def save_many(user_id, results, channel="Website", dataset_id=None):
    """Save many analyses in ONE transaction (fast, and all-or-nothing)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_ = [(user_id, r["text"], channel, r["label"], r["score"], r["emotion"]["dominant"], r["risk"]["level"],
              r["risk"]["points"], r["intent"], r["priority"], r["language"], json.dumps(r["aspects"]), r["engine"],
              now, "", "", dataset_id) for r in results]
    with _conn() as c:
        c.executemany(
            """INSERT INTO analyses (user_id,text,channel,label,score,emotion,risk_level,risk_points,
               intent,priority,language,aspects,engine,created_at,customer_name,customer_contact,dataset_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows_)


def count(user_id):
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM analyses WHERE user_id=?", (user_id,)).fetchone()[0]


def rows(user_id, limit=1000, channel=None, dataset_id=None):
    sql, args = "SELECT * FROM analyses WHERE user_id=?", [user_id]
    if dataset_id is not None:                 # only one uploaded CSV
        sql += " AND dataset_id=?"
        args.append(dataset_id)
    if channel and channel != "All":
        sql += " AND channel=?"
        args.append(channel)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def history(user_id, limit=100, channel=None, dataset_id=None):
    """Everything saved, newest first, with the name of where each review came from."""
    names = {d["id"]: d["name"] for d in list_datasets(user_id)}
    out = []
    for r in rows(user_id, limit, channel, dataset_id):
        r.pop("aspects", None)
        r["source"] = names.get(r.get("dataset_id"), "-")
        out.append(r)
    return out


NEEDS_ACTION = ("status='New' AND (priority LIKE 'P1%' OR priority LIKE 'P2%' OR label='Negative' OR intent IN "
                "('Complaint','Refund request','Cancellation threat','Bug report','Question','Suggestion','Mixed feedback'))")


def inbox(user_id, mode="open", limit=200, dataset_id=None):
    """mode 'open' = reviews that need a reply (praise and plain neutral feedback do not),
    'done' = already Replied or Resolved, 'all' = everything. Urgent (P1) first."""
    sql = ("SELECT id,text,channel,label,score,emotion,risk_level,risk_points,intent,priority,language,status,"
           "customer_name,customer_contact,created_at FROM analyses WHERE user_id=?")
    args = [user_id]
    if dataset_id is not None:
        sql += " AND dataset_id=?"
        args.append(dataset_id)
    if mode == "open":
        sql += " AND " + NEEDS_ACTION
    elif mode == "done":
        sql += " AND status IN ('Replied','Resolved')"
    sql += " ORDER BY (status='Resolved'), priority ASC, id DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def inbox_counts(user_id, dataset_id=None):
    where, args = "user_id=?", [user_id]
    if dataset_id is not None:
        where += " AND dataset_id=?"
        args.append(dataset_id)
    with _conn() as c:
        one = lambda cond: c.execute(f"SELECT COUNT(*) FROM analyses WHERE {where} AND {cond}", args).fetchone()[0]
        return {"open": one(NEEDS_ACTION), "done": one("status IN ('Replied','Resolved')"), "all": one("1=1")}


def status_counts(user_id, dataset_id=None):
    counts = {"New": 0, "Replied": 0, "Resolved": 0}
    with _conn() as c:
        q, args = "SELECT status, COUNT(*) n FROM analyses WHERE user_id=?", [user_id]
        if dataset_id is not None:
            q += " AND dataset_id=?"
            args.append(dataset_id)
        for r in c.execute(q + " GROUP BY status", args):
            counts[r["status"]] = r["n"]
    return counts


def set_status(user_id, review_id, status):
    with _conn() as c:
        return c.execute("UPDATE analyses SET status=? WHERE id=? AND user_id=?", (status, review_id, user_id)).rowcount


def clear(user_id):
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM datasets WHERE user_id=?", (user_id,))


def stats(user_id, channel=None, dataset_id=None):
    data = rows(user_id, 1000, channel, dataset_id)
    total = len(data)
    if total == 0:
        return {"total": 0}

    labels = Counter(r["label"] for r in data)
    emotions = Counter(r["emotion"] for r in data)
    intents = Counter(r["intent"] for r in data if r["intent"])
    languages = Counter(r["language"] for r in data)
    avg = round(sum(r["score"] for r in data) / total)

    aspect_scores = defaultdict(list)
    for r in data:
        for a in json.loads(r["aspects"]):
            aspect_scores[a["name"]].append(a["compound"])
    aspects = sorted(
        ({"name": k, "score": round((sum(v) / len(v) + 1) / 2 * 100), "mentions": len(v),
          "negative": sum(1 for x in v if x <= -0.05), "positive": sum(1 for x in v if x >= 0.05)}
         for k, v in aspect_scores.items()), key=lambda a: a["score"])

    by_channel = defaultdict(list)
    by_day = defaultdict(list)
    for r in data:
        by_channel[r["channel"]].append(r["score"])
        by_day[r["created_at"][:10]].append(r["score"])
    channels = [{"name": k, "score": round(sum(v) / len(v)), "count": len(v)} for k, v in by_channel.items()]
    daily = [{"day": d, "score": round(sum(v) / len(v)), "count": len(v)} for d, v in sorted(by_day.items())][-14:]

    pos_pct = round(100 * labels.get("Positive", 0) / total)
    neg_pct = round(100 * labels.get("Negative", 0) / total)
    return {
        "total": total, "average": avg,
        "positive": labels.get("Positive", 0), "neutral": labels.get("Neutral", 0),
        "negative": labels.get("Negative", 0),
        "index": pos_pct - neg_pct,  # net sentiment index, like NPS: -100 .. +100
        "high_risk": sum(1 for r in data if r["risk_level"] == "High"),
        "urgent": sum(1 for r in data if r["priority"].startswith("P1")),
        "top_emotion": emotions.most_common(1)[0][0],
        "emotions": dict(emotions), "intents": dict(intents), "languages": dict(languages),
        "aspects": aspects, "channels": channels, "daily": daily,
        "recent": [r["score"] for r in reversed(data[:30])],
    }
