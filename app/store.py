"""project ごとの埋め込みインデックスをメモリに保持する（docs/architecture.md）。

DB が source of truth。起動時に DB から復元し、label 時に DB とメモリの両方へ書く。
プロセス再起動で DB から再構築できるので、メモリは純粋なキャッシュ。
"""

from __future__ import annotations

import threading

import numpy as np

from .db import Database


class ProjectIndex:
    """1 project 分の埋め込み行列とサンプルメタ。"""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        # (N, dim) float32, 各行 L2 正規化済み
        self.vectors = np.empty((0, dim), dtype=np.float32)
        self.sample_ids: list[int] = []
        self.facings: list[str] = []          # 'left' | 'right'
        self.is_flip: list[int] = []          # 0 | 1
        self.origin_ids: list[int | None] = []

    @property
    def size(self) -> int:
        return len(self.sample_ids)

    def add(
        self,
        sample_id: int,
        vector: np.ndarray,
        facing: str,
        is_flip_aug: int,
        origin_sample_id: int | None,
    ) -> None:
        v = vector.astype(np.float32).reshape(1, -1)
        self.vectors = np.vstack([self.vectors, v]) if self.size else v.copy()
        self.sample_ids.append(sample_id)
        self.facings.append(facing)
        self.is_flip.append(is_flip_aug)
        self.origin_ids.append(origin_sample_id)

    def update_facing(self, sample_id: int, facing: str) -> None:
        try:
            idx = self.sample_ids.index(sample_id)
        except ValueError:
            return
        self.facings[idx] = facing


class Store:
    """全 project のインデックスを束ねる。スレッドセーフ。"""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._lock = threading.RLock()
        self._indexes: dict[str, ProjectIndex] = {}

    def warmup(self, db: Database) -> None:
        """DB の embeddings を全 project 分メモリへ載せる。"""
        with self._lock:
            self._indexes.clear()
            for project in db.distinct_projects_with_samples():
                index = ProjectIndex(self.dim)
                for row in db.iter_embeddings_for_project(project):
                    vec = np.frombuffer(row["vector"], dtype=np.float32)
                    if vec.shape[0] != self.dim:
                        # モデル/前処理が変わった可能性。ここでは黙って飛ばす（再埋め込み対象）。
                        continue
                    index.add(
                        row["sample_id"],
                        vec,
                        row["facing"],
                        int(row["is_flip_aug"]),
                        row["origin_sample_id"],
                    )
                self._indexes[project] = index

    def get(self, project: str) -> ProjectIndex:
        with self._lock:
            index = self._indexes.get(project)
            if index is None:
                index = ProjectIndex(self.dim)
                self._indexes[project] = index
            return index

    def add(
        self,
        project: str,
        sample_id: int,
        vector: np.ndarray,
        facing: str,
        is_flip_aug: int,
        origin_sample_id: int | None,
    ) -> None:
        with self._lock:
            self.get(project).add(sample_id, vector, facing, is_flip_aug, origin_sample_id)

    def update_facing(self, project: str, sample_id: int, facing: str) -> None:
        with self._lock:
            self.get(project).update_facing(sample_id, facing)

    def project_count(self) -> int:
        with self._lock:
            return len(self._indexes)
