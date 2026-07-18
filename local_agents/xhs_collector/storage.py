from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class LocalStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                create table if not exists state (
                    key text primary key,
                    value text not null
                );
                create table if not exists pending_uploads (
                    id integer primary key autoincrement,
                    endpoint text not null,
                    payload text not null,
                    attempts integer not null default 0,
                    created_at text not null default current_timestamp
                );
            """)

    def connect(self):
        return sqlite3.connect(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self.connect() as db:
            row = db.execute("select value from state where key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        with self.connect() as db:
            db.execute("insert into state(key,value) values(?,?) on conflict(key) do update set value=excluded.value", (key, encoded))

    def enqueue(self, endpoint: str, payload: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("insert into pending_uploads(endpoint,payload) values(?,?)", (endpoint, json.dumps(payload, ensure_ascii=False)))

    def pending(self, limit: int = 50) -> list[tuple[int, str, dict[str, Any]]]:
        with self.connect() as db:
            rows = db.execute("select id,endpoint,payload from pending_uploads order by id limit ?", (limit,)).fetchall()
        return [(row[0], row[1], json.loads(row[2])) for row in rows]

    def uploaded(self, row_id: int) -> None:
        with self.connect() as db:
            db.execute("delete from pending_uploads where id=?", (row_id,))

    def failed_attempt(self, row_id: int) -> None:
        with self.connect() as db:
            db.execute("update pending_uploads set attempts=attempts+1 where id=?", (row_id,))

    def pending_count(self) -> int:
        with self.connect() as db:
            return int(db.execute("select count(*) from pending_uploads").fetchone()[0])
