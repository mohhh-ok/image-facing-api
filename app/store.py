"""project ごとの埋め込みインデックス。各 sample は facing + zoom_up。"""

from __future__ import annotations

import threading

import numpy as np

from .db import Database
from .params import DEFAULT_ZOOM_UP


class ProjectIndex:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors = np.empty((0, dim), dtype=np.float32)
        self.sample_ids: list[int] = []
        self.facings: list[str] = []
        self.zoom_ups: list[bool] = []
        self.is_flip: list[int] = []
        self.origin_ids: list[int | None] = []

    @property
    def size(self) -> int:
        return len(self.sample_ids)

    def add(
        self,
        sample_id: int,
        vector: np.ndarray,
        facing: str,
        zoom_up: bool,
        is_flip_aug: int,
        origin_sample_id: int | None,
    ) -> None:
        v = vector.astype(np.float32).reshape(1, -1)
        self.vectors = np.vstack([self.vectors, v]) if self.size else v.copy()
        self.sample_ids.append(sample_id)
        self.facings.append(facing)
        self.zoom_ups.append(bool(zoom_up))
        self.is_flip.append(is_flip_aug)
        self.origin_ids.append(origin_sample_id)

    def update_label(self, sample_id: int, facing: str, zoom_up: bool) -> None:
        try:
            idx = self.sample_ids.index(sample_id)
        except ValueError:
            return
        self.facings[idx] = facing
        self.zoom_ups[idx] = bool(zoom_up)

    def remove(self, sample_id: int) -> bool:
        try:
            idx = self.sample_ids.index(sample_id)
        except ValueError:
            return False
        self.vectors = np.delete(self.vectors, idx, axis=0)
        del self.sample_ids[idx]
        del self.facings[idx]
        del self.zoom_ups[idx]
        del self.is_flip[idx]
        del self.origin_ids[idx]
        return True


class Store:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._lock = threading.RLock()
        self._indexes: dict[str, ProjectIndex] = {}

    def warmup(self, db: Database) -> None:
        with self._lock:
            self._indexes.clear()
            for project in db.distinct_projects_with_samples():
                index = ProjectIndex(self.dim)
                for row in db.iter_embeddings_for_project(project):
                    vec = np.frombuffer(row["vector"], dtype=np.float32)
                    if vec.shape[0] != self.dim:
                        continue
                    keys = row.keys()
                    if "zoom_up" in keys:
                        zoom_up = bool(int(row["zoom_up"]))
                    else:
                        zoom_up = DEFAULT_ZOOM_UP
                    index.add(
                        row["sample_id"],
                        vec,
                        row["facing"],
                        zoom_up,
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
        zoom_up: bool,
        is_flip_aug: int,
        origin_sample_id: int | None,
    ) -> None:
        with self._lock:
            self.get(project).add(
                sample_id, vector, facing, zoom_up, is_flip_aug, origin_sample_id
            )

    def update_label(self, project: str, sample_id: int, facing: str, zoom_up: bool) -> None:
        with self._lock:
            self.get(project).update_label(sample_id, facing, zoom_up)

    def remove(self, project: str, sample_id: int) -> None:
        with self._lock:
            self.get(project).remove(sample_id)

    def project_count(self) -> int:
        with self._lock:
            return len(self._indexes)
