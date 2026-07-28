"""
Lightweight persistence layer.

Uses SQLite by default (zero-config, fine for a single EC2 free-tier instance).
Swap `DB_PATH` for an EFS-mounted path or migrate to DynamoDB if you need
multi-instance / auto-scaling durability later -- the storage interface
(`add_record`, `get_recent`) is the only thing that would need to change.
"""
import sqlite3
import os
from datetime import datetime
from typing import List
from .models import InvocationRecord

DB_PATH = os.environ.get("RISK_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "risk.db"))


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_chars INTEGER,
            response_chars INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms REAL,
            cost_usd REAL,
            refusal_flag INTEGER,
            uncertainty_flag INTEGER,
            response_preview TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            tickers_json TEXT NOT NULL,
            weights_json TEXT NOT NULL,
            benchmark TEXT NOT NULL,
            period TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(session_id, name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            user_agent TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def record_usage_event(kind: str):
    conn = _connect()
    conn.execute("INSERT INTO usage_events (kind, timestamp) VALUES (?, ?)", (kind, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def count_usage_today(kind: str) -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM usage_events WHERE kind = ? AND timestamp >= datetime('now', 'start of day')",
        (kind,)
    ).fetchone()
    conn.close()
    return row["c"]


def record_visit(visitor_id: str, user_agent: str = ""):
    conn = _connect()
    conn.execute(
        "INSERT INTO visits (visitor_id, timestamp, user_agent) VALUES (?, ?, ?)",
        (visitor_id, datetime.now().isoformat(), user_agent[:300]),
    )
    conn.commit()
    conn.close()


def get_visit_stats():
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) AS c FROM visits").fetchone()["c"]
    unique = conn.execute("SELECT COUNT(DISTINCT visitor_id) AS c FROM visits").fetchone()["c"]
    last_7 = conn.execute("""
        SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS visits, COUNT(DISTINCT visitor_id) AS unique_visitors
        FROM visits
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY day ORDER BY day
    """).fetchall()
    conn.close()
    return {
        "total_visits": total,
        "unique_visitors": unique,
        "last_7_days": [dict(r) for r in last_7],
    }


def save_portfolio(session_id: str, name: str, tickers: List[str], weights: dict, benchmark: str, period: str):
    import json
    conn = _connect()
    conn.execute("""
        INSERT INTO portfolios (session_id, name, tickers_json, weights_json, benchmark, period, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, name) DO UPDATE SET
            tickers_json=excluded.tickers_json, weights_json=excluded.weights_json,
            benchmark=excluded.benchmark, period=excluded.period, created_at=excluded.created_at
    """, (session_id, name, json.dumps(tickers), json.dumps(weights), benchmark, period, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def list_portfolios(session_id: str):
    conn = _connect()
    rows = conn.execute(
        "SELECT name, benchmark, period, created_at FROM portfolios WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_portfolio(session_id: str, name: str):
    import json
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM portfolios WHERE session_id = ? AND name = ?", (session_id, name)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "name": row["name"], "tickers": json.loads(row["tickers_json"]),
        "weights": json.loads(row["weights_json"]), "benchmark": row["benchmark"], "period": row["period"],
    }


def delete_portfolio(session_id: str, name: str):
    conn = _connect()
    conn.execute("DELETE FROM portfolios WHERE session_id = ? AND name = ?", (session_id, name))
    conn.commit()
    conn.close()


def add_record(rec: InvocationRecord) -> int:
    conn = _connect()
    cur = conn.execute("""
        INSERT INTO invocations
        (session_id, timestamp, model, prompt_chars, response_chars,
         input_tokens, output_tokens, latency_ms, cost_usd,
         refusal_flag, uncertainty_flag, response_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rec.session_id, rec.timestamp.isoformat(), rec.model,
        rec.prompt_chars, rec.response_chars, rec.input_tokens,
        rec.output_tokens, rec.latency_ms, rec.cost_usd,
        int(rec.refusal_flag), int(rec.uncertainty_flag), rec.response_preview
    ))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_recent(session_id: str, limit: int = 200) -> List[InvocationRecord]:
    conn = _connect()
    rows = conn.execute("""
        SELECT * FROM invocations WHERE session_id = ?
        ORDER BY id DESC LIMIT ?
    """, (session_id, limit)).fetchall()
    conn.close()
    records = [
        InvocationRecord(
            id=r["id"], session_id=r["session_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]), model=r["model"],
            prompt_chars=r["prompt_chars"], response_chars=r["response_chars"],
            input_tokens=r["input_tokens"], output_tokens=r["output_tokens"],
            latency_ms=r["latency_ms"], cost_usd=r["cost_usd"],
            refusal_flag=bool(r["refusal_flag"]), uncertainty_flag=bool(r["uncertainty_flag"]),
            response_preview=r["response_preview"]
        ) for r in rows
    ]
    records.reverse()  # chronological order
    return records
