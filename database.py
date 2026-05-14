import sqlite3
from datetime import datetime

DB_PATH = "/app/data/ngrok history.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL,
                pdf_name     TEXT,
                rules_used   TEXT,
                report       TEXT,
                created_at   TEXT
            )
        """)


def save_scan(username: str, pdf_name: str, rules: str, report: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scan_history (username, pdf_name, rules_used, report, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, pdf_name, rules, report, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_history(username: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, pdf_name, rules_used, report, created_at "
            "FROM scan_history WHERE username = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
    return [
        {"id": r[0], "pdf_name": r[1], "rules": r[2], "report": r[3], "created_at": r[4]}
        for r in rows
    ]


def delete_scan(scan_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
