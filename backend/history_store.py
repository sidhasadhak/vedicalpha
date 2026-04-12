"""
history_store.py
Stores prediction history and alerts in a local SQLite database.
"""

import sqlite3
import json
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "vyapar_ratna.db"


class HistoryStore:

    def __init__(self):
        self._init_db()

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def _init_db(self):
        with self._conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker    TEXT NOT NULL,
                    horizon   TEXT,
                    signal    TEXT,
                    confidence INTEGER,
                    score     REAL,
                    date      TEXT,
                    created   TEXT,
                    payload   TEXT
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker    TEXT,
                    condition TEXT,
                    threshold REAL,
                    active    INTEGER DEFAULT 1,
                    created   TEXT,
                    payload   TEXT
                )
            """)
            con.commit()

    def save(self, ticker: str, horizon: str, result: dict, target: date):
        with self._conn() as con:
            con.execute(
                """INSERT INTO predictions
                   (ticker, horizon, signal, confidence, score, date, created, payload)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    ticker, horizon,
                    result["signal"],
                    result["confidence"],
                    result["score"],
                    str(target),
                    datetime.now().isoformat(),
                    json.dumps(result),
                )
            )
            con.commit()

    def fetch(self, ticker: str | None = None, limit: int = 20) -> list:
        with self._conn() as con:
            if ticker:
                rows = con.execute(
                    "SELECT ticker,horizon,signal,confidence,date,created FROM predictions "
                    "WHERE ticker=? ORDER BY created DESC LIMIT ?",
                    (ticker.upper(), limit)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT ticker,horizon,signal,confidence,date,created FROM predictions "
                    "ORDER BY created DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [
            {"ticker": r[0], "horizon": r[1], "signal": r[2],
             "confidence": r[3], "date": r[4], "created": r[5]}
            for r in rows
        ]

    def save_alert(self, alert: dict):
        with self._conn() as con:
            con.execute(
                "INSERT INTO alerts (ticker,condition,threshold,created,payload) VALUES (?,?,?,?,?)",
                (
                    alert.get("ticker"),
                    alert.get("condition"),
                    alert.get("threshold", 70),
                    datetime.now().isoformat(),
                    json.dumps(alert),
                )
            )
            con.commit()

    def get_alerts(self) -> list:
        with self._conn() as con:
            rows = con.execute(
                "SELECT ticker,condition,threshold,payload FROM alerts WHERE active=1"
            ).fetchall()
        return [json.loads(r[3]) for r in rows]
