"""Database initialisation and CRUD helpers for tg_queue_mgmt."""

import aiosqlite
import hmac
import hashlib
import os
import secrets
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "queue.db")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'open',
    current_token_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_number INTEGER NOT NULL,
    counter_id INTEGER REFERENCES counters(id),
    customer_name TEXT,
    purpose TEXT,
    status TEXT DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    assigned_counters TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


async def init_db() -> None:
    """Create tables if they do not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()


# ---------------------------------------------------------------------------
# Counter CRUD
# ---------------------------------------------------------------------------

async def get_counters(include_closed: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if include_closed:
            cursor = await db.execute(
                "SELECT * FROM counters ORDER BY id"
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM counters WHERE status = 'open' ORDER BY id"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_counter(counter_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM counters WHERE id = ?", (counter_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_counter_by_name(name: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM counters WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_counter(name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO counters (name, status) VALUES (?, 'open')", (name,)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "name": name, "status": "open"}


async def rename_counter(counter_id: int, new_name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE counters SET name = ? WHERE id = ?", (new_name, counter_id)
        )
        await db.commit()
        return True


async def remove_counter(counter_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM counters WHERE id = ?", (counter_id,))
        await db.commit()
        return True


async def set_counter_status(counter_id: int, status: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE counters SET status = ? WHERE id = ?", (status, counter_id)
        )
        await db.commit()
        return True


async def set_counter_current_token(counter_id: int, token_id: Optional[int]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE counters SET current_token_id = ? WHERE id = ?",
            (token_id, counter_id),
        )
        await db.commit()


PBKDF2_ITERATIONS = 260000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt, expected = stored_hash.split("$", 3)
            iterations = int(iter_str)
        except (ValueError, TypeError):
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(digest, expected)
    return False


async def add_staff(username: str, password: str, display_name: str = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO staff (username, password_hash, display_name)
            VALUES (?, ?, ?)
            """,
            (username, hash_password(password), display_name),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "username": username,
            "display_name": display_name,
            "assigned_counters": "",
            "is_active": 1,
        }


async def get_staff(username: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM staff WHERE username = ?",
            (username,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_staff_by_id(staff_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM staff WHERE id = ?",
            (staff_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_staff() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM staff ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def remove_staff(staff_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_staff_password(staff_id: int, new_password: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE staff SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), staff_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_staff_counters(staff_id: int, counter_ids: list[int]) -> bool:
    deduped = sorted({int(cid) for cid in counter_ids})
    assigned = ",".join(str(cid) for cid in deduped)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE staff SET assigned_counters = ? WHERE id = ?",
            (assigned, staff_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def set_staff_active(staff_id: int, is_active: bool) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE staff SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, staff_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def verify_staff(username: str, password: str) -> Optional[dict]:
    staff = await get_staff(username)
    if not staff:
        return None
    if int(staff.get("is_active") or 0) != 1:
        return None
    if not _verify_password(password, staff["password_hash"]):
        return None
    return staff


# ---------------------------------------------------------------------------
# Token CRUD
# ---------------------------------------------------------------------------

async def get_next_token_number(counter_id: int) -> int:
    """Return the next sequential token number for a counter (starts at 1 today)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT COALESCE(MAX(token_number), 0) + 1
            FROM tokens
            WHERE counter_id = ?
              AND DATE(created_at) = DATE('now')
            """,
            (counter_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 1


async def create_token(
    counter_id: int,
    customer_name: Optional[str] = None,
    purpose: Optional[str] = None,
) -> dict:
    token_number = await get_next_token_number(counter_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tokens (token_number, counter_id, customer_name, purpose, status)
            VALUES (?, ?, ?, ?, 'waiting')
            """,
            (token_number, counter_id, customer_name, purpose),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "token_number": token_number,
            "counter_id": counter_id,
            "customer_name": customer_name,
            "purpose": purpose,
            "status": "waiting",
        }


async def get_token(token_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tokens WHERE id = ?", (token_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_waiting_tokens(counter_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tokens
            WHERE counter_id = ? AND status = 'waiting'
            ORDER BY id
            """,
            (counter_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_current_token_for_counter(counter_id: int) -> Optional[dict]:
    """Return the token currently being served at a counter."""
    counter = await get_counter(counter_id)
    if not counter or not counter.get("current_token_id"):
        return None
    return await get_token(counter["current_token_id"])


async def call_next_token(counter_id: int) -> Optional[dict]:
    """Mark the next waiting token as 'serving' and advance the counter."""
    waiting = await get_waiting_tokens(counter_id)
    if not waiting:
        return None
    next_token = waiting[0]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE tokens
            SET status = 'serving', called_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_token["id"],),
        )
        # Mark previous serving token as done
        await db.execute(
            """
            UPDATE tokens SET status = 'done'
            WHERE counter_id = ? AND status = 'serving' AND id != ?
            """,
            (counter_id, next_token["id"]),
        )
        await db.execute(
            "UPDATE counters SET current_token_id = ? WHERE id = ?",
            (next_token["id"], counter_id),
        )
        await db.commit()
    return next_token


async def call_previous_token(counter_id: int) -> Optional[dict]:
    """Go back to the token before the current one."""
    counter = await get_counter(counter_id)
    if not counter or not counter.get("current_token_id"):
        return None
    current_id = counter["current_token_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Find the done token just before current
        cursor = await db.execute(
            """
            SELECT * FROM tokens
            WHERE counter_id = ? AND status = 'done' AND id < ?
            ORDER BY id DESC LIMIT 1
            """,
            (counter_id, current_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        prev = dict(row)
        # Revert current back to waiting
        await db.execute(
            "UPDATE tokens SET status = 'waiting', called_at = NULL WHERE id = ?",
            (current_id,),
        )
        # Restore previous to serving
        await db.execute(
            "UPDATE tokens SET status = 'serving', called_at = CURRENT_TIMESTAMP WHERE id = ?",
            (prev["id"],),
        )
        await db.execute(
            "UPDATE counters SET current_token_id = ? WHERE id = ?",
            (prev["id"], counter_id),
        )
        await db.commit()
    return prev


async def recall_current_token(counter_id: int) -> Optional[dict]:
    """Re-announce (recall) the current token without changing anything."""
    counter = await get_counter(counter_id)
    if not counter or not counter.get("current_token_id"):
        return None
    token_id = counter["current_token_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tokens SET called_at = CURRENT_TIMESTAMP WHERE id = ?",
            (token_id,),
        )
        await db.commit()
    return await get_token(token_id)


async def reset_queue(counter_id: Optional[int] = None) -> None:
    """Reset all tokens (or tokens for one counter) to 'skipped' and clear current."""
    async with aiosqlite.connect(DB_PATH) as db:
        if counter_id is not None:
            await db.execute(
                """
                UPDATE tokens SET status = 'skipped'
                WHERE counter_id = ? AND status IN ('waiting', 'serving')
                """,
                (counter_id,),
            )
            await db.execute(
                "UPDATE counters SET current_token_id = NULL WHERE id = ?",
                (counter_id,),
            )
        else:
            await db.execute(
                "UPDATE tokens SET status = 'skipped' WHERE status IN ('waiting', 'serving')"
            )
            await db.execute("UPDATE counters SET current_token_id = NULL")
        await db.commit()


async def tokens_ahead(token_id: int) -> int:
    """How many tokens are ahead of this one in its counter queue."""
    token = await get_token(token_id)
    if not token or token["status"] != "waiting":
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM tokens
            WHERE counter_id = ? AND status = 'waiting' AND id < ?
            """,
            (token["counter_id"], token_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_full_status() -> dict:
    """Return full status snapshot for SSE broadcast."""
    counters = await get_counters()
    result = []
    last_called = None

    for counter in counters:
        current = None
        if counter.get("current_token_id"):
            current = await get_token(counter["current_token_id"])
        waiting = await get_waiting_tokens(counter["id"])

        entry = {
            "id": counter["id"],
            "name": counter["name"],
            "current_token": current["token_number"] if current else None,
            "status": counter["status"],
            "waiting_count": len(waiting),
            "waiting": [
                {
                    "token_number": t["token_number"],
                    "customer_name": t.get("customer_name"),
                }
                for t in waiting
            ],
        }
        result.append(entry)

        if current and (
            last_called is None
            or current["called_at"] > (last_called.get("called_at") or "")
        ):
            last_called = {
                "token": current["token_number"],
                "counter": counter["name"],
                "customer_name": current.get("customer_name"),
                "called_at": current.get("called_at"),
            }

    return {"counters": result, "last_called": last_called}
