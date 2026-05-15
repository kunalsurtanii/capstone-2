import os
import sqlite3
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken

DB_PATH = "/app/data/history.db"

# ── Encryption setup ──────────────────────────────────────────────────────────
# Key must be a URL-safe base64-encoded 32-byte value.
# Generate once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then set it as the DB_ENCRYPTION_KEY environment variable.
_raw_key = os.environ.get("DB_ENCRYPTION_KEY", "")
if _raw_key:
    _fernet = Fernet(_raw_key.encode())
else:
    # No key set → generate a session-only key (data is encrypted but key is
    # lost on restart, so rows written in one run can't be read in another).
    # Acceptable for local dev; production MUST set DB_ENCRYPTION_KEY.
    _fernet = Fernet(Fernet.generate_key())


def _enc(text: str) -> str:
    """Encrypt a string → store as hex string in SQLite TEXT column."""
    return _fernet.encrypt(text.encode()).hex()


def _dec(value: str) -> str:
    """Decrypt a hex-encoded encrypted string."""
    try:
        return _fernet.decrypt(bytes.fromhex(value)).decode()
    except (InvalidToken, ValueError):
        return "[encrypted — key mismatch]"


# ── DB helpers ────────────────────────────────────────────────────────────────

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
            (username, pdf_name, _enc(rules), _enc(report),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_history(username: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, pdf_name, rules_used, report, created_at "
            "FROM scan_history WHERE username = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "pdf_name": r[1],
            "rules": _dec(r[2]),
            "report": _dec(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]


def delete_scan(scan_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))