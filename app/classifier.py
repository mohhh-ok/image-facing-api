"""k-NN 判定本体。

同一近傍セットから:
  - facing → similarity 重み付き多数決
  - zoom_up → similarity 重み付き多数決（boolean）
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .params import DEFAULT_ZOOM_UP
from .store import ProjectIndex

SIM_FLOOR = 0.5


@dataclass
class Neighbor:
    sample_id: int
    facing: str
    zoom_up: bool
    similarity: float


@dataclass
class Prediction:
    facing: str
    zoom_up: bool
    confidence: float
    uncertain: bool
    neighbors: list[Neighbor]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _group_key(index: ProjectIndex, i: int) -> int:
    origin = index.origin_ids[i]
    return origin if (index.is_flip[i] == 1 and origin is not None) else index.sample_ids[i]


def predict(index: ProjectIndex, query: np.ndarray, k: int, uncertain_threshold: float) -> Prediction:
    if index.size == 0:
        return Prediction(
            facing="left",
            zoom_up=DEFAULT_ZOOM_UP,
            confidence=0.0,
            uncertain=True,
            neighbors=[],
        )

    q = query.astype(np.float32).reshape(-1)
    sims = index.vectors @ q

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

    votes_face = {"left": 0.0, "right": 0.0}
    votes_zoom = {False: 0.0, True: 0.0}
    neighbors: list[Neighbor] = []
    for i in chosen:
        sim = float(sims[i])
        w = _clamp01(sim)
        facing = index.facings[i]
        zoom_up = bool(index.zoom_ups[i])
        votes_face[facing] += w
        votes_zoom[zoom_up] += w
        neighbors.append(
            Neighbor(index.sample_ids[i], facing, zoom_up, round(sim, 4))
        )

    total_face = votes_face["left"] + votes_face["right"]
    if total_face <= 0.0:
        n0 = neighbors[0]
        return Prediction(
            facing=n0.facing,
            zoom_up=n0.zoom_up,
            confidence=0.0,
            uncertain=True,
            neighbors=neighbors,
        )

    if votes_face["left"] > votes_face["right"]:
        facing = "left"
    elif votes_face["right"] > votes_face["left"]:
        facing = "right"
    else:
        facing = neighbors[0].facing

    if votes_zoom[True] > votes_zoom[False]:
        zoom_up = True
    elif votes_zoom[False] > votes_zoom[True]:
        zoom_up = False
    else:
        zoom_up = neighbors[0].zoom_up

    # confidence は向き票の偏りで定義（主用途）。zoom_up は同じ近傍から読む副属性。
    margin = abs(votes_face["left"] - votes_face["right"]) / total_face
    top_sim = float(sims[chosen[0]])
    nearness = _clamp01((top_sim - SIM_FLOOR) / (1.0 - SIM_FLOOR))
    confidence = round(margin * nearness, 4)
    uncertain = confidence < uncertain_threshold

    return Prediction(
        facing=facing,
        zoom_up=zoom_up,
        confidence=confidence,
        uncertain=uncertain,
        neighbors=neighbors,
    )
