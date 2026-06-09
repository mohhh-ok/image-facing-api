"""k-NN 分類のユニットテスト（docs/model.md の式）。"""

from __future__ import annotations

import numpy as np

from app import classifier
from app.store import ProjectIndex


def _unit(*vals: float) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


def _index_2d() -> ProjectIndex:
    idx = ProjectIndex(dim=2)
    # left の例は (1,0) 付近、right の例は (0,1) 付近
    idx.add(1, _unit(1.0, 0.05), "left", 0, None)
    idx.add(2, _unit(1.0, 0.10), "left", 0, None)
    idx.add(3, _unit(0.05, 1.0), "right", 0, None)
    idx.add(4, _unit(0.10, 1.0), "right", 0, None)
    return idx


def test_empty_index_returns_uncertain_left():
    idx = ProjectIndex(dim=2)
    pred = classifier.predict(idx, _unit(1.0, 0.0), k=9, uncertain_threshold=0.55)
    assert pred.facing == "left"
    assert pred.confidence == 0.0
    assert pred.uncertain is True
    assert pred.neighbors == []


def test_majority_vote_left():
    idx = _index_2d()
    pred = classifier.predict(idx, _unit(1.0, 0.0), k=3, uncertain_threshold=0.55)
    assert pred.facing == "left"
    assert pred.confidence > 0.0
    assert pred.neighbors[0].facing == "left"


def test_majority_vote_right():
    idx = _index_2d()
    pred = classifier.predict(idx, _unit(0.0, 1.0), k=3, uncertain_threshold=0.55)
    assert pred.facing == "right"


def test_flip_aug_dedup_counts_group_once():
    """元(left)と flip(right)が同じ origin グループなら、近傍に両方入っても1票に丸める。"""
    idx = ProjectIndex(dim=2)
    base = _unit(1.0, 0.0)
    idx.add(10, base, "left", 0, None)            # 元
    idx.add(11, base, "right", 1, 10)             # flip 行（origin=10）。同一ベクトルにして衝突を作る
    idx.add(12, _unit(0.9, 0.2), "left", 0, None)  # もう1件 left
    pred = classifier.predict(idx, base, k=2, uncertain_threshold=0.55)
    # グループ畳み込みで {10/11} は1票、12 が1票 → 多数決は安定して left になる
    assert pred.facing == "left"
    # 採用近傍に同一グループの sample が二重に出ていないこと
    keys = {classifier._group_key(idx, idx.sample_ids.index(n.sample_id)) for n in pred.neighbors}
    assert len(keys) == len(pred.neighbors)
