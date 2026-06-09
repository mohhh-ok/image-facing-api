"""API 結合テスト（docs/api.md・docs/roadmap.md の検証観点）。"""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from tests.conftest import create_project, image_bytes, make_image


def _b64(side: str) -> str:
    return base64.b64encode(image_bytes(make_image(side))).decode("ascii")


def _label(client, project, key, side, facing, external_id=None):
    body = {"image_base64": _b64(side), "facing": facing}
    if external_id:
        body["external_id"] = external_id
    return client.post(f"/v1/{project}/label", json=body, headers={"X-API-Key": key})


def _predict(client, project, key, side):
    return client.post(
        f"/v1/{project}/predict", json={"image_base64": _b64(side)}, headers={"X-API-Key": key}
    )


# --- healthz / projects -------------------------------------------------


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_create_project_requires_admin(client):
    resp = client.post("/v1/projects", json={"name": "x"})
    assert resp.status_code == 401


def test_create_project_returns_key_once(client, admin_auth):
    resp = client.post("/v1/projects", json={"name": "proj"}, auth=admin_auth)
    assert resp.status_code == 200
    assert resp.json()["api_key"].startswith("fk_live_")

    listing = client.get("/v1/projects", auth=admin_auth).json()
    assert listing[0]["project"] == "proj"


# --- label / predict ----------------------------------------------------


def test_label_adds_flip_aug(client, admin_auth):
    key = create_project(client, admin_auth)
    resp = _label(client, "proj", key, "left", "left")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flip_added"] is True
    assert body["deduped"] is False
    assert body["project_size"] == 2  # 元 + flip


def test_predict_symmetry(client, admin_auth):
    """left 画像を教えると、その反転は right と判定される（flip 拡張の効果）。"""
    key = create_project(client, admin_auth)
    _label(client, "proj", key, "left", "left")

    same = _predict(client, "proj", key, "left").json()
    assert same["facing"] == "left"

    flipped = _predict(client, "proj", key, "right").json()
    assert flipped["facing"] == "right"


def test_predict_returns_facing_when_no_labels(client, admin_auth):
    key = create_project(client, admin_auth)
    body = _predict(client, "proj", key, "left").json()
    assert body["facing"] in ("left", "right")
    assert body["uncertain"] is True


def test_dedup_updates_facing(client, admin_auth):
    key = create_project(client, admin_auth)
    first = _label(client, "proj", key, "left", "left").json()
    again = _label(client, "proj", key, "left", "right").json()
    assert again["deduped"] is True
    assert again["sample_id"] == first["sample_id"]
    assert again["project_size"] == 2  # 件数は増えない

    # facing を right に直したので、同じ画像の predict は right
    assert _predict(client, "proj", key, "left").json()["facing"] == "right"


def test_include_neighbors_toggle(client, admin_auth):
    key = create_project(client, admin_auth)
    _label(client, "proj", key, "left", "left")
    with_n = client.post(
        "/v1/proj/predict",
        json={"image_base64": _b64("left")},
        headers={"X-API-Key": key},
    ).json()
    assert with_n["neighbors"] is not None

    without = client.post(
        "/v1/proj/predict?include_neighbors=false",
        json={"image_base64": _b64("left")},
        headers={"X-API-Key": key},
    ).json()
    assert without["neighbors"] is None


# --- auth / errors ------------------------------------------------------


def test_missing_api_key(client, admin_auth):
    create_project(client, admin_auth)
    resp = client.post("/v1/proj/predict", json={"image_base64": _b64("left")})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_wrong_api_key(client, admin_auth):
    create_project(client, admin_auth)
    resp = client.post(
        "/v1/proj/predict",
        json={"image_base64": _b64("left")},
        headers={"X-API-Key": "fk_live_wrong"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_no_such_project(client, admin_auth):
    resp = client.post(
        "/v1/ghost/predict",
        json={"image_base64": _b64("left")},
        headers={"X-API-Key": "fk_live_x"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_such_project"


def test_bad_image(client, admin_auth):
    key = create_project(client, admin_auth)
    resp = client.post(
        "/v1/proj/predict",
        json={"image_base64": base64.b64encode(b"not-an-image").decode()},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_image"


def test_label_requires_facing(client, admin_auth):
    key = create_project(client, admin_auth)
    resp = client.post(
        "/v1/proj/label", json={"image_base64": _b64("left")}, headers={"X-API-Key": key}
    )
    assert resp.status_code == 400


def test_project_isolation(client, admin_auth):
    """別 project のラベルに触れない。"""
    key_a = create_project(client, admin_auth, name="a")
    key_b = create_project(client, admin_auth, name="b")
    _label(client, "a", key_a, "left", "left")
    # b は空なので uncertain
    body = client.post(
        "/v1/b/predict", json={"image_base64": _b64("left")}, headers={"X-API-Key": key_b}
    ).json()
    assert body["uncertain"] is True


# --- admin --------------------------------------------------------------


def test_admin_requires_auth(client, admin_auth):
    assert client.get("/admin").status_code == 401


def test_admin_correct_flows_through(client, admin_auth):
    key = create_project(client, admin_auth)
    sample_id = _label(client, "proj", key, "left", "left").json()["sample_id"]

    resp = client.post(
        "/admin/correct",
        data={"project": "proj", "sample_id": str(sample_id), "facing": "right"},
        auth=admin_auth,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # 修正が predict に即反映される
    assert _predict(client, "proj", key, "left").json()["facing"] == "right"


def test_auth_disabled_bypass(app_factory):
    with TestClient(app_factory(True)) as c:
        # admin 認証なしで project 作成できる
        assert c.post("/v1/projects", json={"name": "p"}).status_code == 200
        # API キーなしで predict できる
        assert c.post("/v1/p/predict", json={"image_base64": _b64("left")}).status_code == 200
