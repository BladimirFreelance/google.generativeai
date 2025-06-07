import os
import sqlite3

_DEFAULT_PATH = os.path.expanduser("~/.veo_api_keys.db")


def _connect(path: str = _DEFAULT_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_keys (key TEXT PRIMARY KEY)"
    )
    return conn


def load_keys(path: str = _DEFAULT_PATH):
    """Return a list of stored API keys."""
    with _connect(path) as conn:
        rows = conn.execute("SELECT key FROM api_keys").fetchall()
    return [r[0] for r in rows]


def save_key(key: str, path: str = _DEFAULT_PATH) -> None:
    """Insert an API key if it doesn't already exist."""
    if not key:
        return
    with _connect(path) as conn:
        conn.execute("INSERT OR IGNORE INTO api_keys (key) VALUES (?)", (key,))
        conn.commit()
