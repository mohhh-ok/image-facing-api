"""k-NN 分類のユニットテスト。"""

from __future__ import annotations

import numpy as np

from app import classifier
from app.params import DEFAULT_ZOOM_UP
from app.store import ProjectIndex


def _unit(*vals: float) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


def _index_2d() -> ProjectIndex:
    idx = ProjectIndex(dim=2)
    idx.add(1, _unit(1.0, 0.05), "left", True, 0, None)
    idx.add(2, _unit(1.0, 0.10), "left", True, 0, None)
    idx.add(3, _unit(0.05, 1.0), "right", False, 0, None)
    idx.add(4, _unit(0.10, 1.0), "right", False, 0, None)
    return idx


def test_empty_index_returns_uncertain_defaults():
    idx = ProjectIndex(dim=2)
    pred = classifier.predict(idx, _unit(1.0, 0.0), k=9, uncertain_threshold=0.55)
    assert pred.facing == "left"
    assert pred.zoom_up is DEFAULT_ZOOM_UP
    assert pred.confidence == 0.0
    assert pred.uncertain is True


def test_majority_vote_left_and_zoom_up():
    idx = _index_2d()
    pred = classifier.predict(idx, _unit(1.0, 0.0), k=3, uncertain_threshold=0.55)
    assert pred.facing == "left"
    assert pred.zoom_up is True
    assert pred.confidence > 0.0


def test_majority_vote_right_and_normal():
    idx = _index_2d()
    pred = classifier.predict(idx, _unit(0.0, 1.0), k=3, uncertain_threshold=0.55)
    assert pred.facing == "right"
    assert pred.zoom_up is False


def test_flip_aug_dedup_counts_group_once():
    idx = ProjectIndex(dim=2)
    base = _unit(1.0, 0.0)
    idx.add(10, base, "left", True, 0, None)
    idx.add(11, base, "right", True, 1, 10)
    idx.add(12, _unit(0.9, 0.2), "left", False, 0, None)
    pred = classifier.predict(idx, base, k=2, uncertain_threshold=0.55)
    assert pred.facing == "left"
    keys = {classifier._group_key(idx, idx.sample_ids.index(n.sample_id)) for n in pred.neighbors}
    assert len(keys) == len(pred.neighbors)
