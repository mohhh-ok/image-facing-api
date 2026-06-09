"""k-NN 判定本体（docs/model.md）。

- 距離は cosine 類似度。ベクトルは L2 正規化済みなので内積でよい。
- 近傍 k 件の facing を similarity 重み付きで多数決。
- flip 拡張による二重カウントを抑制（元・反転は同じ「拡張グループ」とみなし1票に丸める）。
- confidence = 票の偏り(margin) × 近さ(top_sim の伸び)。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .store import ProjectIndex

# top_sim をこの値から 1.0 へ線形に伸ばして「近さ」スコアにする。
# これ未満の類似度しか無い（似た学習例が無い）と confidence は 0 に潰れる。
SIM_FLOOR = 0.5


@dataclass
class Neighbor:
    sample_id: int
    facing: str
    similarity: float


@dataclass
class Prediction:
    facing: str
    confidence: float
    uncertain: bool
    neighbors: list[Neighbor]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _group_key(index: ProjectIndex, i: int) -> int:
    """flip 拡張の二重カウント抑制用。元行は自分の id、flip 行は origin の id でグループ化。"""
    origin = index.origin_ids[i]
    return origin if (index.is_flip[i] == 1 and origin is not None) else index.sample_ids[i]


def predict(index: ProjectIndex, query: np.ndarray, k: int, uncertain_threshold: float) -> Prediction:
    n = index.size
    if n == 0:
        # ラベルがまだ無い project。二択は強制されるので left を返しつつ uncertain。
        return Prediction(facing="left", confidence=0.0, uncertain=True, neighbors=[])

    q = query.astype(np.float32).reshape(-1)
    sims = index.vectors @ q  # (N,) cosine 類似度

    # 類似度降順。グループ単位で重複を畳みつつ上位 k グループを採る。
    order = np.argsort(-sims)
    chosen: list[int] = []
    seen_groups: set[int] = set()
    for i in order:
        gk = _group_key(index, int(i))
        if gk in seen_groups:
            continue
        seen_groups.add(gk)
        chosen.append(int(i))
        if len(chosen) >= k:
            break

    # 重み付き票（重み = similarity を [0,1] にクランプ）
    votes = {"left": 0.0, "right": 0.0}
    neighbors: list[Neighbor] = []
    for i in chosen:
        sim = float(sims[i])
        facing = index.facings[i]
        votes[facing] += _clamp01(sim)
        neighbors.append(Neighbor(index.sample_ids[i], facing, round(sim, 4)))

    total = votes["left"] + votes["right"]
    if total <= 0.0:
        # 近傍がどれも非類似（sim<=0）。最近傍の facing に倒し、確信度 0。
        facing = neighbors[0].facing
        return Prediction(facing=facing, confidence=0.0, uncertain=True, neighbors=neighbors)

    if votes["left"] > votes["right"]:
        facing = "left"
    elif votes["right"] > votes["left"]:
        facing = "right"
    else:
        facing = neighbors[0].facing  # 同数なら最近傍に倒す

    margin = abs(votes["left"] - votes["right"]) / total
    top_sim = float(sims[chosen[0]])
    nearness = _clamp01((top_sim - SIM_FLOOR) / (1.0 - SIM_FLOOR))
    confidence = round(margin * nearness, 4)
    uncertain = confidence < uncertain_threshold

    return Prediction(facing=facing, confidence=confidence, uncertain=uncertain, neighbors=neighbors)
