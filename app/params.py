"""フル注釈の boolean パラメータ（zoom_up）の既定・検証。

1 sample = facing + zoom_up の束。
zoom_up = 表示を少し大きくすべきか（true → クライアント側の固定倍率、例 ×1.2）。
原因（羽・角・トサカ等）は問わない。未指定は false。
"""

from __future__ import annotations

DEFAULT_ZOOM_UP = False


def parse_zoom_up(raw, *, default: bool = DEFAULT_ZOOM_UP) -> bool:
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    s = str(raw).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    raise ValueError("zoom_up は boolean です")
