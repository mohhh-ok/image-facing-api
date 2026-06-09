"""SQLite アクセス層（docs/database.md）。全 SQL はこのモジュールに集約する。

- 単一プロセス・単一ワーカー前提。FastAPI の sync ハンドラはスレッドプールで動くため、
  1 本の接続を `check_same_thread=False` + RLock で保護する（低スループットなので十分）。
- 値は必ずパラメータバインド（文字列連結禁止・docs/security.md）。
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT UNIQUE NOT NULL,
    description   TEXT,
    api_key_hash  TEXT NOT NULL,
    k             INTEGER,
    settings_json TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project          TEXT NOT NULL,
    image_sha256     TEXT NOT NULL,
    facing           TEXT NOT NULL CHECK (facing IN ('left', 'right')),
    source           TEXT NOT NULL DEFAULT 'human',
    is_flip_aug      INTEGER NOT NULL DEFAULT 0,
    origin_sample_id INTEGER,
    external_id      TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_project_sha   ON samples (project, image_sha256);
CREATE INDEX IF NOT EXISTS idx_samples_project_face  ON samples (project, facing);
CREATE INDEX IF NOT EXISTS idx_samples_project_flip  ON samples (project, is_flip_aug);
CREATE INDEX IF NOT EXISTS idx_samples_origin        ON samples (origin_sample_id);

CREATE TABLE IF NOT EXISTS embeddings (
    sample_id     INTEGER PRIMARY KEY REFERENCES samples(id) ON DELETE CASCADE,
    model_name    TEXT NOT NULL,
    embed_version INTEGER NOT NULL,
    dim           INTEGER NOT NULL,
    vector        BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project      TEXT NOT NULL,
    image_sha256 TEXT,
    facing       TEXT NOT NULL,
    confidence   REAL NOT NULL,
    uncertain    INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- 低レベルヘルパ ---------------------------------------------------

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def _query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchone()

    def _query_all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    # --- projects --------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str | None,
        api_key_hash: str,
        k: int | None = None,
        settings_json: str | None = None,
    ) -> sqlite3.Row:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO projects (name, description, api_key_hash, k, settings_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, description, api_key_hash, k, settings_json, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return row

    def get_project(self, name: str) -> sqlite3.Row | None:
        return self._query_one("SELECT * FROM projects WHERE name = ?", (name,))

    def list_projects(self) -> list[sqlite3.Row]:
        return self._query_all("SELECT * FROM projects ORDER BY name")

    def update_project_api_key(self, name: str, api_key_hash: str) -> None:
        self._execute(
            "UPDATE projects SET api_key_hash = ? WHERE name = ?", (api_key_hash, name)
        )

    def count_samples(self, project: str, *, include_flip: bool = True) -> int:
        sql = "SELECT COUNT(*) AS n FROM samples WHERE project = ?"
        params: list[Any] = [project]
        if not include_flip:
            sql += " AND is_flip_aug = 0"
        row = self._query_one(sql, params)
        return int(row["n"]) if row else 0

    # --- samples / embeddings -------------------------------------------

    def find_sample_by_sha(
        self, project: str, sha: str, *, is_flip_aug: int = 0
    ) -> sqlite3.Row | None:
        return self._query_one(
            """
            SELECT * FROM samples
            WHERE project = ? AND image_sha256 = ? AND is_flip_aug = ?
            ORDER BY id LIMIT 1
            """,
            (project, sha, is_flip_aug),
        )

    def insert_sample(
        self,
        *,
        project: str,
        image_sha256: str,
        facing: str,
        source: str,
        is_flip_aug: int,
        origin_sample_id: int | None,
        external_id: str | None,
    ) -> int:
        now = utcnow()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO samples
                    (project, image_sha256, facing, source, is_flip_aug,
                     origin_sample_id, external_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project,
                    image_sha256,
                    facing,
                    source,
                    is_flip_aug,
                    origin_sample_id,
                    external_id,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def update_sample_facing(self, sample_id: int, facing: str, source: str | None = None) -> None:
        now = utcnow()
        if source is None:
            self._execute(
                "UPDATE samples SET facing = ?, updated_at = ? WHERE id = ?",
                (facing, now, sample_id),
            )
        else:
            self._execute(
                "UPDATE samples SET facing = ?, source = ?, updated_at = ? WHERE id = ?",
                (facing, source, now, sample_id),
            )

    def get_sample(self, sample_id: int) -> sqlite3.Row | None:
        return self._query_one("SELECT * FROM samples WHERE id = ?", (sample_id,))

    def get_flip_child(self, origin_sample_id: int) -> sqlite3.Row | None:
        return self._query_one(
            "SELECT * FROM samples WHERE origin_sample_id = ? AND is_flip_aug = 1 LIMIT 1",
            (origin_sample_id,),
        )

    def delete_sample(self, sample_id: int) -> None:
        # embeddings は ON DELETE CASCADE（PRAGMA foreign_keys=ON）で同時に消える。
        self._execute("DELETE FROM samples WHERE id = ?", (sample_id,))

    def list_samples(
        self,
        project: str,
        *,
        include_flip: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM samples WHERE project = ?"
        params: list[Any] = [project]
        if not include_flip:
            sql += " AND is_flip_aug = 0"
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return self._query_all(sql, params)

    def insert_embedding(
        self, sample_id: int, model_name: str, embed_version: int, dim: int, vector: bytes
    ) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO embeddings (sample_id, model_name, embed_version, dim, vector)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sample_id, model_name, embed_version, dim, vector),
        )

    def iter_embeddings_for_project(self, project: str) -> list[sqlite3.Row]:
        """store のウォームアップ用。sample メタと埋め込みを join して返す。"""
        return self._query_all(
            """
            SELECT s.id AS sample_id, s.facing, s.is_flip_aug, s.origin_sample_id,
                   e.model_name, e.embed_version, e.dim, e.vector
            FROM samples s
            JOIN embeddings e ON e.sample_id = s.id
            WHERE s.project = ?
            ORDER BY s.id
            """,
            (project,),
        )

    def distinct_projects_with_samples(self) -> list[str]:
        rows = self._query_all("SELECT DISTINCT project FROM samples")
        return [r["project"] for r in rows]

    # --- predictions（任意・監査ログ）-----------------------------------

    def insert_prediction(
        self, project: str, image_sha256: str | None, facing: str, confidence: float, uncertain: bool
    ) -> None:
        self._execute(
            """
            INSERT INTO predictions (project, image_sha256, facing, confidence, uncertain, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project, image_sha256, facing, confidence, int(uncertain), utcnow()),
        )
