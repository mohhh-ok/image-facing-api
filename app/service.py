"""label / predict のコアパイプライン。

routes と admin の手修正がここを共有する（修正は label と同じ経路を通る・docs/admin.md）。
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from . import classifier
from .config import Settings
from .db import Database
from .embed import Embedder
from .errors import bad_request, model_not_loaded
from .images import decode_image, horizontal_flip, save_original, sha256_hex
from .store import Store

VALID_SOURCES = {"human", "import", "model"}


def opposite(facing: str) -> str:
    return "right" if facing == "left" else "left"


@dataclass
class LabelResult:
    sample_id: int
    facing: str
    deduped: bool
    flip_added: bool
    project_size: int


@dataclass
class PredictResult:
    facing: str
    confidence: float
    uncertain: bool
    neighbors: list[classifier.Neighbor]
    model: str
    k: int


class FacingService:
    def __init__(self, db: Database, store: Store, embedder: Embedder | None, settings: Settings):
        self.db = db
        self.store = store
        self.embedder = embedder
        self.settings = settings

    def _require_embedder(self) -> Embedder:
        if self.embedder is None:
            raise model_not_loaded()
        return self.embedder

    def _embed_bytes(self, data: bytes) -> tuple[Image.Image, "object"]:
        embedder = self._require_embedder()
        img = decode_image(data, self.settings.max_image_bytes)
        return img, embedder.embed(img)

    def effective_k(self, project_row) -> int:
        k = project_row["k"] if project_row is not None else None
        return int(k) if k else self.settings.knn_k

    # --- predict ---------------------------------------------------------

    def predict(self, project: str, data: bytes, project_row) -> PredictResult:
        embedder = self._require_embedder()
        _, vector = self._embed_bytes(data)
        index = self.store.get(project)
        k = self.effective_k(project_row)
        pred = classifier.predict(index, vector, k, self.settings.uncertain_threshold)
        return PredictResult(
            facing=pred.facing,
            confidence=pred.confidence,
            uncertain=pred.uncertain,
            neighbors=pred.neighbors,
            model=embedder.model_name,
            k=k,
        )

    # --- label -----------------------------------------------------------

    def add_label(
        self,
        project: str,
        data: bytes,
        facing: str,
        *,
        source: str = "human",
        external_id: str | None = None,
        flip_aug: bool = True,
    ) -> LabelResult:
        if facing not in ("left", "right"):
            raise bad_request("facing は 'left' か 'right' を指定してください")
        if source not in VALID_SOURCES:
            raise bad_request(f"source は {sorted(VALID_SOURCES)} のいずれかです")

        embedder = self._require_embedder()
        img = decode_image(data, self.settings.max_image_bytes)
        sha = sha256_hex(data)

        existing = self.db.find_sample_by_sha(project, sha, is_flip_aug=0)
        if existing is not None:
            return self._update_existing(project, existing, facing, source)

        # 新規: 元画像を保存 → 埋め込み → DB/メモリへ
        save_original(self.settings.images_dir, data, sha)
        vector = embedder.embed(img)
        sample_id = self._insert(
            project, sha, facing, source, is_flip_aug=0, origin_sample_id=None,
            external_id=external_id, vector=vector,
        )

        flip_added = False
        if flip_aug:
            flipped = horizontal_flip(img)
            flip_vec = embedder.embed(flipped)
            self._insert(
                project, sha, opposite(facing), source, is_flip_aug=1,
                origin_sample_id=sample_id, external_id=external_id, vector=flip_vec,
            )
            flip_added = True

        return LabelResult(
            sample_id=sample_id,
            facing=facing,
            deduped=False,
            flip_added=flip_added,
            project_size=self.db.count_samples(project, include_flip=True),
        )

    def _insert(
        self, project, sha, facing, source, *, is_flip_aug, origin_sample_id, external_id, vector
    ) -> int:
        sample_id = self.db.insert_sample(
            project=project,
            image_sha256=sha,
            facing=facing,
            source=source,
            is_flip_aug=is_flip_aug,
            origin_sample_id=origin_sample_id,
            external_id=external_id,
        )
        vec_bytes = vector.astype("float32").tobytes()
        self.db.insert_embedding(
            sample_id, self.embedder.model_name, self.settings.embed_version, vector.shape[0], vec_bytes
        )
        self.store.add(project, sample_id, vector, facing, is_flip_aug, origin_sample_id)
        return sample_id

    def _update_existing(self, project, existing, facing, source) -> LabelResult:
        """同一画像が既にある場合は facing を更新し、flip 拡張行も逆向きに追従させる。"""
        sample_id = int(existing["id"])
        self.db.update_sample_facing(sample_id, facing, source)
        self.store.update_facing(project, sample_id, facing)

        flip_added = False
        child = self.db.get_flip_child(sample_id)
        if child is not None:
            self.db.update_sample_facing(int(child["id"]), opposite(facing), source)
            self.store.update_facing(project, int(child["id"]), opposite(facing))
            flip_added = True

        return LabelResult(
            sample_id=sample_id,
            facing=facing,
            deduped=True,
            flip_added=flip_added,
            project_size=self.db.count_samples(project, include_flip=True),
        )

    # --- admin の手修正（label と同じ経路）-------------------------------

    def correct_facing(self, project: str, sample_id: int, facing: str) -> None:
        if facing not in ("left", "right"):
            raise bad_request("facing は 'left' か 'right' を指定してください")
        row = self.db.get_sample(sample_id)
        if row is None or row["project"] != project or int(row["is_flip_aug"]) == 1:
            raise bad_request("修正対象のサンプルが見つかりません")
        self.db.update_sample_facing(sample_id, facing, "human")
        self.store.update_facing(project, sample_id, facing)
        child = self.db.get_flip_child(sample_id)
        if child is not None:
            self.db.update_sample_facing(int(child["id"]), opposite(facing), "human")
            self.store.update_facing(project, int(child["id"]), opposite(facing))

    def delete_label(self, project: str, sample_id: int) -> int:
        """原本ラベルとその flip 拡張行を DB / index の両方から削除する。

        対象は原本（is_flip_aug=0）のみ指定可。削除した行数（原本+flip子）を返す。
        画像ファイルは sha 単位で他サンプルと共有しうるため、ここでは消さない。
        """
        row = self.db.get_sample(sample_id)
        if row is None or row["project"] != project or int(row["is_flip_aug"]) == 1:
            raise bad_request("削除対象のサンプルが見つかりません（原本ラベルのみ指定可）")

        removed = 0
        child = self.db.get_flip_child(sample_id)
        if child is not None:
            child_id = int(child["id"])
            self.db.delete_sample(child_id)
            self.store.remove(project, child_id)
            removed += 1

        self.db.delete_sample(sample_id)
        self.store.remove(project, sample_id)
        removed += 1
        return removed
